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
