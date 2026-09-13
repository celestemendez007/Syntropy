"""
build_synthetic_conversations.py — Fase 6 (P1 dashboard) / Fase 7 (feedback loop).

Genera `interventions_log.csv` (una fila por decisión de NBA, incluyendo NO_CONTACT --
esa es la métrica "sabe cuándo no molestar") y `conversations_log.csv` (una fila por
conversación, solo cuando `nba.should_contact = true`), corriendo el sistema real
(risk_engine + nba_engine + policy_engine) sobre una muestra de clientes sintéticos.

SUPUESTO DE DEMO explícito y el más importante de este archivo: no hay conversaciones
reales todavía (no hay LLM conectado, ver conversation_engine.py), así que la
aceptación de cada alternativa se simula con una probabilidad "verdadera" fija por
`alt_id` (`TRUE_ACCEPTANCE_PROB` abajo) modulada por el tono de la conversación. Esto
NO es una medición real de qué alternativa funciona mejor -- es un dataset con señal
suficiente y realista para poder demostrar que la Fase 7 (tabla de prioridades con
suavizado bayesiano) efectivamente reordena las alternativas cuando hay evidencia.
En producción esta tabla se llenaría con resultados reales, no con esta simulación.
"""
import os
import sys
import csv
import numpy as np
import pandas as pd

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_BASE_DIR, "..", "ml"))
from risk_engine import get_risk_profile, load_dataset  # noqa: E402
from policy_engine import get_eligible_alternatives  # noqa: E402
from nba_engine import get_next_best_action  # noqa: E402
from conversation_engine import BARRIER_CATEGORIES, TONE_CATEGORIES, SITUATION_TO_EXPECTED_BARRIER  # noqa: E402

_OUT_DIR = os.path.join(_BASE_DIR, "..", "..", "research", "ba_a_tiempo", "data", "interactions")
CONVERSATIONS_PATH = os.path.join(_OUT_DIR, "conversations_log.csv")
INTERVENTIONS_PATH = os.path.join(_OUT_DIR, "interventions_log.csv")

SEED = 7

# SUPUESTO DE DEMO: probabilidad "verdadera" de que el cliente acepte cada alternativa,
# antes de modular por tono. Elegidas para que el orden tenga sentido de negocio (pedir
# poco y ya tener el dinero es más fácil de aceptar que comprometerse a un ahorro futuro
# o a una reestructuración humana) -- así el feedback loop tiene algo real que aprender.
TRUE_ACCEPTANCE_PROB = {
    "ALT-REMINDER-PAYLINK": 0.75,
    "ALT-DATE-SHIFT": 0.70,
    "ALT-GRACE-DAYS": 0.55,
    "ALT-PARTIAL": 0.60,
    "ALT-CHANNEL-SUPPORT": 0.50,
    "ALT-AUTOSAVE-PCT": 0.35,
    "ALT-PAYMENT-PLAN": 0.20,
}
TONE_ACCEPTANCE_MULTIPLIER = {"COOPERATIVE": 1.25, "NEUTRAL": 1.0, "TENSE": 0.55, "HOSTILE": 0.05}
TONE_POPULATION_MIX = {"COOPERATIVE": 0.55, "NEUTRAL": 0.30, "TENSE": 0.12, "HOSTILE": 0.03}
BARRIER_MATCH_RATE = 0.70  # 70% de las veces la barrera dicha coincide con situation_hint
PAID_ON_TIME_IF_ACCEPTED_PROB = 0.85

INTERVENTIONS_FIELDNAMES = ["intervention_id", "customer_id", "situation_hint", "low_digital_response",
                            "risk_level", "decision", "channel_used", "channel_source", "recommended_action",
                            "credit_product", "digital_capability", "needs_guided_help", "complex_case"]
CONVERSATIONS_FIELDNAMES = ["conversation_id", "intervention_id", "customer_id", "situation_hint", "channel",
                            "turns_total", "barrier_detected", "barrier_vs_situation_match", "tone_overall",
                            "escalation_triggered", "alternatives_offered", "alternative_accepted",
                            "final_outcome", "paid_on_time_after"]


def _sample_barrier(rng: np.random.Generator, situation_hint: str) -> str:
    expected = SITUATION_TO_EXPECTED_BARRIER.get(situation_hint)
    if expected and rng.random() < BARRIER_MATCH_RATE:
        return expected
    others = [b for b in BARRIER_CATEGORIES if b != expected]
    return rng.choice(others)


def _sample_tone(rng: np.random.Generator, action: str) -> str:
    if action == "HUMAN_ESCALATION":
        return "HOSTILE" if rng.random() < 0.6 else "TENSE"
    categories = list(TONE_POPULATION_MIX.keys())
    probs = list(TONE_POPULATION_MIX.values())
    return rng.choice(categories, p=probs)


