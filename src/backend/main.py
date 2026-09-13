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
    return golden_customers_df[['customer_id', 'scenario']].to_dict(orient="records")

@app.post("/api/chat")
def chat(req: ChatRequest):
    groq_api_key = os.environ.get("GROQ_API_KEY")
    
    # 1. Run the banking logic for this specific customer
    try:
        score = score_customer(req.customer_id)
        alts = get_eligible_alternatives(score["risk"], score["profile"])
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # 2. Build the strict guardrail prompt
    system_prompt = build_system_prompt(score, alts)
    
    if not groq_api_key:
        # Fallback to local mock LLM
        from src.backend.conversation_engine import call_llm
        last_msg = req.history[-1].content if req.history else ""
        mock_res = call_llm(system_prompt, last_msg, alts)
        reply = f"(Modo Automático - Sin API Key Groq) Te entiendo. Según lo que dices, detecto que tu problema es: {mock_res['barrier_detected']}. El sistema te recomienda las siguientes opciones: {alts[0]['alt_id'] if alts else 'Hablar con un asesor'}."
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
