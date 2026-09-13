"""
export_dashboard_data.py — Fase 8: consolida todo lo construido en un único JSON
que el dashboard mínimo (React, `src/frontend`) puede leer sin necesitar un backend
vivo. No hay servidor HTTP en este MVP -- el "run único" (`run_all.py`) regenera
este archivo y el frontend lo sirve como asset estático
(`src/frontend/public/data/dashboard_data.json`).

Reutiliza `interventions_log.csv` (1,800 clientes muestreados, Fase 7) para las
distribuciones de cartera en vez de volver a puntuar 3,000 clientes uno por uno
(ver el hallazgo de latencia de Fase 5: cada scoring completo cuesta ~55 ms, evitar
pagarlo 3,000 veces solo para un dashboard).
"""
import os
import sys
import json

import pandas as pd

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_BASE_DIR, "..", "ml"))
from risk_engine import get_risk_profile  # noqa: E402
from score_customer import score_customer  # noqa: E402

_RESEARCH_DIR = os.path.join(_BASE_DIR, "..", "..", "research", "ba_a_tiempo")
_OUTPUTS_DIR = os.path.join(_RESEARCH_DIR, "outputs")
_INTERACTIONS_DIR = os.path.join(_RESEARCH_DIR, "data", "interactions")
_GOLDEN_PATH = os.path.join(_BASE_DIR, "..", "..", "data", "synthetic", "golden_customers.csv")
_EXPORT_PATH = os.path.join(_BASE_DIR, "..", "frontend", "public", "data", "dashboard_data.json")

# S4 (baja respuesta digital) del diseño v1 se reemplazó por el flag `low_digital_response`,
# ortogonal a `situation_hint` (S0-S3) -- ver docs/contracts.md. G09 es el único golden con
# `golden_expected_situation = "S4"`, así que su validación real es sobre el flag, no la situación.
_S4_GOLDEN_IDS = {"GOLD-G09"}

# G06 quedó con `golden_expected_situation = "S2"` en el CSV (heredado del diseño v1), pero el
# propio diseño documenta la excepción (BA_A_Tiempo_Diseno_Dataset_v1.md §10, "fecha de ingreso
# desconocida"): con `income_date_unknown=1` la regla S2 NO debe aplicar (no hay gap positivo que
# medir sin fecha), así que S0 es el resultado correcto y esperado, no un fallo del motor de reglas.
_KNOWN_S2_RULE_EXCEPTIONS = {"GOLD-G06": "income_date_unknown=1 desactiva la regla S2 a propósito (v1 §10)"}


def _records(df: pd.DataFrame) -> list:
    """`DataFrame.to_dict` deja `NaN` para celdas vacías (p. ej. un CSV con un
    campo en blanco); `json.dump` escribe eso como el token `NaN`, que NO es
    JSON válido y rompe `JSON.parse` en el navegador. `None` -> `null` sí lo es.
    `DataFrame.where(df.notna(), None)` NO alcanza a reemplazarlo en columnas
    `object` (pandas 3.x sigue dejando el float `nan`), así que se hace la
    limpieza fila por fila después de convertir a dict."""
    records = df.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and pd.isna(value):
                record[key] = None
    return records


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _model_comparison():
    anomaly = _load_json(os.path.join(_OUTPUTS_DIR, "anomaly_benchmark.json")) or {}
    risk = _load_json(os.path.join(_OUTPUTS_DIR, "risk_benchmark.json")) or {}
    channel = _load_json(os.path.join(_OUTPUTS_DIR, "channel_timing_benchmark.json")) or {}
    score_latency = _load_json(os.path.join(_OUTPUTS_DIR, "score_customer_benchmark.json")) or {}

    return {
        "anomaly_detection": {
            "candidates": anomaly, "winner": "IsolationForest",
            "why": "Mejor relación AUC/latencia/explicabilidad (ablación por feature, barata de calcular). "
                   "Z-score de Mahalanobis queda como segunda opinión para monitoreo de drift poblacional.",
        },
        "supervised_risk": {
            "candidates": risk, "winner": "LogisticRegression",
            "why": "Gana en AUC, Brier score, tamaño y latencia pese a ser el modelo más simple -- con "
                   "3,000 filas y 11 features, Random Forest y LightGBM no encuentran no-linealidad real "
                   "que explotar y solo agregan costo de explicabilidad (necesitarían SHAP).",
        },
        "channel_preference": {
            "metrics": channel,
            "why": "Nivel 1 (tasa por cliente) + nivel 2 (Logistic Regression poblacional, AUC modesto "
                   "porque no ve la afinidad oculta del generador) + fallback determinista a CALL. "
                   "El diseño de dos niveles es la elección, no un solo algoritmo ganador.",
        },
        "score_customer_latency": score_latency,
    }


