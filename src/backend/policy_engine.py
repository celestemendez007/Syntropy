import json
import os
from datetime import datetime, timedelta

import pandas as pd

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATASET_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "dataset.csv")
_GOLDEN_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "golden_customers.csv")

# SUPUESTO DE DEMO: `remaining_installments` está en el diseño (BA_A_Tiempo_Propuesta_v2.md §6)
# pero el generador sintético (research/ba_a_tiempo/ba_a_tiempo/generator.py) no lo produce
# todavía (quedó como columna P2/opcional, nunca implementada). Se asume un plazo restante fijo
# para poder calcular ALT-AUTOSAVE-PCT sin bloquear la Fase 5; no confundir con un dato real.
ASSUMED_REMAINING_INSTALLMENTS = 12

_dataset_cache = None
_golden_cache = None


def load_policies():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    policy_path = os.path.join(base_dir, 'policies.json')
    with open(policy_path, 'r') as f:
        return json.load(f)


def load_alternatives_catalog():
    catalog_path = os.path.join(_BASE_DIR, "alternatives_catalog.json")
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_customer_row(customer_id: str):
    global _dataset_cache, _golden_cache
    if _dataset_cache is None:
        _dataset_cache = pd.read_csv(_DATASET_PATH)
    match = _dataset_cache[_dataset_cache["customer_id"] == customer_id]
    if not match.empty:
        return match.iloc[0]
    if _golden_cache is None:
        _golden_cache = pd.read_csv(_GOLDEN_PATH) if os.path.exists(_GOLDEN_PATH) else pd.DataFrame()
    if not _golden_cache.empty:
        match = _golden_cache[_golden_cache["customer_id"] == customer_id]
        if not match.empty:
            return match.iloc[0]
    return None

def get_allowed_offers(customer_id: str, risk_profile: dict) -> list:
    """
    Retorna las opciones válidas basadas en el riesgo.
    """
    offers = [{"id": "O1", "type": "PAY_NOW"}]
    
    if risk_profile.get("risk_level") in ["MEDIUM", "HIGH"]:
        # Permite extensión de acuerdo a policies.json (ej: 15 días max)
        policies = load_policies()
        max_days = policies.get("extension_max_days", 15)
        new_date = (datetime.now() + timedelta(days=max_days)).strftime("%Y-%m-%d")
        
        offers.append({
            "id": "O2",
            "type": "PROMISE_TO_PAY",
            "date": new_date
        })
        
        offers.append({
            "id": "O3",
            "type": "PARTIAL_PAYMENT",
            "min_percentage": policies.get("min_partial_payment_percentage", 20)
        })
    
    offers.append({"id": "O4", "type": "HUMAN_CALLBACK"})
    return offers

def validate_offer(offer_type: str, params: dict) -> bool:
    """
    Asegura que el agente no prometa cosas fuera de política.
    """
    policies = load_policies()
    
    if offer_type == "PROMISE_TO_PAY":
        requested_days = params.get("requested_days", 0)
        if requested_days > policies.get("extension_max_days", 15):
            return False
            
    if offer_type == "PARTIAL_PAYMENT":
        percentage = params.get("percentage", 0)
        if percentage < policies.get("min_partial_payment_percentage", 20):
            return False
            
    if offer_type == "WAIVER" and not policies.get("allow_interest_waiver", False):
        return False
        
    return True

def register_simulated_commitment(customer_id: str, offer_id: str) -> dict:
    return {
        "status": "SUCCESS",
        "customer_id": customer_id,
        "selected_offer": offer_id,
        "policy_result": "AUTHORIZED"
    }


# ---------------------------------------------------------------------------
# Fase 5: catálogo de alternativas (alternatives_catalog.json + BA_A_Tiempo_Propuesta_v2.md §6)
#
# Reemplaza el diseño de "policy_context" de get_allowed_offers (arriba, O1-O4 genéricos)
# por elegibilidad concreta por situation_hint con parámetros YA resueltos (fechas
# reales, porcentajes reales), tal como exige el diseño: "el LLM recibe la lista de
# alt_id elegibles con sus parámetros ya resueltos [...] si no está en la lista, no existe".
# ---------------------------------------------------------------------------

def _eligible_reminder_paylink(ctx: dict, policies: dict) -> dict | None:
    if ctx["situation_hint"] == "S1" and ctx["balance_ratio"] >= 1:
        return {"alt_id": "ALT-REMINDER-PAYLINK", "type": "PAY_NOW"}
    return None


def _eligible_date_shift(ctx: dict, policies: dict) -> dict | None:
    if ctx["situation_hint"] != "S2":
        return None
    gap = ctx.get("income_due_gap_pos", 0)
    if not (1 <= gap <= 10):
        return None
    max_days = policies.get("extension_max_days", 15)
    shift_days = min(int(gap), max_days)
    new_date = (ctx["next_due_date"] + timedelta(days=shift_days)).strftime("%Y-%m-%d")
    return {"alt_id": "ALT-DATE-SHIFT", "type": "PROMISE_TO_PAY", "date": new_date}


