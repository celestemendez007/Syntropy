import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from chat_state_machine import ChatStateMachine


def test_full_happy_path_reaches_close():
    """GOLD-G07 (S3) es elegible para ALT-PARTIAL -- flujo normal hasta CLOSE."""
    csm = ChatStateMachine("GOLD-G07")
    csm.transition("USER_REPLIES")
    csm.transition("BARRIER_IDENTIFIED", {"barrier": "LIQUIDITY", "tone": "NEUTRAL"})
    assert csm.state == "PRESENT_OPTIONS"
    csm.transition("OFFER_SELECTED", {"offer_id": "ALT-PARTIAL"})
    assert csm.state == "CONFIRM"
    csm.transition("USER_CONFIRMS")
    result = csm.get_conversation_result()
    assert result["state"] == "CLOSE"
    assert result["confirmed"] is True
    assert result["policy_result"] == "AUTHORIZED"
    assert result["selected_offer"] == "ALT-PARTIAL"


def test_adversarial_offer_selection_is_rejected_not_advanced():
    """Prueba adversarial explícita del README: aunque el LLM (o un cliente
    manipulando el flujo) pida una alternativa que el Policy Engine nunca
    resolvió como elegible para este cliente, el estado NO debe avanzar a
    CONFIRM -- el Policy Engine bloquea, no el prompt."""
    csm = ChatStateMachine("GOLD-G01")  # S0 estable -> solo ALT-NONE es elegible
    csm.transition("USER_REPLIES")
    csm.transition("BARRIER_IDENTIFIED", {"barrier": "LIQUIDITY", "tone": "NEUTRAL"})
    csm.transition("OFFER_SELECTED", {"offer_id": "ALT-PAYMENT-PLAN"})  # nunca autorizada para G01
    assert csm.state != "CONFIRM"
    result = csm.get_conversation_result()
    assert result["policy_result"] == "REJECTED_NOT_ELIGIBLE"
    assert result["confirmed"] is False


def test_unknown_barrier_string_normalizes_to_other():
    """Si algo (LLM, input externo) manda una categoría inventada, no debe
    colarse tal cual -- se normaliza a OTHER, que sí es una categoría cerrada."""
    csm = ChatStateMachine("GOLD-G07")
    csm.transition("USER_REPLIES")
    csm.transition("BARRIER_IDENTIFIED", {"barrier": "ESTA_CATEGORIA_NO_EXISTE", "tone": "NEUTRAL"})
    assert csm.barrier == "OTHER"


def test_hostile_tone_escalates_automatically():
    csm = ChatStateMachine("GOLD-G11")
    csm.transition("USER_REPLIES")
    csm.transition("BARRIER_IDENTIFIED", {"barrier": "LIQUIDITY", "tone": "HOSTILE"})
    assert csm.state == "ESCALATED_TO_HUMAN"
    result = csm.get_conversation_result()
    assert result["escalation_triggered"] is True


def test_dispute_barrier_escalates_automatically():
    csm = ChatStateMachine("GOLD-G01")
    csm.transition("USER_REPLIES")
    csm.transition("BARRIER_IDENTIFIED", {"barrier": "DISPUTE", "tone": "NEUTRAL"})
    assert csm.state == "ESCALATED_TO_HUMAN"


def test_llm_response_hallucination_is_tracked_in_result():
    csm = ChatStateMachine("GOLD-G07")
    csm.check_llm_response("Te lo dejo sin intereses.")
    result = csm.get_conversation_result()
    assert result["llm_hallucination_flag"] is True


def test_clean_llm_response_does_not_flag():
    csm = ChatStateMachine("GOLD-G07")
    partial = csm._eligible_by_id.get("ALT-PARTIAL")
    csm.check_llm_response(f"Puedes abonar ${partial['min_amount']} y diferimos el resto.")
    result = csm.get_conversation_result()
    assert result["llm_hallucination_flag"] is False
