"""
nba_engine.py — Next Best Action real (Fase 5, BA_A_Tiempo_Diseno_Dataset_v1.md §P
y BA_A_Tiempo_Propuesta_v2.md §7-8; arquetipos de 3 capas post-Fase 8).

Todo determinista (reglas), nada de ML aquí -- el riesgo viene de risk_engine.py
(Fases 2-3) y el canal/momento de channel_timing_engine.py (Fase 4). Este módulo
decide:

  1. `should_contact` (compuertas, v1 §P): no si ya pagó, no si pidió no ser
     contactado, no si se le contactó muy seguido, no si low_digital_response
     "todavía" (regla anti-insistencia G10), no si el riesgo es bajo y no hay
     anomalía, no fuera de la ventana de intervención (1-10 días antes del
     vencimiento).
  2. `recommended_action`: mapeo de `situation_hint` + `low_digital_response`
     (+ severidad para escalamiento a humano, ver G11) -- ahora también con:
       - `digital_capability` (D1/D2/D3): un D3 necesita guía paso a paso dentro
         de la app (`GUIDED_APP_HELP`), no solo un cambio de canal (ver G13).
       - `credit_product`: productos sensibles (garantía real, vivienda, vehículo)
         bajan el umbral de escalamiento a humano -- un error de negociación
         automática pesa más en esos productos (ver G14).
  3. `channel`/`scheduled_for`: delega en channel_timing_engine (Fase 4).
  4. `nba_reason`: plantilla legible desde `top_factors`.

El arquetipo completo de un cliente (para NBA, Policy Engine y el prompt del LLM)
es la combinación de estas tres capas -- p. ej. "crédito de vehículo + desfase de
fecha + capacidad digital D1" -- nunca una sola dimensión aislada.
"""
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml"))
from channel_timing_engine import get_channel_and_timing  # noqa: E402

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATASET_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "dataset.csv")
_GOLDEN_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "golden_customers.csv")
_CONTACTS_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "contacts_log.csv")

CONTACT_CAP_7D = 2
MIN_DAYS_BETWEEN_CONTACTS = 3
INTERVENTION_WINDOW = (1, 15)
ESCALATION_FAILED_ATTEMPTS_MIN = 3
ESCALATION_BALANCE_RATIO_MAX = 0.3

# Arquetipos de 3 capas (post-Fase 8, ver config.py de research/ba_a_tiempo para la
# fuente de verdad de estas listas -- duplicadas aquí a propósito, mismo patrón que
# IF_FEATURES/LR_FEATURES en risk_engine.py: producción no importa desde research/).
SENSITIVE_CREDIT_PRODUCTS = {"PERSONAL_LOAN_MORTGAGE_BACKED", "HOME_LOAN", "VEHICLE_LOAN"}
REVOLVING_CREDIT_PRODUCTS = {"CREDICHEQUE", "OVERDRAFT_ELITE", "EXTRA_FINANCING", "SALARY_ADVANCE"}
# Umbral de escalamiento MÁS BAJO para productos sensibles: un error de negociación
# automática en una hipoteca o un vehículo pesa más que en un crédito personal chico.
SENSITIVE_ESCALATION_BALANCE_RATIO_MAX = 0.5
SENSITIVE_ESCALATION_FAILED_ATTEMPTS_MIN = 1

# Defaults para las compuertas tempranas (cliente no encontrado / no se debe contactar):
# no hay acción real que tomar, pero el contrato siempre debe traer estas llaves.
_DEFAULT_ARCHETYPE_FIELDS = {
    "credit_product": "PERSONAL_LOAN_PAYROLL_DEDUCTION", "digital_capability": "D1",
    "needs_guided_help": False, "human_support_recommended": False,
    "complex_case": False, "avoid_more_credit": False,
}

TOP_FACTOR_TEMPLATES = {
    "balance_ratio": "el saldo actual cubre poco de la cuota",
    "balance_vs_historical": "el saldo está muy por debajo de su propio histórico",
    "recent_balance_drop": "el saldo cayó rápido en las últimas dos semanas",
    "min_balance_ratio_30d": "tocó fondo en algún momento del último mes",
    "income_variation": "el ingreso reciente se desvía de su promedio histórico",
    "expense_variation_30d": "el gasto reciente subió respecto a su promedio",
    "spending_velocity_7d": "el ritmo de gasto de la última semana se aceleró",
    "failed_payment_attempts_30d": "hubo intentos de cobro fallidos este mes",
    "last_payment_delay_deviation": "el último pago se retrasó más de lo habitual para este cliente",
    "failed_attempts_deviation": "los intentos fallidos están por encima de su propia norma",
}

_dataset_cache = None
_golden_cache = None
_contacts_cache = None


def _load_dataset():
    global _dataset_cache
    if _dataset_cache is None:
        _dataset_cache = pd.read_csv(_DATASET_PATH)
    return _dataset_cache


