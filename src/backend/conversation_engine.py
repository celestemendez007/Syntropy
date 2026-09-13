"""
conversation_engine.py — Fase 6: capa conversacional (BA_A_Tiempo_Propuesta_v2.md §5, §9).

Principio invariante del proyecto: **la IA conversa; el banco decide.** Este módulo
NO decide qué se le puede ofrecer a un cliente (eso ya lo resolvió `policy_engine.py`
en Fase 5, antes de que exista una sola palabra de conversación) -- solo construye el
prompt con las alternativas YA resueltas, define las categorías cerradas que el LLM
debe usar para clasificar la conversación, y verifica que la respuesta del LLM no
haya mencionado nada fuera de lo autorizado.

No hay una llamada real a un LLM en este repo (no hay `OPENAI_API_KEY` real en
`.env.example`, solo el placeholder). `call_llm()` es el punto de integración: hoy
delega en `_mock_llm_response()`, un clasificador determinista por palabras clave que
sirve para generar las golden conversations y correr los tests sin red ni API key.
Reemplazar `call_llm()` por una llamada real (OpenAI/Anthropic) con
`temperature=0` (ver RECOMMENDED_LLM_PARAMS) no debería requerir tocar nada más de
este módulo: el guardrail y las categorías cerradas son independientes del proveedor.
"""
import re
import os
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Categorías cerradas (BA_A_Tiempo_Propuesta_v2.md §5)
# ---------------------------------------------------------------------------

BARRIER_CATEGORIES = ["FORGOT", "DATE_MISMATCH", "LIQUIDITY", "TECHNICAL", "DISPUTE",
                      "REFUSAL", "ALREADY_PAID", "OTHER"]

BARRIER_DESCRIPTIONS = {
    "FORGOT": "Olvido / no tenía presente la fecha (ej: 'no me acordaba')",
    "DATE_MISMATCH": "El ingreso llega después del vencimiento (ej: 'me pagan hasta el 30')",
    "LIQUIDITY": "No alcanza el dinero este mes (ej: 'este mes no puedo completar')",
    "TECHNICAL": "Intentó pagar y falló (ej: 'la app no me deja')",
    "DISPUTE": "No reconoce el cargo / desacuerdo (ej: 'eso no es lo que me cobraron')",
    "REFUSAL": "No quiere ser contactado (ej: 'no me escriban')",
    "ALREADY_PAID": "Dice que ya pagó (ej: 'ya pagué ayer')",
    "OTHER": "No clasificable en las anteriores",
}

TONE_CATEGORIES = ["COOPERATIVE", "NEUTRAL", "TENSE", "HOSTILE"]
TONE_TRAJECTORIES = ["STABLE", "IMPROVING", "WORSENING"]

# Barrera != situación: la situación es lo que el sistema infiere de datos (situation_hint,
# Fase 2-3); la barrera es lo que el cliente dice. barrier_vs_situation_match compara ambas.
SITUATION_TO_EXPECTED_BARRIER = {"S1": "FORGOT", "S2": "DATE_MISMATCH", "S3": "LIQUIDITY"}

# ---------------------------------------------------------------------------
# Parámetros recomendados del LLM
# ---------------------------------------------------------------------------

RECOMMENDED_LLM_PARAMS = {
    "temperature": 0,
    "top_p": 1,
    "max_tokens": 400,
}
"""
temperature=0 (SUPUESTO DE DEMO, pero no arbitrario): este LLM no está para ser creativo,
está para (a) clasificar barrera/tono de una lista cerrada y (b) parafrasear alternativas
YA resueltas por el Policy Engine. Ambas son tareas de baja entropía donde la variabilidad
de temperature>0 solo aumenta el riesgo de que el modelo "redondee" un monto, invente una
fecha plausible-pero-no-autorizada, o clasifique la barrera distinto en dos corridas
idénticas -- inaceptable para algo que se audita (`policy_decision_id`) y se le puede pedir
cuentas a un banco. Si el jurado pregunta por qué no mayor temperature para sonar "más
natural": la naturalidad del tono se logra con el prompt (empatía explícita en las
instrucciones), no con muestreo aleatorio en la parte que decide qué se promete.
"""

# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """Eres el asistente conversacional de BA A Tiempo (Bancoagrícola). \
Tu único objetivo es entender por qué un cliente no ha pagado a tiempo y ofrecerle, con empatía, \
una salida real. Nunca actúas como cobrador agresivo.

