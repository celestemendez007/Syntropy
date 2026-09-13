"""
chat_state_machine.py — Fase 6: máquina de estados de la conversación.

Antes era genérica (no validaba nada, `barrier`/`selected_offer` eran strings libres).
Ahora aplica lo que el README marca como criterio de éxito del MVP: "el Policy Engine
bloquea condiciones inválidas aunque el usuario intente manipular al LLM (pruebas
adversariales)". Concretamente:
  - `barrier` se normaliza contra las categorías cerradas de `conversation_engine.py`
    (nunca deja pasar una categoría inventada).
  - Un tono HOSTILE, o una barrera DISPUTE / OTHER de baja confianza, escala a un
    humano automáticamente (`should_escalate`), sin depender de que el LLM "decida"
    escalar por su cuenta.
  - `OFFER_SELECTED` solo avanza el estado si el `alt_id` está en la lista YA resuelta
    por `policy_engine.get_eligible_alternatives` para este cliente -- si alguien (el
    LLM alucinando, o un usuario manipulando la llamada) pide algo fuera de esa lista,
    la transición se rechaza (`policy_result = REJECTED_NOT_ELIGIBLE`) y el estado NO
    avanza a CONFIRM. Esto es lo que hace que el Policy Engine bloquee de verdad, no
    solo en el prompt.
  - `check_llm_response` corre el guardrail anti-alucinación sobre cualquier texto que
    el LLM haya generado, y lo deja registrado para `conversations_log.llm_hallucination_flag`.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml"))
from risk_engine import get_risk_profile  # noqa: E402
from policy_engine import get_eligible_alternatives  # noqa: E402
from conversation_engine import BARRIER_CATEGORIES, TONE_CATEGORIES, should_escalate, check_hallucination  # noqa: E402


class ChatStateMachine:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.state = "START"
        self.barrier = None
        self.tone = None
        self.selected_alt = None
        self.policy_result = None
        self.hallucination_flags = []

        risk_profile = get_risk_profile(customer_id)
        self.eligible_alternatives = get_eligible_alternatives(customer_id, risk_profile)
        self._eligible_by_id = {a["alt_id"]: a for a in self.eligible_alternatives}

    def transition(self, action: str, data: dict = None):
        """
        Maneja la transición de estados de la conversación.
        """
        data = data or {}

        if self.state == "START" and action == "USER_REPLIES":
            self.state = "UNDERSTAND"

        elif self.state == "UNDERSTAND" and action == "BARRIER_IDENTIFIED":
            barrier = data.get("barrier")
            self.barrier = barrier if barrier in BARRIER_CATEGORIES else "OTHER"
            tone = data.get("tone")
            self.tone = tone if tone in TONE_CATEGORIES else self.tone

            if should_escalate(self.tone or "NEUTRAL", self.barrier, data.get("barrier_confidence", 1.0)):
                self.state = "ESCALATED_TO_HUMAN"
            else:
                self.state = "PRESENT_OPTIONS"

        elif self.state == "PRESENT_OPTIONS" and action == "OFFER_SELECTED":
            alt_id = data.get("offer_id")
            if alt_id in self._eligible_by_id:
                self.selected_alt = alt_id
                self.policy_result = "AUTHORIZED"
                self.state = "CONFIRM"
            else:
                # Guardrail real: nunca avanza con una alternativa que el Policy Engine
                # no resolvió como elegible para este cliente, sin importar quién la pidió.
                self.policy_result = "REJECTED_NOT_ELIGIBLE"

        elif self.state == "CONFIRM" and action == "USER_CONFIRMS":
            self.state = "CLOSE"

        elif action == "ESCALATE":
            self.state = "ESCALATED_TO_HUMAN"

        return self.state

    def check_llm_response(self, response_text: str) -> dict:
        """Corre el guardrail anti-alucinación (montos/fechas fuera de lo autorizado)
        sobre un texto generado por el LLM en esta conversación."""
        result = check_hallucination(response_text, self.eligible_alternatives)
        if result["llm_hallucination_flag"]:
            self.hallucination_flags.append(response_text)
        return result

    def get_conversation_result(self) -> dict:
        selected = self._eligible_by_id.get(self.selected_alt)
        return {
            "state": self.state,
            "barrier": self.barrier,
            "tone_overall": self.tone,
            "selected_offer": self.selected_alt,
            "policy_result": self.policy_result,
            "result": selected["type"] if selected else None,
            "confirmed": self.state == "CLOSE",
            "escalation_triggered": self.state == "ESCALATED_TO_HUMAN",
            "llm_hallucination_flag": bool(self.hallucination_flags),
        }