def _load_golden():
    global _golden_cache
    if _golden_cache is None:
        _golden_cache = pd.read_csv(_GOLDEN_PATH) if os.path.exists(_GOLDEN_PATH) else pd.DataFrame()
    return _golden_cache


def _load_contacts():
    global _contacts_cache
    if _contacts_cache is None:
        _contacts_cache = pd.read_csv(_CONTACTS_PATH, parse_dates=["sent_at"]) if os.path.exists(_CONTACTS_PATH) \
            else pd.DataFrame(columns=["customer_id", "sent_at"])
    return _contacts_cache


def _find_customer_row(customer_id: str):
    dataset = _load_dataset()
    match = dataset[dataset["customer_id"] == customer_id]
    if not match.empty:
        return match.iloc[0]
    golden = _load_golden()
    if not golden.empty:
        match = golden[golden["customer_id"] == customer_id]
        if not match.empty:
            return match.iloc[0]
    return None


def _contacts_last_7d(customer_id: str, snapshot_date: str) -> int:
    contacts = _load_contacts()
    hist = contacts[contacts["customer_id"] == customer_id]
    if hist.empty:
        return 0
    cutoff = pd.to_datetime(snapshot_date) - timedelta(days=7)
    return int((hist["sent_at"] >= cutoff).sum())


def _should_contact(row: pd.Series, risk_profile: dict) -> tuple[bool, str | None]:
    """Devuelve (should_contact, motivo_de_bloqueo). Compuertas en orden (v1 §P)."""
    if bool(row.get("current_cycle_paid", False)):
        return False, "CURRENT_CYCLE_PAID"
    if bool(row.get("opt_out_flag", False)):
        return False, "OPT_OUT"

    days_since_last_contact = row.get("days_since_last_contact", 999)
    if pd.notna(days_since_last_contact) and days_since_last_contact < MIN_DAYS_BETWEEN_CONTACTS:
        return False, "CONTACTED_TOO_RECENTLY"

    snapshot_date = row.get("snapshot_date", datetime.now().strftime("%Y-%m-%d"))
    if _contacts_last_7d(row.get("customer_id"), snapshot_date) >= CONTACT_CAP_7D:
        return False, "CONTACT_CAP_7D_REACHED"

    days_to_due = row.get("days_to_due", 7)
    if pd.notna(days_to_due) and not (INTERVENTION_WINDOW[0] <= days_to_due <= INTERVENTION_WINDOW[1]):
        return False, "OUTSIDE_INTERVENTION_WINDOW"

    risk_level = risk_profile.get("risk_level", "LOW")
    anomaly_score = risk_profile.get("anomaly_score", 0.0)
    if risk_level == "LOW" and anomaly_score < 0.5:
        return False, "S0_STABLE"

    return True, None


def _is_complex_case(situation_hint: str, credit_product: str, failed_attempts_30d: int,
                      balance_ratio: float, low_digital_response: bool) -> bool:
    """S6 del arquetipo ampliado: caso que debe escalar a humano, ya sea por producto
    sensible con severidad moderada (umbral bajo a propósito, ver G14) o por la regla
    genérica ya existente (S3 + baja respuesta digital + severidad alta, ver G11)."""
    if situation_hint != "S3":
        return False
    if credit_product in SENSITIVE_CREDIT_PRODUCTS and (
            balance_ratio < SENSITIVE_ESCALATION_BALANCE_RATIO_MAX
            or failed_attempts_30d >= SENSITIVE_ESCALATION_FAILED_ATTEMPTS_MIN):
        return True
    if low_digital_response and (
            failed_attempts_30d >= ESCALATION_FAILED_ATTEMPTS_MIN or balance_ratio < ESCALATION_BALANCE_RATIO_MAX):
        return True
    return False


def _recommended_action(situation_hint: str, low_digital_response: bool, digital_capability: str,
                         credit_product: str, failed_attempts_30d: int, balance_ratio: float) -> tuple:
    """Devuelve (action, complex_case). Orden de prioridad: 1) seguridad (escalar si
    el caso es complejo) antes que 2) capacidad digital (D3 necesita guía, no solo
    otro canal) antes que 3) baja respuesta (cambiar canal) antes que 4) la acción
    base por situación financiera."""
    if _is_complex_case(situation_hint, credit_product, failed_attempts_30d, balance_ratio, low_digital_response):
        return "HUMAN_ESCALATION", True
    if digital_capability == "D3":
        return "GUIDED_APP_HELP", False
    if low_digital_response:
        return "CHANNEL_SWITCH", False
    action = {"S0": "NO_CONTACT", "S1": "SIMPLE_REMINDER", "S2": "DATE_OPTIONS",
              "S3": "EMPATHETIC_CONVERSATION"}.get(situation_hint, "SIMPLE_REMINDER")
    return action, False


