"""
risk_engine.py — Motor de riesgo real (Fase 1-3 de research/ba_a_tiempo).

Reemplaza el mock anterior (4 clientes hardcodeados). Implementa:
  - anomaly_score real: Isolation Forest entrenado sobre 3,000 clientes sintéticos
    (ver research/ba_a_tiempo/outputs/anomaly_benchmark_report.md para la comparación
    contra Local Outlier Factor, One-Class SVM y z-score de Mahalanobis).
  - risk_prob_lr real: Logistic Regression entrenada sobre la etiqueta sintética
    `synthetic_late_payment_next_cycle` (ver research/ba_a_tiempo/outputs/risk_benchmark_report.md
    para la comparación contra Random Forest y LightGBM -- LR gana en AUC, calibración,
    tamaño y latencia, además de ser el único con explicabilidad de fórmula exacta).
  - risk_score = 0.6*risk_prob_lr + 0.4*anomaly_score (SUPUESTO DE DEMO, pesos fijos
    en RISK_W_LR/RISK_W_IF, cortes de risk_level en RISK_CUTS). Ya no es un proxy de
    anomaly_score solamente.
  - situation_hint real: reglas deterministas (no ML) sobre las features derivadas,
    S0-S4 según docs/contracts.md v2.
  - top_factors real: ablación por feature sobre el Isolation Forest (reemplazar por
    la mediana y medir el cambio en el score).

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

LR_FEATURES = [
    "balance_ratio", "projected_coverage", "balance_vs_historical", "income_variation",
    "expense_variation_30d", "payment_punctuality", "partial_payments_n",
    "failed_payment_attempts_30d", "income_due_gap_pos", "income_amount_cv", "external_debt_ratio_mock",
]
LR_LOG1P = {"balance_ratio", "projected_coverage", "balance_vs_historical"}

RISK_W_LR, RISK_W_IF = 0.6, 0.4  # SUPUESTO DE DEMO (BA_A_Tiempo_Diseno_Dataset_v1.md §7)
RISK_CUTS = (0.35, 0.65)

_dataset_cache = None
_model_cache = None
_scaler_cache = None
_golden_cache = None
_risk_model_cache = None
_risk_scaler_cache = None
_if_feature_medians_cache = None


def load_dataset() -> pd.DataFrame:
    global _dataset_cache
    if _dataset_cache is None:
        _dataset_cache = pd.read_csv(_DATA_PATH)
    return _dataset_cache


def _if_feature_medians() -> pd.Series:
    """Medianas poblacionales de IF_FEATURES, cacheadas: `_top_factors` las usa
    para la ablación en cada llamada, y recalcular `median()` sobre 3,000 filas
    por feature en cada scoring individual es trabajo repetido innecesario
    (el dataset no cambia entre llamadas)."""
    global _if_feature_medians_cache
    if _if_feature_medians_cache is None:
        _if_feature_medians_cache = load_dataset()[IF_FEATURES].median()
    return _if_feature_medians_cache


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


def _load_risk_model_and_scaler():
    global _risk_model_cache, _risk_scaler_cache
    if _risk_model_cache is None:
        _risk_model_cache = joblib.load(os.path.join(_MODELS_DIR, "risk_LogisticRegression.joblib"))
        _risk_scaler_cache = joblib.load(os.path.join(_MODELS_DIR, "risk_scaler.joblib"))
    return _risk_model_cache, _risk_scaler_cache


def _prepare_features(row: pd.Series) -> pd.DataFrame:
    X = row[IF_FEATURES].to_frame().T.astype(float)
    for col in IF_LOG1P:
        X[col] = np.log1p(np.clip(X[col], 0, None))
    return X


def _prepare_lr_features(row: pd.Series) -> pd.DataFrame:
    X = row[LR_FEATURES].to_frame().T.astype(float)
    for col in LR_LOG1P:
        X[col] = np.log1p(np.clip(X[col], 0, None))
    return X


def _risk_prob_lr(row: pd.Series) -> float:
    """Probabilidad de pago tardío/parcial en el siguiente ciclo, según la Logistic
    Regression ganadora del benchmark de Fase 3 (ver risk_benchmark_report.md)."""
    model, scaler = _load_risk_model_and_scaler()
    X = _prepare_lr_features(row)
    X_s = pd.DataFrame(scaler.transform(X), columns=X.columns)
    return float(model.predict_proba(X_s)[0, 1])


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
    explican la anomalía de este cliente.

    Batcheado en una sola llamada a `score_samples` (base + 10 versiones
    ablacionadas = 11 filas) en vez de 11 llamadas individuales: cada llamada a
    IsolationForest.score_samples paga ~7ms de overhead fijo (validación +
    recorrer 200 árboles) sin importar el tamaño del batch, así que 11 llamadas
    de 1 fila cuestan ~11x más que 1 llamada de 11 filas. Esto fue el cuello de
    botella real medido en el benchmark end-to-end de Fase 5
    (score_customer_benchmark_report.md) -- no el I/O, como se sospechaba antes
    de perfilar."""
    model, scaler = _load_model_and_scaler()
    medians = _if_feature_medians()

    variants = [row]
    for feat in IF_FEATURES:
        modified = row.copy()
        modified[feat] = medians[feat]
        variants.append(modified)

    X_all = pd.concat([_prepare_features(v) for v in variants], ignore_index=True)
    X_all_s = pd.DataFrame(scaler.transform(X_all), columns=X_all.columns)
    raw_scores = model.score_samples(X_all_s)
    scores = np.clip((-raw_scores + 0.2) / 0.8, 0, 1)

    base_score = scores[0]
    contributions = {feat: base_score - scores[i + 1] for i, feat in enumerate(IF_FEATURES)}
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

    anomaly_score (Isolation Forest), risk_prob_lr (Logistic Regression) y
    situation_hint (reglas) son reales. risk_score combina IF + LR con los pesos
    SUPUESTO DE DEMO de RISK_W_LR/RISK_W_IF (ver BA_A_Tiempo_Diseno_Dataset_v1.md §7
    y research/ba_a_tiempo/outputs/risk_benchmark_report.md para por qué se eligió LR).
    """
    dataset = load_dataset()
    row = _find_customer_row(customer_id)
    if row is None:
        return {
            "customer_id": customer_id, "risk_level": "MEDIUM", "risk_score": 0.5,
            "anomaly_score": 0.5, "risk_prob_lr": 0.5, "situation_hint": "S0", "low_digital_response": False,
            "top_factors": [], "_warning": "customer_id no encontrado en dataset ni golden, valores por defecto",
        }

    anomaly_score, _ = _anomaly_score(row)
    risk_prob_lr = _risk_prob_lr(row)
    situation_hint, low_digital_response = _situation_hint(row)
    top_factors = _top_factors(row)

    risk_score = RISK_W_LR * risk_prob_lr + RISK_W_IF * anomaly_score
    if risk_score < RISK_CUTS[0]:
        risk_level = "LOW"
    elif risk_score < RISK_CUTS[1]:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    return {
        "customer_id": customer_id,
        "risk_score": round(risk_score, 4),
        "risk_level": risk_level,
        "anomaly_score": round(anomaly_score, 4),
        "risk_prob_lr": round(risk_prob_lr, 4),
        "situation_hint": situation_hint,
        "low_digital_response": low_digital_response,
        "top_factors": top_factors,
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