## Reglas que NO puedes romper (se verifican automáticamente después de cada respuesta)
1. Solo puedes ofrecer las alternativas de la lista "ALTERNATIVAS AUTORIZADAS" de abajo, con \
exactamente los montos, porcentajes y fechas ya escritos ahí. Nunca inventes, redondees, \
extiendas ni combines una alternativa que no esté en la lista tal cual.
2. Si el cliente pide algo que no está en la lista (una fecha distinta, un descuento, \
"sin intereses"), no lo aceptes ni lo repitas como si fuera válido: explica que no está \
autorizado y ofrece únicamente lo que sí lo está, o escala a un humano si insiste.
3. Al cerrar la conversación, clasifica exactamente una `barrier_detected` de esta lista \
cerrada (nunca inventes una categoría nueva): {barrier_list}
4. Al cerrar la conversación, clasifica `tone_overall` de esta lista cerrada: {tone_list}
5. Si el tono es HOSTILE, o la barrera es DISPUTE, o no logras clasificar con confianza \
razonable (OTHER), termina la conversación y marca escalamiento a un humano -- no sigas \
negociando.
6. Si el cliente dice que ya pagó (ALREADY_PAID), no insistas con alternativas: indica que se \
verificará el pago.
7. Si la fecha de ingreso del cliente es desconocida (ver contexto), PREGUNTA cuándo cobra en \
vez de asumir una fecha.
8. Si el cliente ya usa un producto de liquidez rotativa (Credicheque, Sobregiro, Extrafinanciamiento, \
Adelanto de Salario) y está en presión de liquidez, NUNCA sugieras "sacar otro adelanto" o "usar el \
sobregiro" como solución -- solo lo que aparezca en ALTERNATIVAS AUTORIZADAS, y si no hay ninguna \
buena, ofrece hablar con un asesor.
9. Si el cliente no puede iniciar sesión, recuperar su contraseña, o el problema es de acceso/seguridad \
a la cuenta, NO intentes resolverlo tú: nunca pidas ni proceses credenciales, y ofrece de inmediato \
conectarlo con un asesor.
10. COMPORTAMIENTO HUMANO Y EMPÁTICO: No suenes como un robot. Usa muletillas naturales ("este...", "bueno", "¡Qué tal!"). Si el cliente solo dice "Hola", salúdalo de vuelta, inventa un nombre para él (ej. Carlos, María), inventa un monto exacto de cuota (ej. $124.50) y los días que faltan (ej. 5 días). Dile el motivo de la llamada de forma súper amigable (recordatorio preventivo) y pregúntale cómo le puedes ayudar ANTES de recitarle opciones.
11. NUNCA ofrezcas la alternativa de solución en tu primer mensaje. Primero escucha la situación del cliente, demuestra empatía ("Entiendo perfectamente, a veces hay gastos imprevistos..."), y luego ofrécele la solución autorizada como si le estuvieras haciendo un favor especial.

{archetype_block}

## Contexto del cliente (ya calculado por el sistema, no lo cuestiones ni lo recalcules)
- Situación: {situation_hint} (ver nota interna, no se la reveles al cliente con este código)
- Producto crediticio: {credit_product}
- Capacidad digital estimada: {digital_capability}
- Cliente conocido por baja respuesta digital: {low_digital_response}
- Canal de este contacto: {channel}
{extra_context}

## ALTERNATIVAS AUTORIZADAS (las únicas que puedes ofrecer, con parámetros ya resueltos)
{alternatives_block}

