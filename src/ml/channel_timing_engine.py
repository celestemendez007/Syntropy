"""
channel_timing_engine.py — Motor de canal y momento real (Fase 4 de research/ba_a_tiempo).

Implementa el diseño de BA_A_Tiempo_Propuesta_v2.md §7 (ver
research/ba_a_tiempo/ba_a_tiempo/channel_timing.py y outputs/channel_timing_report.md
para el benchmark completo, AUC, latencia y veredicto):

  - Canal (`get_channel_preference`): nivel 1 (tasa de respuesta por canal del propio
    cliente en `contacts_log`, si tiene >= 3 envíos a ese canal y el mejor supera al
    segundo por >= 0.2) con fallback a nivel 2 (Logistic Regression poblacional).
    Si la confianza de cualquiera de los dos es < CHANNEL_CONF_MIN, el canal es
    `UNDETERMINED` y el canal REAL usado (`channel_used`) es CALL (regla de producto,
    no del modelo -- así el sistema nunca se queda sin canal).
  - Momento (`get_timing`): estadístico, no ML. Franja horaria de 90 min con mayor
    tasa de respuesta si hay >= 5 observaciones del cliente, si no franja poblacional
    por `income_type`. Anticipación (días antes del vencimiento) por bucket con
    >= 3 observaciones, si no 5 días poblacional.

Ninguno de los dos combina con `risk_score`: son ortogonales a la Fase 3.
"""
import os
import json
import joblib
import numpy as np
import pandas as pd

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONTACTS_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "contacts_log.csv")
_DATASET_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "dataset.csv")
_GOLDEN_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "golden_customers.csv")
_MODELS_DIR = os.path.join(_BASE_DIR, "models")

CHANNELS = ["APP_PUSH", "SMS", "WHATSAPP", "CALL"]
DEFAULT_CHANNEL = "CALL"
CHANNEL_CONF_MIN = 0.5
EXPLORATION_RATE = 0.10
POP_HOUR_WINDOW = {"SALARIED": "12:00-13:30", "BIWEEKLY": "12:00-13:30",
                   "INDEPENDENT": "18:00-19:30", "UNKNOWN": "12:00-13:30"}
POP_DAYS_BEFORE_DUE = 5

HOUR_BIN_WIDTH = 1.5
DAYS_BUCKETS = [(1, 2), (3, 5), (6, 8), (9, 15)]
DAYS_BUCKET_CENTERS = {(1, 2): 2, (3, 5): 4, (6, 8): 7, (9, 15): 9}
LEVEL1_MIN_SENDS = 3
LEVEL1_MIN_MARGIN = 0.20

_contacts_cache = None
_dataset_cache = None
_golden_cache = None
_channel_payload_cache = None


def load_contacts() -> pd.DataFrame:
    global _contacts_cache
    if _contacts_cache is None:
        _contacts_cache = pd.read_csv(_CONTACTS_PATH, parse_dates=["sent_at"])
    return _contacts_cache


def load_dataset() -> pd.DataFrame:
    global _dataset_cache
    if _dataset_cache is None:
        _dataset_cache = pd.read_csv(_DATASET_PATH)
    return _dataset_cache


def load_golden() -> pd.DataFrame:
    global _golden_cache
    if _golden_cache is None:
        _golden_cache = pd.read_csv(_GOLDEN_PATH) if os.path.exists(_GOLDEN_PATH) else pd.DataFrame()
    return _golden_cache


def _find_customer_row(customer_id: str):
    dataset = load_dataset()
    match = dataset[dataset["customer_id"] == customer_id]
    if not match.empty:
        return match.iloc[0]
    golden = load_golden()
    if not golden.empty:
        match = golden[golden["customer_id"] == customer_id]
        if not match.empty:
            return match.iloc[0]
    return None


def _load_channel_model():
    global _channel_payload_cache
    if _channel_payload_cache is None:
        _channel_payload_cache = joblib.load(os.path.join(_MODELS_DIR, "channel_pref_v1.joblib"))
    return _channel_payload_cache


def _level2_feature_row(channel: str, customer_row: pd.Series, columns: list) -> pd.DataFrame:
    row = {c: 0.0 for c in columns}
    ch_col = f"ch_{channel}"
    if ch_col in row:
        row[ch_col] = 1.0
    income_type = customer_row.get("income_type", "UNKNOWN")
    inc_col = f"inc_{income_type}"
    if inc_col in row:
        row[inc_col] = 1.0
    hour_window = POP_HOUR_WINDOW.get(income_type, POP_HOUR_WINDOW["UNKNOWN"])
    row["hour_sent"] = float(hour_window.split("-")[0].split(":")[0])
    row["days_before_due_at_contact"] = POP_DAYS_BEFORE_DUE
    row["app_engagement_ratio"] = float(customer_row.get("app_engagement_ratio", 1.0))
    row["tenure_months"] = float(customer_row.get("tenure_months", 12))
    row["push_enabled"] = float(bool(customer_row.get("push_enabled", True)))
    return pd.DataFrame([row], columns=columns)


