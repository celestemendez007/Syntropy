import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from score_customer import score_customer

CONTRACT_TOP_KEYS = {"customer_id", "snapshot_date", "days_to_due", "gates", "risk", "situation",
                      "channel", "timing", "nba", "policy_context", "meta"}


def test_contract_has_all_top_level_sections():
    result = score_customer("C00001")
    assert CONTRACT_TOP_KEYS <= set(result.keys())


def test_risk_section_matches_risk_engine_contract():
    result = score_customer("C00001")
    risk = result["risk"]
    assert 0 <= risk["risk_score"] <= 1
    assert risk["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert isinstance(risk["anomaly_flag"], bool)
    assert 0 <= risk["risk_prob_lr"] <= 1


def test_channel_always_resolves_and_never_leaves_customer_without_channel():
    result = score_customer("GOLD-G09")
    assert result["channel"]["channel_pref_model"] in {"UNDETERMINED", "APP_PUSH", "SMS", "WHATSAPP", "CALL"}
    # G09 (baja respuesta digital) debe activar NBA -> CHANNEL_SWITCH con algún canal real
    assert result["nba"]["recommended_action"] == "CHANNEL_SWITCH"


def test_channel_used_is_never_undetermined_even_when_model_is():
    """Regresión: `channel_pref_model` puede ser UNDETERMINED (baja confianza),
    pero `channel_used` -- lo que un consumidor real necesita para saber a qué
    canal escribirle -- siempre debe ser uno de los cuatro canales reales."""
    result = score_customer("GOLD-G09")
    assert result["channel"]["channel_pref_model"] == "UNDETERMINED"
    assert result["channel"]["channel_used"] in {"APP_PUSH", "SMS", "WHATSAPP", "CALL"}


def test_golden_g01_stable_produces_no_offer_hint():
    result = score_customer("GOLD-G01")
    assert result["nba"]["should_contact"] is False
    assert result["policy_context"]["eligible_alternatives_hint"] == ["ALT-NONE"]


def test_golden_g07_liquidity_pressure_produces_partial_hint():
    result = score_customer("GOLD-G07")
    assert result["nba"]["should_contact"] is True
    assert "ALT-PARTIAL" in result["policy_context"]["eligible_alternatives_hint"]


def test_unknown_customer_returns_error_not_crash():
    result = score_customer("NO_EXISTE_9999")
    assert result["error"] == "CUSTOMER_NOT_FOUND"


def test_meta_has_model_version_and_timestamp():
    result = score_customer("C00001")
    assert result["meta"]["model_version"]
    assert "T" in result["meta"]["scored_at"]  # ISO 8601
