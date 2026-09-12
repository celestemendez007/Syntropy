"""
risk_engine.py — Motor de riesgo real (Fase 1-2 de research/ba_a_tiempo).

Reemplaza el mock anterior (4 clientes hardcodeados). Implementa:
  - anomaly_score real: Isolation Forest entrenado sobre 3,000 clientes sintéticos
    (ver research/ba_a_tiempo/outputs/anomaly_benchmark_report.md para la comparación
    contra Local Outlier Factor, One-Class SVM y z-score de Mahalanobis).
  - situation_hint real: reglas deterministas (no ML) sobre las features derivadas,
    S0-S4 según docs/contracts.md v2.
  - top_factors real: ablación por feature (reemplazar por la mediana y medir el
    cambio en el score de IF).

PENDIENTE (Fase 3, no implementada aún):
  - risk_score / risk_level combinando IF + un modelo supervisado (Logistic Regression /
    LightGBM sobre la etiqueta sintética). Por ahora risk_level se deriva SOLO de
    anomaly_score como proxy interino -- está marcado explícitamente abajo para que
    nadie lo confunda con el diseño final. No se debe usar como score productivo.

Requiere: pandas, scikit-learn, joblib, numpy (ver requirements del módulo ml).
"""
import os
import json
import joblib
import numpy as np
import pandas as pd

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "dataset.csv")
_MODELS_DIR = os.path.join(_BASE_DIR, "models")

IF_FEATURES = [
    "balance_vs_historical", "recent_balance_drop", "balance_ratio", "min_balance_ratio_30d",
    "income_variation", "expense_variation_30d", "spending_velocity_7d",
    "failed_payment_attempts_30d", "last_payment_delay_deviation", "failed_attempts_deviation",
]
IF_LOG1P = {"balance_vs_historical", "balance_ratio", "min_balance_ratio_30d", "spending_velocity_7d"}

_dataset_cache = None
_model_cache = None
_scaler_cache = None
_golden_cache = None


def load_dataset() -> pd.DataFrame:
    global _dataset_cache
    if _dataset_cache is None:
        _dataset_cache = pd.read_csv(_DATA_PATH)
    return _dataset_cache


def load_golden() -> pd.DataFrame:
    global _golden_cache
    if _golden_cache is None:
        golden_path = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "golden_customers.csv")
        _golden_cache = pd.read_csv(golden_path) if os.path.exists(golden_path) else pd.DataFrame()
    return _golden_cache


def _find_customer_row(customer_id: str):
    """Busca en el dataset principal y, si no aparece, en los golden customers
    (viven en un archivo separado con prefijo GOLD-)."""
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


def _load_model_and_scaler():
    global _model_cache, _scaler_cache
    if _model_cache is None:
        _model_cache = joblib.load(os.path.join(_MODELS_DIR, "anomaly_IsolationForest.joblib"))
        _scaler_cache = joblib.load(os.path.join(_MODELS_DIR, "anomaly_scaler.joblib"))
    return _model_cache, _scaler_cache


def _prepare_features(row: pd.Series) -> pd.DataFrame:
    X = row[IF_FEATURES].to_frame().T.astype(float)
    for col in IF_LOG1P:
        X[col] = np.log1p(np.clip(X[col], 0, None))
    return X


def _anomaly_score(row: pd.Series):
    """Retorna (anomaly_score en [0,1], raw_score) usando el IF real."""
    model, scaler = _load_model_and_scaler()
    X = _prepare_features(row)
    X_s = pd.DataFrame(scaler.transform(X), columns=X.columns)
    raw = model.score_samples(X_s)[0]  # sklearn: score bajo = anómalo
    # normalización aproximada: rango típico de score_samples de IF entrenado es [-0.6, 0.2]
    # (ver anomaly_benchmark.py para la normalización exacta contra la población de train)
    anomaly_score = float(np.clip((-raw + 0.2) / 0.8, 0, 1))
    return anomaly_score, raw


def _top_factors(row: pd.Series, n: int = 3):
    """Ablación: reemplaza cada feature por la mediana poblacional y mide cuánto
    sube el anomaly_score al quitarla. Las que más lo suben son las que más
    explican la anomalía de este cliente."""
    dataset = load_dataset()
    base_score, _ = _anomaly_score(row)
    contributions = {}
    for feat in IF_FEATURES:
        modified = row.copy()
        modified[feat] = dataset[feat].median()
        score_without, _ = _anomaly_score(modified)
        contributions[feat] = base_score - score_without  # cuánto aportaba esta feature
    ranked = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)
    return [f for f, delta in ranked[:n] if delta > 0.02]