def _level2_channel_preference(customer_row: pd.Series):
    payload = _load_channel_model()
    model, scaler, columns = payload["model"], payload["scaler"], payload["columns"]
    probs = {}
    for channel in CHANNELS:
        if channel == "APP_PUSH" and not bool(customer_row.get("push_enabled", True)):
            continue
        X = _level2_feature_row(channel, customer_row, columns)
        X_s = pd.DataFrame(scaler.transform(X), columns=columns)
        probs[channel] = float(model.predict_proba(X_s)[0, 1])
    if not probs:
        return None, 0.0
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    best_channel, best_p = ranked[0]
    second_p = ranked[1][1] if len(ranked) > 1 else 0.0
    return best_channel, best_p - second_p


def _level1_channel_preference(customer_id: str, contacts: pd.DataFrame):
    hist = contacts[contacts["customer_id"] == customer_id]
    if hist.empty:
        return None
    rates = hist.groupby("channel")["responded"].agg(["mean", "count"])
    rates = rates[rates["count"] >= LEVEL1_MIN_SENDS]
    if rates.empty:
        return None
    ranked = rates.sort_values("mean", ascending=False)
    best_channel, best_rate = ranked.index[0], ranked.iloc[0]["mean"]
    second_rate = ranked.iloc[1]["mean"] if len(ranked) > 1 else 0.0
    if best_rate - second_rate < LEVEL1_MIN_MARGIN:
        return None
    return best_channel, float(best_rate)


def get_channel_preference(customer_id: str) -> dict:
    """`channel_pref_model` / `channel_pref_confidence` / `channel_used` / `channel_source`
    del contrato v2 (docs/contracts.md). `channel_used` SIEMPRE es un canal real
    (nunca UNDETERMINED): si la confianza es baja, cae a CALL."""
    contacts = load_contacts()
    customer_row = _find_customer_row(customer_id)

    level1 = _level1_channel_preference(customer_id, contacts)
    if level1 is not None:
        channel, confidence, source = level1[0], level1[1], "MODEL_LEVEL1"
    elif customer_row is not None:
        channel, confidence = _level2_channel_preference(customer_row)
        source = "MODEL_LEVEL2" if channel is not None else "FALLBACK_CALL"
    else:
        channel, confidence, source = None, 0.0, "FALLBACK_CALL"

    if channel is None or confidence < CHANNEL_CONF_MIN:
        return {"channel_pref_model": "UNDETERMINED", "channel_pref_confidence": round(float(confidence or 0.0), 4),
                "channel_used": DEFAULT_CHANNEL, "channel_source": "FALLBACK_CALL"}
    return {"channel_pref_model": channel, "channel_pref_confidence": round(float(confidence), 4),
            "channel_used": channel, "channel_source": source}


def _hour_bucket(hour: float) -> int:
    return int(hour // HOUR_BIN_WIDTH)


def _bucket_to_window(bucket: int) -> str:
    start = bucket * HOUR_BIN_WIDTH
    end = start + HOUR_BIN_WIDTH
    return f"{int(start):02d}:{int((start % 1) * 60):02d}-{int(end):02d}:{int((end % 1) * 60):02d}"


def _days_bucket(days: float):
    for lo, hi in DAYS_BUCKETS:
        if lo <= days <= hi:
            return (lo, hi)
    return None


def get_timing(customer_id: str) -> dict:
    """`best_hour_window` / `best_days_before_due` / `timing_confidence` del contrato v2."""
    contacts = load_contacts()
    customer_row = _find_customer_row(customer_id)
    income_type = customer_row.get("income_type", "UNKNOWN") if customer_row is not None else "UNKNOWN"

    hist = contacts[contacts["customer_id"] == customer_id].copy()

    hour_window = POP_HOUR_WINDOW.get(income_type, POP_HOUR_WINDOW["UNKNOWN"])
    n_hour_obs = len(hist)
    if n_hour_obs >= 5:
        hist["hour_bucket"] = hist["hour_sent"].apply(_hour_bucket)
        rates = hist.groupby("hour_bucket")["responded"].agg(["mean", "count"])
        rates = rates[rates["count"] >= 5]
        if not rates.empty:
            hour_window = _bucket_to_window(rates["mean"].idxmax())

    days_before = POP_DAYS_BEFORE_DUE
    hist["days_bucket"] = hist["days_before_due_at_contact"].apply(_days_bucket)
    days_hist = hist.dropna(subset=["days_bucket"])
    n_days_obs = len(days_hist)
    if n_days_obs >= 3:
        rates = days_hist.groupby("days_bucket")["responded"].agg(["mean", "count"])
        rates = rates[rates["count"] >= 3]
        if not rates.empty:
            days_before = DAYS_BUCKET_CENTERS[rates["mean"].idxmax()]

    timing_confidence = min(1.0, max(n_hour_obs, n_days_obs) / 10)
    return {"best_hour_window": hour_window, "best_days_before_due": int(days_before),
            "timing_confidence": round(timing_confidence, 4)}


def get_channel_and_timing(customer_id: str) -> dict:
    """Combina ambos para el contrato v2 (`channel` + `timing`, ver docs/contracts.md)."""
    return {**get_channel_preference(customer_id), **get_timing(customer_id)}


if __name__ == "__main__":
    dataset = load_dataset()
    sample_id = dataset["customer_id"].iloc[0]
    print(json.dumps(get_channel_and_timing(sample_id), indent=2, ensure_ascii=False))
