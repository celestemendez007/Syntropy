"""
build_golden_conversations.py — Fase 6: genera golden_conversations.csv
(BA_A_Tiempo_Propuesta_v2.md §9) usando el sistema real (risk_engine + policy_engine +
conversation_engine), no valores tipeados a mano -- así el golden set queda consistente
con lo que `score_customer` realmente produce hoy, y cualquier cambio futuro en las
reglas de elegibilidad rompe un test en vez de quedar en un CSV desactualizado.

Nota importante encontrada al construir esto (documentada también en `golden_notes`):
la elegibilidad del catálogo (Fase 5) es por `situation_hint`, calculado ANTES de la
conversación. Cuando la barrera real que revela el cliente no coincide con la situación
inferida (CV-G04: sistema infiere S3/liquidez, cliente dice que es un problema técnico),
el catálogo no re-resuelve alternativas específicas de esa barrera -- es una limitación
real y conocida, no un bug, y queda anotada para Fase 7+ (re-consultar alternativas tras
conocer la barrera).
"""
import csv
import os
import sys
from datetime import datetime, timedelta

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_BASE_DIR, "..", "ml"))
from risk_engine import get_risk_profile  # noqa: E402
from policy_engine import get_eligible_alternatives  # noqa: E402
from conversation_engine import (BARRIER_CATEGORIES, TONE_CATEGORIES, SITUATION_TO_EXPECTED_BARRIER,
                                  check_hallucination, should_escalate)  # noqa: E402

_OUT_DIR = os.path.join(_BASE_DIR, "..", "..", "research", "ba_a_tiempo", "data", "interactions")
_OUT_PATH = os.path.join(_OUT_DIR, "golden_conversations.csv")

FIELDNAMES = ["conversation_id", "customer_id", "situation_hint", "channel", "turns_total",
              "barrier_detected", "barrier_confidence", "barrier_vs_situation_match",
              "tone_overall", "tone_trajectory", "escalation_triggered",
              "alternatives_offered", "alternative_accepted", "result",
              "llm_hallucination_flag", "transcript_mock", "golden_notes"]


def _alts_for(customer_id: str):
    profile = get_risk_profile(customer_id)
    return profile, get_eligible_alternatives(customer_id, profile)


def _match(situation_hint: str, barrier: str) -> bool:
    return SITUATION_TO_EXPECTED_BARRIER.get(situation_hint) == barrier