def _golden_customers_validation():
    golden = pd.read_csv(_GOLDEN_PATH)
    rows = []
    for _, g in golden.iterrows():
        cid = g["customer_id"]
        profile = get_risk_profile(cid)
        note = None
        if cid in _S4_GOLDEN_IDS:
            passed = bool(profile["low_digital_response"]) == bool(g["golden_expected_situation"] == "S4")
            expected_display = "low_digital_response=True (v1 S4, ver nota v2)"
            actual_display = f"low_digital_response={profile['low_digital_response']}"
        elif cid in _KNOWN_S2_RULE_EXCEPTIONS:
            passed = profile["situation_hint"] == "S0"
            expected_display, actual_display = "S0 (excepción documentada)", profile["situation_hint"]
            note = _KNOWN_S2_RULE_EXCEPTIONS[cid]
        else:
            passed = profile["situation_hint"] == g["golden_expected_situation"]
            expected_display = g["golden_expected_situation"]
            actual_display = profile["situation_hint"]
        rows.append({
            "customer_id": cid, "scenario": g["golden_scenario"],
            "expected_situation": expected_display, "actual_situation": actual_display,
            "passed": passed, "risk_level": profile["risk_level"], "anomaly_score": profile["anomaly_score"],
            "note": note,
        })
    return rows


def _sample_scored_customers(n: int = 20) -> list:
    interventions_path = os.path.join(_INTERACTIONS_DIR, "interventions_log.csv")
    interventions = pd.read_csv(interventions_path)
    # una muestra representativa: algunos de cada situation_hint si existen
    sample_ids = []
    for situation in ["S0", "S1", "S2", "S3"]:
        subset = interventions[interventions["situation_hint"] == situation]["customer_id"]
        sample_ids += subset.head(max(1, n // 4)).tolist()
    sample_ids = sample_ids[:n]
    return [score_customer(cid) for cid in sample_ids]


def _portfolio_summary() -> dict:
    interventions_path = os.path.join(_INTERACTIONS_DIR, "interventions_log.csv")
    interventions = pd.read_csv(interventions_path)
    intervened = interventions[interventions["decision"] == "INTERVENE"]

    return {
        "n_sampled": len(interventions),
        "pct_no_contact": round((interventions["decision"] == "NO_CONTACT").mean() * 100, 1),
        "situation_hint_distribution": interventions["situation_hint"].value_counts(normalize=True).round(4).to_dict(),
        "risk_level_distribution": interventions["risk_level"].value_counts(normalize=True).round(4).to_dict(),
        "recommended_action_distribution": intervened["recommended_action"].value_counts().to_dict(),
        "channel_source_distribution": intervened["channel_source"].value_counts(normalize=True).round(4).to_dict(),
    }


def _conversation_metrics() -> dict:
    conversations_path = os.path.join(_INTERACTIONS_DIR, "conversations_log.csv")
    conversations = pd.read_csv(conversations_path)
    return {
        "n_conversations": len(conversations),
        "tone_distribution": conversations["tone_overall"].value_counts(normalize=True).round(4).to_dict(),
        "barrier_distribution": conversations["barrier_detected"].value_counts(normalize=True).round(4).to_dict(),
        "barrier_vs_situation_match_rate": round(float(conversations["barrier_vs_situation_match"].mean()), 4),
        "escalation_rate": round(float(conversations["escalation_triggered"].mean()), 4),
        "acceptance_rate": round(float(conversations["alternative_accepted"].fillna("").ne("").mean()), 4),
    }


def _priority_table_top(n: int = 15) -> list:
    path = os.path.join(_OUTPUTS_DIR, "nba_priority_table.csv")
    if not os.path.exists(path):
        return []
    table = pd.read_csv(path)
    return _records(table.head(n))


def _golden_conversations() -> list:
    path = os.path.join(_INTERACTIONS_DIR, "golden_conversations.csv")
    if not os.path.exists(path):
        return []
    return _records(pd.read_csv(path))


def build_dashboard_data() -> dict:
    return {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "models": _model_comparison(),
        "golden_customers": _golden_customers_validation(),
        "golden_conversations": _golden_conversations(),
        "portfolio": _portfolio_summary(),
        "conversation_metrics": _conversation_metrics(),
        "nba_priority_table_top": _priority_table_top(),
        "sample_scored_customers": _sample_scored_customers(),
    }


def write_dashboard_data() -> str:
    data = build_dashboard_data()
    os.makedirs(os.path.dirname(_EXPORT_PATH), exist_ok=True)
    with open(_EXPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    return _EXPORT_PATH


if __name__ == "__main__":
    path = write_dashboard_data()
    size_kb = os.path.getsize(path) / 1024
    print(f"dashboard_data.json escrito ({size_kb:.1f} KB) en {path}")
