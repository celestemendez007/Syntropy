import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from conversation_engine import (BARRIER_CATEGORIES, TONE_CATEGORIES, RECOMMENDED_LLM_PARAMS,
                                  build_system_prompt, check_hallucination, should_escalate, call_llm)

DEMO_SCORE = {"situation": {"situation_hint": "S3", "low_digital_response": False, "flags": []},
              "channel": {"channel_pref_model": "WHATSAPP"}}
DEMO_ALTS = [{"alt_id": "ALT-PARTIAL", "type": "PARTIAL_PAYMENT", "min_percentage": 20, "min_amount": 40.0}]


def test_categories_match_design():
    assert BARRIER_CATEGORIES == ["FORGOT", "DATE_MISMATCH", "LIQUIDITY", "TECHNICAL", "DISPUTE",
                                   "REFUSAL", "ALREADY_PAID", "OTHER"]
    assert TONE_CATEGORIES == ["COOPERATIVE", "NEUTRAL", "TENSE", "HOSTILE"]


def test_recommended_temperature_is_zero():
    """El diseño pide explícitamente temperature=0 para tareas de clasificación
    cerrada y parafraseo de montos/fechas ya resueltos -- no debe quedar como
    valor por defecto sin decisión explícita."""
    assert RECOMMENDED_LLM_PARAMS["temperature"] == 0


def test_prompt_includes_closed_categories_and_resolved_alternatives():
    prompt = build_system_prompt(DEMO_SCORE, DEMO_ALTS)
    for barrier in BARRIER_CATEGORIES:
        assert barrier in prompt
    for tone in TONE_CATEGORIES:
        assert tone in prompt
    assert "ALT-PARTIAL" in prompt
    assert "40.0" in prompt


def test_prompt_never_includes_full_catalog_alt_ids_not_eligible():
    """El LLM nunca debe ver alt_ids del catálogo completo que no fueron
    resueltos como elegibles para este cliente."""
    prompt = build_system_prompt(DEMO_SCORE, DEMO_ALTS)
    assert "ALT-DATE-SHIFT" not in prompt  # no es parte de las alternativas resueltas para este demo


def test_prompt_asks_for_income_date_when_unknown():
    score = {"situation": {"situation_hint": "S0", "low_digital_response": False,
                            "flags": ["income_date_unknown"]},
             "channel": {"channel_pref_model": "WHATSAPP"}}
    prompt = build_system_prompt(score, [])
    assert "pregúntasela" in prompt or "no se conoce la fecha" in prompt


def test_hallucination_guardrail_passes_clean_response():
    clean = "Puedes abonar un mínimo de $40.00 (20%) y diferimos el resto."
    result = check_hallucination(clean, DEMO_ALTS)
    assert result["llm_hallucination_flag"] is False


def test_hallucination_guardrail_catches_unauthorized_date_and_keyword():
    bad = "Te lo dejo sin intereses, y si prefieres el 2026-12-01 no hay problema."
    result = check_hallucination(bad, DEMO_ALTS)
    assert result["llm_hallucination_flag"] is True
    assert "2026-12-01" in result["unauthorized_mentions"]["dates"]
    assert "sin intereses" in result["unauthorized_keywords"]


def test_hallucination_guardrail_catches_unauthorized_amount():
    bad = "Puedes pagar solo $10.00 y quedamos a mano."
    result = check_hallucination(bad, DEMO_ALTS)
    assert result["llm_hallucination_flag"] is True
    assert 10.0 in result["unauthorized_mentions"]["amounts"]


def test_should_escalate_on_hostile_tone():
    assert should_escalate("HOSTILE", "LIQUIDITY") is True


def test_should_escalate_on_dispute_barrier():
    assert should_escalate("NEUTRAL", "DISPUTE") is True


def test_should_not_escalate_on_cooperative_forgot():
    assert should_escalate("COOPERATIVE", "FORGOT") is False


def test_call_llm_returns_only_closed_categories():
    result = call_llm("system prompt", "este mes no puedo completar", DEMO_ALTS)
    assert result["barrier_detected"] in BARRIER_CATEGORIES
    assert result["tone_overall"] in TONE_CATEGORIES
