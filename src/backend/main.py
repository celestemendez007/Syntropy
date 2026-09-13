import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import groq
from dotenv import load_dotenv
import pandas as pd
import json

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src", "backend"))

from score_customer import score_customer
from policy_engine import get_eligible_alternatives
from conversation_engine import build_system_prompt, check_hallucination

load_dotenv()

app = FastAPI(title="Syntropy Simulator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local Vite dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    customer_id: str
    history: list[ChatMessage]
    force_archetype: str | None = None
    force_product: str | None = None

# Load models and data at startup
golden_customers_df = None

@app.on_event("startup")
def startup_event():
    global golden_customers_df
    try:
        golden_customers_df = pd.read_csv("data/synthetic/golden_customers.csv")
    except Exception as e:
        print("Error loading golden customers:", e)
        golden_customers_df = pd.DataFrame()

@app.get("/api/customers")
def get_customers():
    if golden_customers_df.empty:
        return []
    # La columna real en golden_customers.csv es `golden_scenario`, no `scenario`
    # -- este endpoint tronaba con KeyError y el dropdown del simulador nunca cargaba.
    return (golden_customers_df[['customer_id', 'golden_scenario']]
            .rename(columns={'golden_scenario': 'scenario'})
            .to_dict(orient="records"))

@app.post("/api/chat")
def chat(req: ChatRequest):
    groq_api_key = os.environ.get("GROQ_API_KEY")
    
    # 1. Run the banking logic or use forced random profile
    if req.force_archetype and req.force_product:
        config_path = os.path.join(os.path.dirname(__file__), "archetypes_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            archetypes = json.load(f)
            
        target_arch = next((a for a in archetypes if a["id"] == req.force_archetype), archetypes[0])
        situation = target_arch["match"]["situations"][0] if target_arch["match"]["situations"] else "S0"
        digital_cap = target_arch["match"]["digital_capabilities"][0] if target_arch["match"]["digital_capabilities"] else "D1"
        
        score = {
            "profile": {
                "credit_product": req.force_product,
                "digital_capability": digital_cap
            },
            "situation": {
                "situation_hint": situation
            }
        }
        
        # Extract alternatives for guardrails
        alts_text = ""
        for line in target_arch.get("useful_alternatives", []):
            if req.force_product in line:
                if ":" in line:
                    alts_text = line.split(":", 1)[1]
                else:
                    alts_text = line
                break
                
        if not alts_text and target_arch.get("useful_alternatives"):
            alts_text = target_arch["useful_alternatives"][0].split(":", 1)[1] if ":" in target_arch["useful_alternatives"][0] else target_arch["useful_alternatives"][0]
            
        alts = [{"alt_id": alt.strip()} for alt in alts_text.split(",") if alt.strip()]
    else:
        try:
            score = score_customer(req.customer_id)
            # get_eligible_alternatives espera (customer_id, risk_profile) -- risk_profile
            # necesita "situation_hint" (vive en score["situation"]), no en score["risk"].
            # La llamada anterior pasaba (score["risk"], score["profile"]), que no es ni
            # el cliente ni un risk_profile valido: siempre devolvia alternativas vacias
            # sin avisar, asi que el LLM nunca tenia nada real que ofrecer.
            risk_profile_for_policy = {**score["situation"], **score["risk"]}
            alts = get_eligible_alternatives(req.customer_id, risk_profile_for_policy)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))
    
    # 2. Build the strict guardrail prompt
    system_prompt = build_system_prompt(score, alts)
    
    if not groq_api_key:
        # --- Motor Conversacional Mock (Multi-Fase), SIN API key de Groq ---
        #
        # Antes esto avanzaba contando turnos (n == 1, n == 2...) y saludaba a
        # "Carlos" siempre, sin importar quién fuera el cliente real -- por eso
        # se sentía robótico y "perdía el hilo" en cuanto el cliente decía algo
        # fuera del guion esperado para ese número de turno exacto.
        #
        # Ahora la fase se determina leyendo la ÚLTIMA RESPUESTA DEL ASISTENTE
        # en el historial (no un contador ciego), así que si el cliente contesta
        # "fuera de orden" la conversación sigue desde donde de verdad se quedó,
        # no desde donde el contador de turnos asumía que debía estar. Y el
        # nombre/monto/producto/días son los REALES del cliente (`score`), nunca
        # inventados -- así nunca chocan con el guardrail `check_hallucination`.
        last_msg = req.history[-1].content.lower().strip() if req.history else ""
        last_bot_msg = next((m.content for m in reversed(req.history) if m.role == "assistant"), "")

        policy_context = score.get("policy_context", {})
        name = policy_context.get("customer_display_name") or "estimado cliente"
        product = req.force_product or score.get("profile", {}).get("credit_product", "su crédito")
        amount = policy_context.get("installment_amount")
        days_left = score.get("days_to_due")
        amount_display = f"${amount:.2f}" if amount is not None else "su cuota"
        days_display = str(days_left) if days_left is not None else "pocos"

        # --- Intent helpers (sobre el ÚLTIMO mensaje del cliente) ---
        def has(words): return any(w in last_msg for w in words)
        is_yes       = has(["si", "sí", "claro", "ok", "bueno", "dale", "correcto", "perfecto", "adelante", "diga", "aha", "aham"])
        is_no_time   = has(["ocupad", "luego", "despues", "después", "ahorita no", "no puedo hablar", "no tengo tiempo"])
        is_confused  = has(["quien", "quién", "de donde", "qué banco", "cuál banco", "no entiendo", "que pasa", "cómo", "como así"])
        is_paid      = has(["ya pagué", "ya pague", "ya lo hice", "ya realicé", "ya transferí"])
        is_problem   = has(["malo", "mal", "problema", "error", "falla", "no tengo", "no me alcanza", "quedé corto", "falta", "aprieto", "difícil", "dificil", "complicado", "no cuento"])
        is_angry     = has(["molest", "enfad", "indign", "grosería", "irresponsable", "siempre hacen", "pésimo", "pesimo", "mal servicio"])
        is_agreement = has(["de acuerdo", "acepto", "está bien", "listo", "perfecto", "va", "hecho", "venga"])
        is_question  = has(["cuánto", "cuanto", "cuando", "cuándo", "cómo pago", "donde pago", "por qué", "porque me llaman"])
        is_reject    = has(["no", "no quiero", "no me sirve", "no puedo con eso", "otra opción", "otra opcion"]) and not is_yes

        # --- Fase actual: se lee de la última respuesta del asistente, no de un contador ---
        if not last_bot_msg:
            phase = "START"
        elif "¿Hablo con" in last_bot_msg:
            phase = "GREETING"
        elif "normalmente usted siempre está al día" in last_bot_msg or "¿Cómo va todo este mes?" in last_bot_msg:
            phase = "INTRO"
        elif "a veces los imprevistos" in last_bot_msg or "déjeme registrar su queja" in last_bot_msg:
            phase = "LISTENING"
        elif "tengo autorizado ofrecerle" in last_bot_msg:
            phase = "OFFERING"
        elif "Para confirmar" in last_bot_msg:
            phase = "CONFIRMING"
        else:
            phase = "OTHER"

        def offer_text():
            if not alts:
                return "conectarle con un asesor para revisar su caso con más detalle"
            alt = alts[0]
            parts = [f"**{alt['alt_id']}**"]
            for key in ("date", "min_amount", "min_percentage", "percentage", "grace_days"):
                if alt.get(key) is not None:
                    parts.append(f"{key}={alt[key]}")
            return " ".join(parts)

        # --- Máquina de estados: (fase_anterior, intención del cliente) -> respuesta ---
        if phase == "START":
            reply = f"¡Hola! Muy buenos días. ¿Hablo con {name}?"

        elif phase == "GREETING" and is_confused:
            reply = f"Disculpe, claro. Le habla Sofía, asesora de Bancoagrícola. Le llamo por su {product}. ¿Tiene un minutito?"

        elif phase == "GREETING" and is_no_time:
            reply = "Entendido, no hay problema. ¿A qué hora le queda mejor para devolverle la llamada?"

        elif phase == "GREETING":
            # Cualquier respuesta que no sea "no tengo tiempo" se toma como que sí es la persona
            reply = (f"Perfecto, {name}. Gracias. Fíjese que le llamo porque notamos que se acerca su fecha "
                     f"de pago de {product} y normalmente usted siempre está al día. Solo quería asegurarme "
                     f"de que todo estuviera bien de su parte. ¿Cómo va todo este mes?")

        elif is_paid:
            reply = (f"¡Qué bien, {name}! Si ya realizó el pago, el sistema se actualizará en las próximas "
                     f"horas. Le agradecemos mucho su puntualidad. ¿Hay algo más en que le podamos ayudar?")

        elif is_angry:
            reply = (f"{name}, tiene toda la razón y entiendo su molestia. Antes de cualquier otra cosa, "
                     f"déjeme registrar su queja para que quede documentada. ¿Me puede contar exactamente qué pasó?")

        elif phase == "INTRO" and is_question:
            reply = (f"Claro que sí. Su cuota es de {amount_display} y su fecha límite es en {days_display} "
                     f"días. Puede pagar desde la app, en ventanilla o en cualquier corresponsal. "
                     f"¿Cuál le queda más fácil?")

        elif phase in ("INTRO", "LISTENING") and (is_problem or (phase == "INTRO" and not is_question)):
            reply = ("Entiendo perfectamente, a veces los imprevistos aparecen. No se preocupe, para eso "
                     "estamos. ¿Es una situación de esta quincena o viene de un poco más atrás?")

        elif phase == "LISTENING":
            # Ya escuchamos al menos una vez -- pasar a ofrecer, sin importar la palabra exacta
            reply = (f"Perfecto {name}, le cuento. Dado su perfil con nosotros, tengo autorizado ofrecerle "
                     f"una opción que puede ayudarle: {offer_text()}. Esto le permitiría estar tranquilo "
                     f"con su historial. ¿Le parece una buena opción o prefiere ver otra alternativa?")

        elif phase == "OFFERING" and is_reject and len(alts) > 1:
            reply = f"Entiendo, no hay problema. También tengo disponible: {alts[1]['alt_id']}. ¿Le acomoda más esta?"

        elif phase == "OFFERING" and is_reject:
            reply = ("Entiendo. Si ninguna de estas opciones le funciona, lo mejor es que hable directo con "
                     "un asesor humano para revisar su caso con más detalle -- ¿le parece si lo conecto?")

        elif phase == "OFFERING" and has(["app", "ventanilla", "corresponsal", "banca en línea", "banca en linea"]):
            # El cliente ya adelantó el canal de pago en el mismo mensaje que acepta --
            # no volver a preguntarlo, es justo el tipo de "no sigue la conversación"
            # que se sentía roto antes.
            channel_named = "la app" if "app" in last_msg else ("ventanilla" if "ventanilla" in last_msg else "ese canal")
            reply = (f"Excelente, {name}, quedamos en {offer_text()} para su {product}, pagando desde "
                     f"{channel_named}. Le llegará un mensaje de texto en los próximos minutos con el "
                     f"resumen. ¡Muchas gracias por su tiempo! Que tenga un excelente día.")

        elif phase == "OFFERING":
            reply = (f"Excelente, {name}. Para confirmar: quedamos en {offer_text()} para su {product}. "
                     f"Le llegará un mensaje de texto en los próximos minutos con el resumen. "
                     f"¿El pago lo haría desde la app o prefiere ventanilla?")

        elif phase == "CONFIRMING":
            reply = (f"Perfecto. Entonces, solo para dejarlo bien anotado en el sistema: el arreglo queda "
                     f"registrado para los próximos {days_display} días. ¡Muchas gracias por su tiempo, "
                     f"{name}! Que tenga un excelente día.")

        else:
            reply = f"Cuénteme un poco más, {name}, para poder orientarle de la mejor manera posible."

        hallucination_check = check_hallucination(reply, alts)
        return {
            "reply": reply,
            "hallucination_flagged": hallucination_check["llm_hallucination_flag"],
            "unauthorized_mentions": hallucination_check["unauthorized_mentions"]
        }

    client = groq.Groq(api_key=groq_api_key)
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})

    # 3. Call the LLM
    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.1-8b-instant",  # Extremely fast, free tier
            temperature=0,  # Enforce determinism and banking strictness
            max_tokens=400,
        )
        reply = chat_completion.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")

    # 4. Run the guardrails on the LLM's response before sending it back
    hallucination_check = check_hallucination(reply, alts)

    return {
        "reply": reply,
        "hallucination_flagged": hallucination_check["llm_hallucination_flag"],
        "unauthorized_mentions": hallucination_check["unauthorized_mentions"]
    }

@app.get("/api/archetypes")
def get_archetypes():
    config_path = os.path.join(os.path.dirname(__file__), "archetypes_config.json")
    if not os.path.exists(config_path):
        return []
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/archetypes")
def update_archetypes(new_config: list[dict]):
    config_path = os.path.join(os.path.dirname(__file__), "archetypes_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2, ensure_ascii=False)
    return {"status": "success"}