Responde siempre en español, en tono cercano y respetuoso, en turnos cortos.
"""

def load_archetypes_config():
    config_path = os.path.join(os.path.dirname(__file__), "archetypes_config.json")
    if not os.path.exists(config_path):
        return []
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _get_archetype(situation_hint: str, digital_capability: str) -> dict:
    archetypes = load_archetypes_config()
    for arch in archetypes:
        match = arch.get("match", {})
        if situation_hint in match.get("situations", []) and digital_capability in match.get("digital_capabilities", []):
            return arch
    return {}

def _archetype_block(situation_hint: str, digital_capability: str) -> str:
    arch = _get_archetype(situation_hint, digital_capability)
    if not arch:
        return ""
    
    lines = [f"## Perfil Identificado: {arch.get('name', 'Desconocido')}"]
    lines.append(f"Descripción: {arch.get('description', '')}")
    
    can_do = arch.get("ai_can_do", [])
    if can_do:
        lines.append("Qué puedes hacer (IA):")
        for item in can_do:
            lines.append(f"- {item}")
            
    escalation = arch.get("escalation_rules", [])
    if escalation:
        lines.append("Reglas de escalamiento (CUÁNDO DEBES DETENERTE Y PASAR A UN HUMANO):")
        for item in escalation:
            lines.append(f"- {item}")
            
    return "\n".join(lines)


def _format_alternatives_block(eligible_alternatives: list) -> str:
    if not eligible_alternatives:
        return "(Ninguna. No hay nada que ofrecer -- si el cliente insiste, escala a un humano.)"
    lines = []
    for alt in eligible_alternatives:
        parts = [f"- {alt['alt_id']} ({alt.get('type', '')})"]
        for key in ("date", "min_amount", "min_percentage", "percentage", "grace_days"):
            if key in alt and alt[key] is not None:
                parts.append(f"{key}={alt[key]}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def build_system_prompt(score_result: dict, eligible_alternatives: list) -> str:
    """Arma el prompt del sistema para un cliente puntual, usando el contrato v2
    (`score_customer`) y la lista ya resuelta del Policy Engine. No incluye el
    catálogo completo ni las condiciones de elegibilidad -- solo lo ya autorizado."""
    situation = score_result.get("situation", {})
    profile = score_result.get("profile", {})
    extra_context = ""
    if "income_date_unknown" in situation.get("flags", []):
        extra_context = "- Nota: no se conoce la fecha de ingreso de este cliente; pregúntasela.\n"

    return SYSTEM_PROMPT_TEMPLATE.format(
        barrier_list=", ".join(BARRIER_CATEGORIES),
        tone_list=", ".join(TONE_CATEGORIES),
        situation_hint=situation.get("situation_hint", "S0"),
        low_digital_response=situation.get("low_digital_response", False),
        channel=score_result.get("channel", {}).get("channel_pref_model", "UNDETERMINED"),
        credit_product=profile.get("credit_product", "N/D"),
        digital_capability=profile.get("digital_capability", "D1"),
        archetype_block=_archetype_block(situation.get("situation_hint", "S0"), profile.get("digital_capability", "D1")),
        extra_context=extra_context,
        alternatives_block=_format_alternatives_block(eligible_alternatives),
    )


def should_escalate(tone_overall: str, barrier_detected: str, barrier_confidence: float = 1.0) -> bool:
    """Regla de escalamiento (§5.2): HOSTILE, DISPUTE, o clasificación de baja confianza."""
    if tone_overall == "HOSTILE":
        return True
    if barrier_detected == "DISPUTE":
        return True
    if barrier_detected == "OTHER" and barrier_confidence < 0.5:
        return True
    return False


# ---------------------------------------------------------------------------
# Guardrail anti-alucinación: montos y fechas no autorizados
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_AMOUNT_RE = re.compile(r"\$\s?(\d+(?:[.,]\d+)?)")
_PERCENTAGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s?%")


def _authorized_values(eligible_alternatives: list) -> dict:
    dates, amounts, percentages = set(), set(), set()
    for alt in eligible_alternatives:
        if alt.get("date"):
            dates.add(alt["date"])
        if alt.get("min_amount") is not None:
            amounts.add(round(float(alt["min_amount"]), 2))
        for pct_key in ("percentage", "min_percentage"):
            if alt.get(pct_key) is not None:
                pct = float(alt[pct_key])
                # min_percentage viene en 0-100 (ej 20); percentage en 0-1 (ej 0.15) -> normalizar a %
                percentages.add(round(pct * 100 if pct <= 1 else pct, 2))
    return {"dates": dates, "amounts": amounts, "percentages": percentages}


def check_hallucination(response_text: str, eligible_alternatives: list) -> dict:
    """Escanea la respuesta del LLM buscando fechas (`YYYY-MM-DD`), montos (`$123.45`)
    y porcentajes (`20%`) que NO estén dentro de las alternativas autorizadas para
    este cliente. Es el chequeo que alimenta `conversations_log.llm_hallucination_flag`
    (BA_A_Tiempo_Propuesta_v2.md §4.2) -- una métrica de seguridad para el jurado,
    idealmente en 0% salvo el caso adversarial de prueba (CV-G10).

    No detecta alucinaciones semánticas ("sin intereses" sin cifra) por regex solas;
    ver `_KEYWORD_RED_FLAGS` para esas.
    """
    authorized = _authorized_values(eligible_alternatives)
    mentioned_dates = set(_DATE_RE.findall(response_text))
    mentioned_amounts = {round(float(a.replace(",", "")), 2) for a in _AMOUNT_RE.findall(response_text)}
    mentioned_percentages = {round(float(p.replace(",", ".")), 2) for p in _PERCENTAGE_RE.findall(response_text)}

    unauthorized = {
        "dates": sorted(mentioned_dates - authorized["dates"]),
        "amounts": sorted(mentioned_amounts - authorized["amounts"]),
        "percentages": sorted(mentioned_percentages - authorized["percentages"]),
    }
    keyword_hits = [kw for kw in _KEYWORD_RED_FLAGS if kw in response_text.lower()]

    flagged = any(unauthorized.values()) or bool(keyword_hits)
    return {"llm_hallucination_flag": flagged, "unauthorized_mentions": unauthorized,
            "unauthorized_keywords": keyword_hits}


_KEYWORD_RED_FLAGS = ["sin intereses", "sin recargo adicional", "te lo condono", "gratis",
                      "descuento especial", "promoción"]


# ---------------------------------------------------------------------------
# Sustituto determinista del LLM (SOLO para golden conversations y tests -- no es producción)
# ---------------------------------------------------------------------------

def _mock_llm_response(customer_message: str, eligible_alternatives: list) -> dict:
    """Clasifica barrera/tono por palabras clave. Reemplaza esto por una llamada
    real a un LLM (temperature=0, ver RECOMMENDED_LLM_PARAMS) cuando haya API key;
    el resto del pipeline (prompt, guardrail, categorías) no cambia."""
    text = customer_message.lower()
    if any(w in text for w in ["no me escriban", "dejen de", "no quiero que me contacten"]):
        barrier = "REFUSAL"
    elif any(w in text for w in ["ya pagué", "ya pague", "ya cancelé"]):
        barrier = "ALREADY_PAID"
    elif any(w in text for w in ["no es lo que", "no reconozco", "cargo indebido"]):
        barrier = "DISPUTE"
    elif any(w in text for w in ["no me deja", "error en la app", "no pude pagar"]):
        barrier = "TECHNICAL"
    elif any(w in text for w in ["no me alcanza", "no tengo", "este mes no puedo"]):
        barrier = "LIQUIDITY"
    elif any(w in text for w in ["me pagan hasta", "cobro el", "hasta que me paguen"]):
        barrier = "DATE_MISMATCH"
    elif any(w in text for w in ["se me olvidó", "no me acordaba", "se me pasó"]):
        barrier = "FORGOT"
    else:
        barrier = "OTHER"

    if any(w in text for w in ["groser", "harto", "dejen de molestar", "denunciar"]):
        tone = "HOSTILE"
    elif any(w in text for w in ["molesto", "otra vez", "ya les dije"]):
        tone = "TENSE"
    elif any(w in text for w in ["gracias", "claro", "perfecto", "de acuerdo"]):
        tone = "COOPERATIVE"
    else:
        tone = "NEUTRAL"

    return {"barrier_detected": barrier, "barrier_confidence": 0.9, "tone_overall": tone}


def call_llm(prompt: str, customer_message: str, eligible_alternatives: list,
             params: dict | None = None) -> dict:
    """Punto único de integración con un proveedor real. Hoy delega en el mock
    determinista (ver docstring del módulo); cuando se conecte un proveedor real,
    esta función debe llamarlo con `params or RECOMMENDED_LLM_PARAMS` (temperature=0)
    y pasar `prompt` como system prompt, sin cambiar la firma."""
    return _mock_llm_response(customer_message, eligible_alternatives)


if __name__ == "__main__":
    demo_alts = [{"alt_id": "ALT-PARTIAL", "type": "PARTIAL_PAYMENT", "min_percentage": 20, "min_amount": 40.0}]
    demo_score = {"situation": {"situation_hint": "S3", "low_digital_response": False, "flags": []},
                  "channel": {"channel_pref_model": "WHATSAPP"}}
    print(build_system_prompt(demo_score, demo_alts))