def _turns_for_tone(rng: np.random.Generator, tone: str) -> int:
    ranges = {"COOPERATIVE": (2, 4), "NEUTRAL": (3, 6), "TENSE": (4, 8), "HOSTILE": (1, 3)}
    lo, hi = ranges[tone]
    return int(rng.integers(lo, hi + 1))


def _simulate_offer_acceptance(rng: np.random.Generator, eligible_alternatives: list, tone: str):
    """Recorre las alternativas elegibles en el orden dado y simula si el cliente
    acepta la primera que "le gusta" -- modela que el LLM las presenta en orden
    de prioridad (Fase 7) y el cliente no necesariamente evalúa todas."""
    multiplier = TONE_ACCEPTANCE_MULTIPLIER[tone]
    for alt in eligible_alternatives:
        base_p = TRUE_ACCEPTANCE_PROB.get(alt["alt_id"])
        if base_p is None:  # ALT-NONE u otras sin probabilidad definida
            continue
        p = min(0.97, base_p * multiplier)
        if rng.random() < p:
            return alt["alt_id"]
    return None


def generate(n_customers: int = 1800, seed: int = SEED) -> tuple:
    rng = np.random.default_rng(seed)
    dataset = load_dataset()
    sample_ids = rng.choice(dataset["customer_id"].values, size=min(n_customers, len(dataset)), replace=False)

    interventions, conversations = [], []
    for i, customer_id in enumerate(sample_ids):
        risk_profile = get_risk_profile(customer_id)
        nba = get_next_best_action(customer_id, risk_profile)
        intervention_id = f"IV-{i:06d}"

        interventions.append({
            "intervention_id": intervention_id, "customer_id": customer_id,
            "situation_hint": risk_profile["situation_hint"],
            "low_digital_response": risk_profile["low_digital_response"],
            "risk_level": risk_profile["risk_level"],
            "decision": "INTERVENE" if nba["intervene"] else "NO_CONTACT",
            "channel_used": nba["channel"], "channel_source": nba.get("channel_source", ""),
            "recommended_action": nba["action"],
            "credit_product": nba["credit_product"], "digital_capability": nba["digital_capability"],
            "needs_guided_help": nba["needs_guided_help"], "complex_case": nba["complex_case"],
        })

        if not nba["intervene"]:
            continue

        eligible = get_eligible_alternatives(customer_id, risk_profile)
        eligible = [a for a in eligible if a["alt_id"] != "ALT-NONE"]
        if nba["action"] != "HUMAN_ESCALATION":
            eligible = [a for a in eligible if not a.get("human_only")]

        situation_hint = risk_profile["situation_hint"]
        barrier = _sample_barrier(rng, situation_hint)
        tone = _sample_tone(rng, nba["action"])
        turns = _turns_for_tone(rng, tone)
        escalation = tone == "HOSTILE" or nba["action"] == "HUMAN_ESCALATION"

        accepted = None if escalation else _simulate_offer_acceptance(rng, eligible, tone)
        if accepted:
            final_outcome = "ACCEPTED"
            paid_on_time = bool(rng.random() < PAID_ON_TIME_IF_ACCEPTED_PROB)
        elif escalation:
            final_outcome = "ESCALATED"
            paid_on_time = False
        else:
            final_outcome = "REJECTED" if eligible else "NO_RESPONSE"
            paid_on_time = False

        conversations.append({
            "conversation_id": f"CV-{i:06d}", "intervention_id": intervention_id, "customer_id": customer_id,
            "situation_hint": situation_hint, "channel": nba["channel"], "turns_total": turns,
            "barrier_detected": barrier,
            "barrier_vs_situation_match": SITUATION_TO_EXPECTED_BARRIER.get(situation_hint) == barrier,
            "tone_overall": tone, "escalation_triggered": escalation,
            "alternatives_offered": ";".join(a["alt_id"] for a in eligible),
            "alternative_accepted": accepted or "",
            "final_outcome": final_outcome, "paid_on_time_after": paid_on_time,
        })

    return interventions, conversations


def write_csvs(n_customers: int = 1800, seed: int = SEED) -> tuple:
    interventions, conversations = generate(n_customers, seed)
    os.makedirs(_OUT_DIR, exist_ok=True)
    with open(INTERVENTIONS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INTERVENTIONS_FIELDNAMES)
        writer.writeheader()
        writer.writerows(interventions)
    with open(CONVERSATIONS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CONVERSATIONS_FIELDNAMES)
        writer.writeheader()
        writer.writerows(conversations)
    return INTERVENTIONS_PATH, CONVERSATIONS_PATH


if __name__ == "__main__":
    iv_path, cv_path = write_csvs()
    iv_df, cv_df = pd.read_csv(iv_path), pd.read_csv(cv_path)
    print(f"interventions_log: {len(iv_df)} filas ({(iv_df['decision'] == 'NO_CONTACT').mean() * 100:.1f}% NO_CONTACT) -> {iv_path}")
    print(f"conversations_log: {len(cv_df)} filas -> {cv_path}")
    print(cv_df["tone_overall"].value_counts(normalize=True).round(3))
