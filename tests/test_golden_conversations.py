import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from build_golden_conversations import build_golden_conversations, write_golden_conversations_csv
from conversation_engine import BARRIER_CATEGORIES, TONE_CATEGORIES


@pytest.fixture(scope="module")
def golden():
    write_golden_conversations_csv()
    return build_golden_conversations()


def test_ten_golden_conversations():
    assert len(build_golden_conversations()) == 10


def test_all_barriers_and_tones_are_from_closed_categories(golden):
    for row in golden:
        assert row["barrier_detected"] in BARRIER_CATEGORIES
        assert row["tone_overall"] in TONE_CATEGORIES


def test_adversarial_case_flags_hallucination(golden):
    """CV-G10 es el caso de prueba deliberado: la respuesta menciona 'sin intereses'
    y una fecha no autorizada -- el guardrail debe detectarlo (métrica de seguridad
    para el jurado, ver BA_A_Tiempo_Propuesta_v2.md §9)."""
    cv10 = next(r for r in golden if r["conversation_id"] == "CV-G10")
    assert cv10["llm_hallucination_flag"] is True


def test_only_the_adversarial_case_flags_hallucination(golden):
    """Todas las demás conversaciones (las que respetan las alternativas
    autorizadas) deben quedar en 0% -- si esto falla, revisar si se agregó una
    alternativa nueva sin actualizar el transcript_mock correspondiente."""
    flagged = [r["conversation_id"] for r in golden if r["llm_hallucination_flag"]]
    assert flagged == ["CV-G10"]


def test_hostile_conversation_triggers_escalation(golden):
    cv06 = next(r for r in golden if r["conversation_id"] == "CV-G06")
    assert cv06["tone_overall"] == "HOSTILE"
    assert cv06["escalation_triggered"] is True


def test_already_paid_never_offers_alternatives(golden):
    cv07 = next(r for r in golden if r["conversation_id"] == "CV-G07")
    assert cv07["barrier_detected"] == "ALREADY_PAID"
    assert cv07["alternatives_offered"] == ""


def test_refusal_case_does_not_offer_alternatives(golden):
    cv09 = next(r for r in golden if r["conversation_id"] == "CV-G09")
    assert cv09["barrier_detected"] == "REFUSAL"
    assert cv09["result"] == "OPT_OUT"


def test_csv_file_written_and_loadable():
    path = write_golden_conversations_csv()
    df = pd.read_csv(path)
    assert len(df) == 10
    assert "llm_hallucination_flag" in df.columns
