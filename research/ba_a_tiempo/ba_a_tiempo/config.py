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
