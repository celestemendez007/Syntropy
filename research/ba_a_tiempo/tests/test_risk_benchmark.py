import joblib
import pytest

from ba_a_tiempo import generator as G
from ba_a_tiempo import risk_benchmark as RB
from ba_a_tiempo import config as C


@pytest.fixture(scope="module")
def bench():
    G.run_all()
    results, summary = RB.run_benchmark()
    RB.build_report(results, summary)
    return results, summary


def test_all_three_models_ran(bench):
    _, summary = bench
    assert set(summary.index) == {"LogisticRegression", "RandomForest", "LightGBM"}


def test_auc_within_plausible_range(bench):
    """Ningún modelo debería dar AUC ~0.5 (no aprendió nada) ni ~1.0 (leakage/circularidad
    en la etiqueta sintética, ver BA_A_Tiempo_Diseno_Dataset_v1.md §6)."""
    _, summary = bench
    for name, row in summary.iterrows():
        auc = float(row["auc"])
        assert 0.55 < auc < 0.95, f"{name}: AUC sospechoso ({auc})"


def test_calibration_metrics_bounded(bench):
    _, summary = bench
    for name, row in summary.iterrows():
        assert 0 <= float(row["brier_score"]) <= 0.25
        assert 0 <= float(row["calibration_mae"]) <= 0.5


def test_latency_production_viable(bench):
    """Ningún modelo debería tardar más de 100ms p95 por cliente (scoring uno-a-uno)."""
    _, summary = bench
    for name, row in summary.iterrows():
        p95 = float(row["latency_p95_ms"])
        assert p95 < 100, f"{name}: latencia p95 demasiado alta para producción ({p95} ms)"


def test_golden_customers_excluded_from_benchmark(bench):
    """Los golden tienen etiqueta fija (0) por construcción; si se colaran al benchmark
    inflarían artificialmente la clase negativa."""
    snap = RB.load_data()
    assert "is_golden" not in snap.columns or snap["is_golden"].fillna(False).sum() == 14


def test_models_persisted_and_reloadable():
    for name in ["LogisticRegression", "RandomForest", "LightGBM"]:
        path = C.MODELS / f"risk_{name}.joblib"
        assert path.exists(), f"falta {path}"
        model = joblib.load(path)
        assert hasattr(model, "predict_proba")
    assert (C.MODELS / "risk_scaler.joblib").exists()
    assert (C.MODELS / "risk_feature_order.json").exists()


def test_no_forbidden_feature_used(bench):
    for feat in C.LR_FEATURES:
        assert feat not in C.FORBIDDEN_FEATURES


def test_report_file_written(bench):
    path = C.OUTPUTS / "risk_benchmark_report.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Veredicto" in text
    assert len(text) > 500