def _nba_reason(top_factors: list, situation_hint: str, action: str) -> str:
    if action == "GUIDED_APP_HELP":
        return ("Puedo ayudarle a revisar su crédito, entender sus opciones y guiarle paso a paso "
                "dentro de la app. Si su caso necesita revisión especial o apoyo técnico más directo, "
                "puedo conectarle con un asesor para continuar.")
    if not top_factors:
        return "Sin factores destacados sobre su propio histórico; situación estable." if situation_hint == "S0" \
            else "Señal de riesgo sin un factor dominante claro."
    phrases = [TOP_FACTOR_TEMPLATES.get(f, f) for f in top_factors]
    return "Se observa que " + "; y ".join(phrases) + "."


def get_next_best_action(customer_id: str, risk_profile: dict) -> dict:
    """
    Decide la intervención completa para un cliente: compuertas, acción, canal y
    momento (delegado a channel_timing_engine), y una razón legible.

    `risk_profile` es la salida de `risk_engine.get_risk_profile` (Fases 2-3);
    este motor no vuelve a calcular riesgo, solo decide qué hacer con él.
    """
    row = _find_customer_row(customer_id)
    if row is None:
        return {**_DEFAULT_ARCHETYPE_FIELDS, "intervene": False, "channel": "NONE", "action": "NO_CONTACT",
                "reason": "CUSTOMER_NOT_FOUND", "nba_reason": "Cliente no encontrado."}

    should_contact, block_reason = _should_contact(row, risk_profile)
    if not should_contact:
        # `needs_guided_help` describe al cliente (su capacidad digital), no la decisión de
        # contactarlo -- debe reflejar digital_capability real aunque no se vaya a intervenir,
        # no quedar en el default solo porque las compuertas bloquearon el contacto.
        blocked_digital_capability = row.get("digital_capability", "D1")
        return {**_DEFAULT_ARCHETYPE_FIELDS, "intervene": False, "channel": "NONE", "action": "NO_CONTACT",
                "reason": block_reason, "nba_reason": "No se cumplen las condiciones para intervenir.",
                "credit_product": row.get("credit_product", "PERSONAL_LOAN_PAYROLL_DEDUCTION"),
                "digital_capability": blocked_digital_capability,
                "needs_guided_help": blocked_digital_capability == "D3"}

    situation_hint = risk_profile.get("situation_hint", "S0")
    low_digital_response = bool(risk_profile.get("low_digital_response", False))
    failed_attempts_30d = int(row.get("failed_payment_attempts_30d", 0))
    balance_ratio = float(row.get("balance_ratio", 1.0))
    digital_capability = row.get("digital_capability", "D1")
    credit_product = row.get("credit_product", "PERSONAL_LOAN_PAYROLL_DEDUCTION")

    action, complex_case = _recommended_action(situation_hint, low_digital_response, digital_capability,
                                                credit_product, failed_attempts_30d, balance_ratio)
    needs_guided_help = digital_capability == "D3"
    human_support_recommended = complex_case or (needs_guided_help and situation_hint == "S3")
    avoid_more_credit = credit_product in REVOLVING_CREDIT_PRODUCTS and situation_hint in ("S3",)

    channel_timing = get_channel_and_timing(customer_id)

    days_to_due = row.get("days_to_due", 7)
    scheduled_for = None
    if pd.notna(days_to_due):
        target_days_before = min(int(days_to_due), channel_timing["best_days_before_due"])
        start_hour = channel_timing["best_hour_window"].split("-")[0]
        scheduled_date = datetime.now() + timedelta(days=max(int(days_to_due) - target_days_before, 0))
        scheduled_for = f"{scheduled_date.strftime('%Y-%m-%d')}T{start_hour}"

    return {
        "intervene": action != "NO_CONTACT",
        "channel": channel_timing["channel_used"],
        "channel_source": channel_timing["channel_source"],
        "time_window": channel_timing["best_hour_window"],
        "scheduled_for": scheduled_for,
        "action": action,
        "reason": f"{situation_hint}{'_LOW_DIGITAL_RESPONSE' if low_digital_response else ''}",
        "nba_reason": _nba_reason(risk_profile.get("top_factors", []), situation_hint, action),
        "credit_product": credit_product,
        "digital_capability": digital_capability,
        "needs_guided_help": needs_guided_help,
        "human_support_recommended": human_support_recommended,
        "complex_case": complex_case,
        "avoid_more_credit": avoid_more_credit,
    }


if __name__ == "__main__":
    import json
    dataset = _load_dataset()
    sample_id = dataset["customer_id"].iloc[0]
    mock_risk = {"risk_level": "HIGH", "anomaly_score": 0.8, "situation_hint": "S3",
                 "low_digital_response": False, "top_factors": ["balance_ratio", "income_variation"]}
    print(json.dumps(get_next_best_action(sample_id, mock_risk), indent=2, ensure_ascii=False))
