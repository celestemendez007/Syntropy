"""Constantes y SUPUESTOS DE DEMO. Todo aquí es ficticio y ajustable."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW, PROCESSED, GOLDEN, GENSTATE, INTER = (
    DATA / "raw_synthetic", DATA / "processed", DATA / "golden", DATA / "generator_state", DATA / "interactions")
MODELS, OUTPUTS = ROOT / "models", ROOT / "outputs"

SEED = 42
N_CUSTOMERS = 3000
SNAPSHOT_DATE = "2026-09-12"
HIST_CYCLES = 6                      # ventana histórica (SUPUESTO DE DEMO)
SITUATION_MIX = {"S0": 0.50, "S1": 0.15, "S2": 0.13, "S3": 0.12, "S4": 0.10}

IF_FEATURES = [
    "balance_vs_historical", "recent_balance_drop", "balance_ratio", "min_balance_ratio_30d",
    "income_variation", "expense_variation_30d", "spending_velocity_7d",
    "failed_payment_attempts_30d", "last_payment_delay_deviation", "failed_attempts_deviation",
]
IF_LOG1P = {"balance_vs_historical", "balance_ratio", "min_balance_ratio_30d", "spending_velocity_7d"}
IF_CONTAMINATION = 0.10

LR_FEATURES = [
    "balance_ratio", "projected_coverage", "balance_vs_historical", "income_variation",
    "expense_variation_30d", "payment_punctuality", "partial_payments_n",
    "failed_payment_attempts_30d", "income_due_gap_pos", "income_amount_cv", "external_debt_ratio_mock",
]
LR_LOG1P = {"balance_ratio", "projected_coverage", "balance_vs_historical"}
LABEL = "synthetic_late_payment_next_cycle"

RISK_W_LR, RISK_W_IF = 0.6, 0.4
RISK_CUTS = (0.35, 0.65)

CONTACT_CAP_7D = 2
MIN_DAYS_BETWEEN_CONTACTS = 3
INTERVENTION_WINDOW = (1, 10)
CHANNEL_CONF_MIN = 0.5
DEFAULT_CHANNEL = "CALL"
EXPLORATION_RATE = 0.10
CHANNELS = ["APP_PUSH", "SMS", "WHATSAPP", "CALL"]
POP_HOUR_WINDOW = {"SALARIED": "12:00-13:30", "BIWEEKLY": "12:00-13:30",
                   "INDEPENDENT": "18:00-19:30", "UNKNOWN": "12:00-13:30"}
POP_DAYS_BEFORE_DUE = 5

FORBIDDEN_FEATURES = {
    LABEL, "latent_stress_index", "synthetic_situation_truth", "is_golden", "golden_scenario",
    "anomaly_score", "risk_score", "risk_level", "situation_hint", "top_factors", "current_cycle_paid",
    "max_days_in_arrears_12m", "last_intervention_outcome", "prior_interventions_accepted_n",
    "days_to_due", "customer_id", "full_name_mock", "dui_mock", "phone_mock", "account_id_mock",
}

# --- Arquetipos de 3 capas (mejora post-Fase 8): producto crediticio + capacidad digital ---
# Ninguno de los dos entra a IF_FEATURES ni LR_FEATURES a propósito: son contexto de
# enrutamiento (NBA / Policy Engine / prompt), no señales de riesgo o anomalía -- mezclarlos
# arriesgaría que el modelo "aprenda" que cierto producto es intrínsecamente más riesgoso en
# vez de medir el comportamiento real del ciclo (mismo principio que excluye `income_type` de IF).
CREDIT_PRODUCTS = {
    "PERSONAL_LOAN_PAYROLL_DEDUCTION": 0.20,   # Crédito Personal con orden de descuento
    "PERSONAL_LOAN_ACCOUNT_DEBIT": 0.15,       # Crédito Personal con cargo a cuenta
    "PERSONAL_LOAN_MORTGAGE_BACKED": 0.05,     # Crédito Personal con Garantía Hipotecaria
    "CREDICHEQUE": 0.10,
    "SALARY_ADVANCE": 0.08,                    # Adelanto de Salario
    "OVERDRAFT_ELITE": 0.07,                   # Sobregiro Elite
    "EXTRA_FINANCING": 0.05,                   # Extrafinanciamiento
    "HOME_LOAN": 0.10,                         # Crédito de Vivienda
    "VEHICLE_LOAN": 0.12,                      # Crédito para Vehículo
    "STUDENT_LOAN": 0.08,                      # Crédito de Estudio
}
# Productos donde el umbral de escalamiento a humano debe ser más bajo (garantía real o
# monto/plazo grandes -- un error de negociación automática pesa más).
SENSITIVE_CREDIT_PRODUCTS = {"PERSONAL_LOAN_MORTGAGE_BACKED", "HOME_LOAN", "VEHICLE_LOAN"}
# Productos rotativos/liquidez-puente: no se debe ofrecer "más crédito" como salida
# automática a una presión de liquidez ya existente (evita el ciclo deuda-sobre-deuda).
REVOLVING_CREDIT_PRODUCTS = {"CREDICHEQUE", "OVERDRAFT_ELITE", "EXTRA_FINANCING", "SALARY_ADVANCE"}

# D1 = autónomo digital, D2 = necesita guía paso a paso, D3 = no sabe usar bien la app.
# SUPUESTO DE DEMO: no hay dato de edad en el generador, así que es un sorteo independiente
# (documentado como limitación -- en producción real vendría de comportamiento observado a
# más largo plazo, no de una sola corrida).
DIGITAL_CAPABILITY_MIX = {"D1": 0.65, "D2": 0.25, "D3": 0.10}
