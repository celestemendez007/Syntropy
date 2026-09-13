import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/ml')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from policy_engine import validate_offer, load_policies, load_alternatives_catalog, get_eligible_alternatives
from risk_engine import get_risk_profile

def test_load_policies():
    policies = load_policies()
    assert "extension_max_days" in policies

def test_validate_valid_extension():
    assert validate_offer("PROMISE_TO_PAY", {"requested_days": 10}) == True

def test_validate_invalid_extension():
    assert validate_offer("PROMISE_TO_PAY", {"requested_days": 100}) == False

def test_validate_invalid_partial_payment():
    assert validate_offer("PARTIAL_PAYMENT", {"percentage": 10}) == False

def test_validate_waiver_not_allowed():
    assert validate_offer("WAIVER", {}) == False


# --- Fase 5: catálogo de alternativas ---

def test_catalog_loads_all_alt_ids():
    catalog = load_alternatives_catalog()
    alt_ids = {a["alt_id"] for a in catalog["alternatives"]}
    assert alt_ids == {"ALT-REMINDER-PAYLINK", "ALT-DATE-SHIFT", "ALT-GRACE-DAYS", "ALT-PARTIAL",
                        "ALT-AUTOSAVE-PCT", "ALT-PAYMENT-PLAN", "ALT-CHANNEL-SUPPORT", "ALT-NONE"}


def test_stable_customer_gets_no_offer():
    """G01 (S0 estable) no debe recibir ninguna alternativa de cobranza real."""
    profile = get_risk_profile("GOLD-G01")
    alts = get_eligible_alternatives("GOLD-G01", profile)
    assert [a["alt_id"] for a in alts] == ["ALT-NONE"]


def test_g05_date_mismatch_gets_concrete_date_shift():
    """G05 (S2, el ingreso llega despues del vencimiento) debe recibir ALT-DATE-SHIFT
    con una fecha concreta ya resuelta, no una condicion abstracta."""
    profile = get_risk_profile("GOLD-G05")
    alts = get_eligible_alternatives("GOLD-G05", profile)
    date_shift = next((a for a in alts if a["alt_id"] == "ALT-DATE-SHIFT"), None)
    assert date_shift is not None
    assert "date" in date_shift and len(date_shift["date"]) == 10  # YYYY-MM-DD


def test_g07_liquidity_pressure_gets_partial_with_min_amount():
    """G07 (S3, balance_ratio 0.4) debe calificar para pago parcial con un monto
    minimo concreto, nunca un porcentaje sin resolver."""
    profile = get_risk_profile("GOLD-G07")
    alts = get_eligible_alternatives("GOLD-G07", profile)
    partial = next((a for a in alts if a["alt_id"] == "ALT-PARTIAL"), None)
    assert partial is not None
    assert partial["min_amount"] > 0


def test_g11_severe_case_offers_human_only_restructuring():
    profile = get_risk_profile("GOLD-G11")
    alts = get_eligible_alternatives("GOLD-G11", profile)
    plan = next((a for a in alts if a["alt_id"] == "ALT-PAYMENT-PLAN"), None)
    assert plan is not None
    assert plan["human_only"] is True


def test_unknown_customer_gets_no_alternatives():
    profile = get_risk_profile("NO_EXISTE_9999")
    assert get_eligible_alternatives("NO_EXISTE_9999", profile) == []


# --- Arquetipos de 3 capas: producto crediticio como contexto de elegibilidad ---

def test_g14_sensitive_product_moderate_severity_gets_human_restructuring():
    """G14 (garantía hipotecaria, balance_ratio 0.45) debe calificar para
    ALT-PAYMENT-PLAN aunque no cumpla el umbral genérico (0.3) -- el umbral es
    más bajo a propósito para productos sensibles."""
    profile = get_risk_profile("GOLD-G14")
    alts = get_eligible_alternatives("GOLD-G14", profile)
    plan = next((a for a in alts if a["alt_id"] == "ALT-PAYMENT-PLAN"), None)
    assert plan is not None
    assert plan["human_only"] is True


def test_revolving_product_under_liquidity_pressure_never_gets_autosave():
    """Arquetipo 5: no empujar más deuda (comprometer % de ingreso futuro) a un
    cliente que ya usa un producto rotativo y está en presión de liquidez."""
    import pandas as pd
    import os as _os
    dataset = pd.read_csv(_os.path.join(_os.path.dirname(__file__), "..", "data", "synthetic", "dataset.csv"))
    revolving = {"CREDICHEQUE", "OVERDRAFT_ELITE", "EXTRA_FINANCING", "SALARY_ADVANCE"}
    checked = 0
    for cid, product in zip(dataset["customer_id"], dataset["credit_product"]):
        if product not in revolving:
            continue
        profile = get_risk_profile(cid)
        if profile["situation_hint"] != "S3":
            continue
        alts = get_eligible_alternatives(cid, profile)
        alt_ids = {a["alt_id"] for a in alts}
        assert "ALT-AUTOSAVE-PCT" not in alt_ids
        assert "ALT-PAYMENT-PLAN" in alt_ids
        checked += 1
        if checked >= 5:
            break
    assert checked > 0, "no se encontraron clientes rotativos en S3 en esta corrida -- revisar la muestra"