def _situation_hint(row: pd.Series):
    """Reglas deterministas (NO ML) -- ver docs/contracts.md v2 §situation_hint.
    Se evalúan en orden; la primera que aplica gana."""
    balance_ratio = row.get("balance_ratio", 1.0)
    income_variation = row.get("income_variation", 0.0)
    expense_variation = row.get("expense_variation_30d", 0.0)
    failed_attempts = row.get("failed_payment_attempts_30d", 0)
    min_balance_ratio = row.get("min_balance_ratio_30d", 1.0)
    income_due_gap = row.get("income_due_gap", -99)
    projected_coverage = row.get("projected_coverage", 2.0)
    payment_punctuality = row.get("payment_punctuality", 1.0)
    payment_delay_avg = row.get("payment_delay_avg", 0.0)
    contacts_sent = row.get("contacts_sent_90d", 0)
    contact_response_rate = row.get("contact_response_rate", 1.0)
    app_engagement_ratio = row.get("app_engagement_ratio", 1.0)
    days_since_last_login = row.get("days_since_last_login", 0)

    if balance_ratio < 1 and (income_variation < -0.2 or expense_variation > 0.25
                               or failed_attempts >= 2 or min_balance_ratio < 0.3):
        situation = "S3"
    elif balance_ratio < 1 and income_due_gap is not None and income_due_gap > 0 and projected_coverage >= 1:
        situation = "S2"
    elif balance_ratio >= 1 and (payment_punctuality < 0.6 or payment_delay_avg > 1):
        situation = "S1"
    else:
        situation = "S0"

    low_digital_response = bool(
        (contacts_sent >= 3 and pd.notna(contact_response_rate) and contact_response_rate < 0.25)
        or (app_engagement_ratio < 0.3 and days_since_last_login > 21)
    )
    return situation, low_digital_response


def get_risk_profile(customer_id: str) -> dict:
    """
    Perfil de riesgo real para un cliente. Reemplaza el mock anterior.

    anomaly_score y situation_hint son reales (Isolation Forest + reglas).
    risk_score/risk_level son un PROXY INTERINO basado solo en anomaly_score
    hasta que la Fase 3 (Logistic Regression / LightGBM sobre etiqueta sintética)
    esté integrada -- no representan el diseño final del riesgo combinado.
    """
    dataset = load_dataset()
    row = _find_customer_row(customer_id)
    if row is None:
        return {
            "customer_id": customer_id, "risk_level": "MEDIUM", "risk_score": 0.5,
            "anomaly_score": 0.5, "situation_hint": "S0", "low_digital_response": False,
            "top_factors": [], "_warning": "customer_id no encontrado en dataset ni golden, valores por defecto",
        }

    anomaly_score, _ = _anomaly_score(row)
    situation_hint, low_digital_response = _situation_hint(row)
    top_factors = _top_factors(row)

    # --- PROXY INTERINO (ver docstring). Cortes iguales a docs/contracts.md (0.35/0.65). ---
    risk_score_proxy = anomaly_score
    if risk_score_proxy < 0.35:
        risk_level = "LOW"
    elif risk_score_proxy < 0.65:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    return {
        "customer_id": customer_id,
        "risk_score": round(risk_score_proxy, 4),
        "risk_level": risk_level,
        "anomaly_score": round(anomaly_score, 4),
        "situation_hint": situation_hint,
        "low_digital_response": low_digital_response,
        "top_factors": top_factors,
        "_pending": "risk_score es proxy de anomaly_score; falta integrar LR/LightGBM (Fase 3)",
    }


if __name__ == "__main__":
    dataset = load_dataset()
    sample_id = dataset["customer_id"].iloc[0]
    print(json.dumps(get_risk_profile(sample_id), indent=2, ensure_ascii=False))

    golden_path = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "golden_customers.csv")
    if os.path.exists(golden_path):
        golden = pd.read_csv(golden_path)
        print(f"\n--- {len(golden)} golden customers ---")
        for _, g in golden.iterrows():
            profile = get_risk_profile(g["customer_id"])
            print(f"{g['customer_id']:>12} | esperado={str(g.get('golden_expected_situation','?')):>3} "
                  f"| obtenido={profile['situation_hint']:>3} | anomaly={profile['anomaly_score']:.2f} "
                  f"| factors={profile['top_factors']}")
