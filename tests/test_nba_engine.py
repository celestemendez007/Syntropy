import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/ml')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from risk_engine import get_risk_profile
from nba_engine import get_next_best_action


def _nba_for(customer_id):
    profile = get_risk_profile(customer_id)
    return profile, get_next_best_action(customer_id, profile)


def test_golden_g01_stable_no_contact():
    _, nba = _nba_for("GOLD-G01")
    assert nba["intervene"] is False
    assert nba["action"] == "NO_CONTACT"


def test_golden_g03_friction_simple_reminder():
    _, nba = _nba_for("GOLD-G03")
    assert nba["intervene"] is True
    assert nba["action"] == "SIMPLE_REMINDER"


def test_golden_g05_date_mismatch_offers_date_options():
    _, nba = _nba_for("GOLD-G05")
    assert nba["intervene"] is True
    assert nba["action"] == "DATE_OPTIONS"


def test_golden_g07_liquidity_pressure_empathetic():
    _, nba = _nba_for("GOLD-G07")
    assert nba["intervene"] is True
    assert nba["action"] == "EMPATHETIC_CONVERSATION"


def test_golden_g09_low_digital_response_switches_channel():
    """G09: baja respuesta digital debe forzar cambio de canal aunque la
    situación financiera de base parezca estable (v1 §9, orthogonal a S0-S3)."""
    _, nba = _nba_for("GOLD-G09")
    assert nba["intervene"] is True
    assert nba["action"] == "CHANNEL_SWITCH"


def test_golden_g10_anti_insistence_blocks_contact():
    """G10: contactado hace 2 días (< MIN_DAYS_BETWEEN_CONTACTS=3) -> no
    contactar todavía, es la regla anti-insistencia del diseño."""
    _, nba = _nba_for("GOLD-G10")
    assert nba["intervene"] is False
    assert nba["reason"] == "CONTACTED_TOO_RECENTLY"


def test_golden_g11_severe_liquidity_and_no_response_escalates_to_human():
    _, nba = _nba_for("GOLD-G11")
    assert nba["intervene"] is True
    assert nba["action"] == "HUMAN_ESCALATION"


def test_golden_g12_new_customer_no_contact():
    _, nba = _nba_for("GOLD-G12")
    assert nba["intervene"] is False


def test_unknown_customer_does_not_crash():
    profile = get_risk_profile("NO_EXISTE_9999")
    nba = get_next_best_action("NO_EXISTE_9999", profile)
    assert nba["intervene"] is False


def test_intervene_customer_always_has_a_real_channel():
    _, nba = _nba_for("GOLD-G07")
    assert nba["channel"] in {"APP_PUSH", "SMS", "WHATSAPP", "CALL"}


# --- Arquetipos de 3 capas: producto crediticio + capacidad digital ---

def test_golden_g13_low_digital_capability_gets_guided_help():
    """G13 (capacidad digital D3): debe recibir ayuda guiada paso a paso, no solo
    un cambio de canal -- son necesidades distintas (no sabe usar la app vs. no
    responde por el canal habitual)."""
    _, nba = _nba_for("GOLD-G13")
    assert nba["intervene"] is True
    assert nba["action"] == "GUIDED_APP_HELP"
    assert nba["needs_guided_help"] is True


def test_golden_g14_sensitive_product_escalates_at_lower_threshold():
    """G14: crédito con garantía hipotecaria + balance_ratio 0.45 -- NO escalaría
    con el umbral genérico (0.3), pero sí debe escalar porque el producto es
    sensible (umbral más bajo a propósito)."""
    _, nba = _nba_for("GOLD-G14")
    assert nba["intervene"] is True
    assert nba["action"] == "HUMAN_ESCALATION"
    assert nba["complex_case"] is True
    assert nba["human_support_recommended"] is True


def test_same_severity_does_not_escalate_on_non_sensitive_product():
    """Regresión de diseño: G07 tiene balance_ratio 0.4 (similar a G14) pero un
    producto NO sensible -- no debe escalar por el umbral bajo de G14."""
    _, nba = _nba_for("GOLD-G07")
    assert nba["action"] != "HUMAN_ESCALATION"


def test_every_customer_carries_credit_product_and_digital_capability():
    for gid in ["GOLD-G01", "GOLD-G13", "GOLD-G14"]:
        _, nba = _nba_for(gid)
        assert nba["credit_product"]
        assert nba["digital_capability"] in {"D1", "D2", "D3"}


def test_needs_guided_help_reflects_true_capability_even_when_blocked():
    """Regresión: `needs_guided_help` describe al cliente (su capacidad digital),
    no la decisión de contactarlo -- no debe quedar en False solo porque una
    compuerta (ej. fuera de la ventana de intervención) bloqueó el contacto."""
    from risk_engine import load_dataset
    df = load_dataset()
    d3_customer = df[df["digital_capability"] == "D3"].iloc[0]
    profile, nba = _nba_for(d3_customer["customer_id"])
    assert nba["digital_capability"] == "D3"
    assert nba["needs_guided_help"] is True  # sin importar si intervene es True o False