def _eligible_grace_days(ctx: dict, policies: dict) -> dict | None:
    if ctx["situation_hint"] not in ("S1", "S2"):
        return None
    if ctx.get("payment_punctuality", 0) < 0.6:
        return None
    grace_days = min(3, policies.get("extension_max_days", 15))  # SUPUESTO DE DEMO
    new_date = (ctx["next_due_date"] + timedelta(days=grace_days)).strftime("%Y-%m-%d")
    return {"alt_id": "ALT-GRACE-DAYS", "type": "GRACE_PERIOD", "grace_days": grace_days, "date": new_date}


def _eligible_partial(ctx: dict, policies: dict) -> dict | None:
    if ctx["situation_hint"] != "S3":
        return None
    if not (0.3 <= ctx["balance_ratio"] < 1):
        return None
    if ctx.get("partial_payments_n", 0) > 2:
        return None
    min_pct = policies.get("min_partial_payment_percentage", 20)
    min_amount = round(ctx["installment_amount"] * min_pct / 100, 2)
    return {"alt_id": "ALT-PARTIAL", "type": "PARTIAL_PAYMENT", "min_percentage": min_pct, "min_amount": min_amount}


def _eligible_autosave(ctx: dict, policies: dict) -> dict | None:
    if ctx["situation_hint"] not in ("S1", "S2", "S3"):
        return None
    if ctx["income_hist_avg"] - ctx["expenses_hist_avg"] <= 0:
        return None
    months_left = max(ASSUMED_REMAINING_INSTALLMENTS, 1)
    pct = min(0.15, ctx["installment_amount"] / (ctx["income_hist_avg"] * months_left))
    pct = round(max(pct, 0.0), 4)
    return {"alt_id": "ALT-AUTOSAVE-PCT", "type": "AUTOSAVE_PCT", "percentage": pct,
            "assumed_remaining_installments": months_left}


def _eligible_payment_plan(ctx: dict, policies: dict) -> dict | None:
    if ctx["situation_hint"] != "S3":
        return None
    if ctx["balance_ratio"] < 0.3 or ctx.get("income_variation", 0) < -0.4:
        return {"alt_id": "ALT-PAYMENT-PLAN", "type": "HUMAN_RESTRUCTURING", "human_only": True}
    return None


def _eligible_channel_support(ctx: dict, policies: dict) -> dict | None:
    if ctx.get("failed_payment_attempts_30d", 0) >= 2 and ctx["balance_ratio"] >= 1:
        return {"alt_id": "ALT-CHANNEL-SUPPORT", "type": "TECHNICAL_SUPPORT"}
    return None


_ELIGIBILITY_RULES = [
    _eligible_reminder_paylink,
    _eligible_date_shift,
    _eligible_grace_days,
    _eligible_partial,
    _eligible_autosave,
    _eligible_payment_plan,
    _eligible_channel_support,
]


def get_eligible_alternatives(customer_id: str, risk_profile: dict) -> list:
    """Resuelve la lista de `alt_id` elegibles con parámetros concretos (fechas,
    porcentajes, montos) para un cliente, según `situation_hint` y su contexto
    financiero. Es la fuente de verdad para `policy_context.eligible_alternatives_hint`
    del contrato v2 (docs/contracts.md) -- el LLM (Fase 6) nunca ve el catálogo
    completo ni las condiciones, solo esta lista ya resuelta.

    Siempre incluye ALT-NONE si `situation_hint == S0` y ninguna otra alternativa
    aplicó (nada que ofrecer a un cliente estable).
    """
    row = _load_customer_row(customer_id)
    if row is None:
        return []

    policies = load_policies()
    next_due_date = pd.to_datetime(row.get("next_due_date"))
    if pd.isna(next_due_date):
        # Golden customers no siempre traen next_due_date (no son un ciclo real);
        # se ancla a snapshot_date para poder resolver fechas de todas formas.
        next_due_date = pd.to_datetime(row.get("snapshot_date"))
    ctx = {
        "situation_hint": risk_profile.get("situation_hint", "S0"),
        "balance_ratio": float(row.get("balance_ratio", 0)),
        "income_due_gap_pos": float(row.get("income_due_gap_pos", 0)),
        "payment_punctuality": float(row.get("payment_punctuality", 1.0)),
        "partial_payments_n": int(row.get("partial_payments_n", 0)),
        "installment_amount": float(row.get("installment_amount", 0)),
        "income_hist_avg": float(row.get("income_hist_avg", 0)),
        "expenses_hist_avg": float(row.get("expenses_hist_avg", 0)),
        "income_variation": float(row.get("income_variation", 0)),
        "failed_payment_attempts_30d": int(row.get("failed_payment_attempts_30d", 0)),
        "next_due_date": next_due_date,
    }

    eligible = [alt for rule in _ELIGIBILITY_RULES if (alt := rule(ctx, policies)) is not None]

    if ctx["situation_hint"] == "S0" and not eligible:
        eligible.append({"alt_id": "ALT-NONE", "type": "NO_OFFER"})

    return eligible