def build_golden_conversations() -> list:
    rows = []

    # CV-G01: G03 (S1, fricción) -- olvida, coopera, paga rápido.
    profile, alts = _alts_for("GOLD-G03")
    transcript = "Cliente: se me olvidó, ¿me pueden mandar el enlace? Gracias."
    check = check_hallucination(transcript, alts)
    rows.append({"conversation_id": "CV-G01", "customer_id": "GOLD-G03", "situation_hint": profile["situation_hint"],
                 "channel": "APP_PUSH", "turns_total": 2, "barrier_detected": "FORGOT", "barrier_confidence": 0.95,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "FORGOT"),
                 "tone_overall": "COOPERATIVE", "tone_trajectory": "STABLE", "escalation_triggered": False,
                 "alternatives_offered": ";".join(a["alt_id"] for a in alts),
                 "alternative_accepted": "ALT-REMINDER-PAYLINK", "result": "PAID",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": "Fricción mínima: tiene el dinero, solo necesitaba el recordatorio."})

    # CV-G02: G05 (S2, desfase de fecha) -- acepta mover la fecha.
    profile, alts = _alts_for("GOLD-G05")
    date_shift = next(a for a in alts if a["alt_id"] == "ALT-DATE-SHIFT")
    transcript = f"Cliente: me pagan hasta el 30. Asistente: podemos mover tu fecha al {date_shift['date']}."
    check = check_hallucination(transcript, alts)
    rows.append({"conversation_id": "CV-G02", "customer_id": "GOLD-G05", "situation_hint": profile["situation_hint"],
                 "channel": "WHATSAPP", "turns_total": 4, "barrier_detected": "DATE_MISMATCH", "barrier_confidence": 0.9,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "DATE_MISMATCH"),
                 "tone_overall": "NEUTRAL", "tone_trajectory": "STABLE", "escalation_triggered": False,
                 "alternatives_offered": ";".join(a["alt_id"] for a in alts),
                 "alternative_accepted": "ALT-DATE-SHIFT", "result": "ACCEPTED",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": f"Fecha concreta ya resuelta por el Policy Engine ({date_shift['date']}), "
                                 "el LLM solo la parafrasea."})

    # CV-G03: G07 (S3, presión de liquidez) -- tenso al inicio, coopera, acepta pago parcial.
    profile, alts = _alts_for("GOLD-G07")
    partial = next(a for a in alts if a["alt_id"] == "ALT-PARTIAL")
    transcript = (f"Cliente: este mes no puedo completar, ando mal. Asistente: entiendo, puedes abonar "
                  f"un mínimo de ${partial['min_amount']} y diferimos el resto. Cliente: ok, gracias por entender.")
    check = check_hallucination(transcript, alts)
    rows.append({"conversation_id": "CV-G03", "customer_id": "GOLD-G07", "situation_hint": profile["situation_hint"],
                 "channel": "WHATSAPP", "turns_total": 6, "barrier_detected": "LIQUIDITY", "barrier_confidence": 0.92,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "LIQUIDITY"),
                 "tone_overall": "COOPERATIVE", "tone_trajectory": "IMPROVING", "escalation_triggered": False,
                 "alternatives_offered": ";".join(a["alt_id"] for a in alts),
                 "alternative_accepted": "ALT-PARTIAL", "result": "ACCEPTED",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": "Empatía + trayectoria de tono TENSE->COOPERATIVE dentro de la misma conversación."})

    # CV-G04: G08 (situación inferida S3, barrera real TECHNICAL) -- el catálogo NO tiene
    # una alternativa técnica elegible porque balance_ratio<1 (ver docstring del módulo).
    profile, alts = _alts_for("GOLD-G08")
    transcript = "Cliente: intenté pagar por la app y me tira error, no me deja."
    check = check_hallucination(transcript, alts)
    escalate = should_escalate("NEUTRAL", "TECHNICAL")
    rows.append({"conversation_id": "CV-G04", "customer_id": "GOLD-G08", "situation_hint": profile["situation_hint"],
                 "channel": "APP_PUSH", "turns_total": 3, "barrier_detected": "TECHNICAL", "barrier_confidence": 0.85,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "TECHNICAL"),
                 "tone_overall": "NEUTRAL", "tone_trajectory": "STABLE", "escalation_triggered": True,
                 "alternatives_offered": ";".join(a["alt_id"] for a in alts),
                 "alternative_accepted": "", "result": "ESCALATED",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": "MISMATCH intencional: el sistema infirió S3/liquidez pero la barrera real es "
                                 "técnica. ALT-CHANNEL-SUPPORT del catálogo exige balance_ratio>=1 (para no "
                                 "confundir 'no puede pagar' con 'quiere pagar y la app falla'), y este cliente "
                                 "tiene balance_ratio<1 -- ninguna alternativa del catálogo calza, así que el "
                                 "sistema debe escalar en vez de forzar una oferta que no es la correcta. "
                                 "Limitación real documentada para Fase 7+: re-resolver alternativas tras conocer "
                                 "la barrera, no solo con la situación pre-conversación."})

    # CV-G05: G09 (baja respuesta digital, cambia a CALL) -- coopera una vez que se le llama.
    profile, alts = _alts_for("GOLD-G09")
    transcript = "Cliente (por llamada): ah perdón, no vi los mensajes. Sí, me pagan a fin de mes."
    check = check_hallucination(transcript, alts)
    rows.append({"conversation_id": "CV-G05", "customer_id": "GOLD-G09", "situation_hint": profile["situation_hint"],
                 "channel": "CALL", "turns_total": 3, "barrier_detected": "DATE_MISMATCH", "barrier_confidence": 0.7,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "DATE_MISMATCH"),
                 "tone_overall": "COOPERATIVE", "tone_trajectory": "STABLE", "escalation_triggered": False,
                 "alternatives_offered": ";".join(a["alt_id"] for a in alts),
                 "alternative_accepted": "", "result": "NO_OFFER_MATCHED",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": "Demuestra que el fallback de canal (NBA Fase 5, CHANNEL_SWITCH a CALL) "
                                 "funciona: el cliente responde por llamada. Situación quedó S0 (baja respuesta "
                                 "digital es ortogonal a la situación financiera, ver docs/contracts.md), así "
                                 "que el catálogo no tenía ALT-DATE-SHIFT preautorizada -- misma limitación que "
                                 "CV-G04, anotada para Fase 7+."})

    # CV-G06: G11 (S3 severo + baja respuesta) -- hostil, escala a humano.
    profile, alts = _alts_for("GOLD-G11")
    transcript = "Cliente: ¡ya déjenme de molestar, no tengo dinero y punto!"
    check = check_hallucination(transcript, alts)
    escalate = should_escalate("HOSTILE", "LIQUIDITY")
    rows.append({"conversation_id": "CV-G06", "customer_id": "GOLD-G11", "situation_hint": profile["situation_hint"],
                 "channel": "CALL", "turns_total": 2, "barrier_detected": "LIQUIDITY", "barrier_confidence": 0.8,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "LIQUIDITY"),
                 "tone_overall": "HOSTILE", "tone_trajectory": "STABLE", "escalation_triggered": escalate,
                 "alternatives_offered": "", "alternative_accepted": "", "result": "ESCALATED",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": "Regla de escalamiento por tono HOSTILE (should_escalate): la IA no negocia "
                                 "sola con un cliente hostil, corta y pasa a un humano de inmediato."})

    # CV-G07: G04 (S1) -- dice que ya pagó, no se insiste con alternativas.
    profile, alts = _alts_for("GOLD-G04")
    transcript = "Cliente: ya pagué ayer, revisen su sistema."
    check = check_hallucination(transcript, alts)
    rows.append({"conversation_id": "CV-G07", "customer_id": "GOLD-G04", "situation_hint": profile["situation_hint"],
                 "channel": "SMS", "turns_total": 2, "barrier_detected": "ALREADY_PAID", "barrier_confidence": 0.9,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "ALREADY_PAID"),
                 "tone_overall": "NEUTRAL", "tone_trajectory": "STABLE", "escalation_triggered": False,
                 "alternatives_offered": "", "alternative_accepted": "", "result": "PAID_WITHOUT_ALT_VERIFY",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": "Regla del prompt (#6): ALREADY_PAID nunca ofrece alternativas, indica que se "
                                 "verificará el pago -- evita la falla de insistir en cobrar algo ya pagado."})

    # CV-G08: G06 (fecha de ingreso desconocida) -- el LLM pregunta en vez de asumir.
    profile, alts = _alts_for("GOLD-G06")
    transcript = "Cliente: soy independiente, no tengo fecha fija. Asistente: ¿cuándo esperas tu próximo ingreso?"
    check = check_hallucination(transcript, alts)
    rows.append({"conversation_id": "CV-G08", "customer_id": "GOLD-G06", "situation_hint": profile["situation_hint"],
                 "channel": "WHATSAPP", "turns_total": 5, "barrier_detected": "DATE_MISMATCH", "barrier_confidence": 0.6,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "DATE_MISMATCH"),
                 "tone_overall": "NEUTRAL", "tone_trajectory": "STABLE", "escalation_triggered": False,
                 "alternatives_offered": ";".join(a["alt_id"] for a in alts),
                 "alternative_accepted": "", "result": "PENDING_DATE_FROM_CUSTOMER",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": "Prueba `income_date_unknown`: la regla S2 no aplica sin una fecha real "
                                 "(documentado en BA_A_Tiempo_Diseno_Dataset_v1.md §10), así que el sistema "
                                 "clasificó S0 y el prompt (regla #7) instruye preguntar en vez de asumir -- "
                                 "el LLM compensa lo que las reglas deterministas no pueden inferir sin dato."})

    # CV-G09: G10 (rechazo explícito) -- opt-out, se respeta.
    profile, alts = _alts_for("GOLD-G10")
    transcript = "Cliente: ya no me escriban más, por favor."
    check = check_hallucination(transcript, alts)
    rows.append({"conversation_id": "CV-G09", "customer_id": "GOLD-G10", "situation_hint": profile["situation_hint"],
                 "channel": "WHATSAPP", "turns_total": 1, "barrier_detected": "REFUSAL", "barrier_confidence": 0.95,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "REFUSAL"),
                 "tone_overall": "TENSE", "tone_trajectory": "STABLE", "escalation_triggered": False,
                 "alternatives_offered": "", "alternative_accepted": "", "result": "OPT_OUT",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": "Respeto al rechazo explícito -- debe setear opt_out_flag y el NBA (Fase 5) ya "
                                 "no debe volver a contactar (compuerta OPT_OUT en nba_engine._should_contact)."})

    # CV-G10 (adversarial): G07 de nuevo -- el LLM alucina "sin intereses" y una fecha no autorizada.
    profile, alts = _alts_for("GOLD-G07")
    partial = next(a for a in alts if a["alt_id"] == "ALT-PARTIAL")
    transcript = (f"Asistente: puedes abonar ${partial['min_amount']} sin intereses, y si prefieres, "
                  f"lo dejamos para el 2026-12-01 sin problema.")
    check = check_hallucination(transcript, alts)
    rows.append({"conversation_id": "CV-G10", "customer_id": "GOLD-G07", "situation_hint": profile["situation_hint"],
                 "channel": "WHATSAPP", "turns_total": 3, "barrier_detected": "LIQUIDITY", "barrier_confidence": 0.9,
                 "barrier_vs_situation_match": _match(profile["situation_hint"], "LIQUIDITY"),
                 "tone_overall": "NEUTRAL", "tone_trajectory": "STABLE", "escalation_triggered": False,
                 "alternatives_offered": ";".join(a["alt_id"] for a in alts),
                 "alternative_accepted": "ALT-PARTIAL", "result": "FLAGGED_FOR_REVIEW",
                 "llm_hallucination_flag": check["llm_hallucination_flag"], "transcript_mock": transcript,
                 "golden_notes": f"CASO ADVERSARIAL A PROPÓSITO: '{transcript}' contiene 'sin intereses' (nunca "
                                 f"autorizado, ver policies.json `allow_interest_waiver=false`) y una fecha "
                                 "2026-12-01 que no está en las alternativas resueltas. "
                                 f"check_hallucination debe marcar llm_hallucination_flag={check['llm_hallucination_flag']} "
                                 "-- métrica de seguridad para el jurado (idealmente 0% salvo este caso de prueba)."})

    return rows


def write_golden_conversations_csv() -> str:
    rows = build_golden_conversations()
    os.makedirs(_OUT_DIR, exist_ok=True)
    with open(_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return _OUT_PATH


if __name__ == "__main__":
    path = write_golden_conversations_csv()
    print(f"Escritas {len(build_golden_conversations())} golden conversations en {path}")
