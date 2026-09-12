import time
import joblib
import numpy as np
import pandas as pd
import pytest

from ba_a_tiempo import generator as G
from ba_a_tiempo import anomaly_benchmark as AB
from ba_a_tiempo import config as C
from ba_a_tiempo.detectors import ZScoreDetector


@pytest.fixture(scope="module")
def bench():
    G.run_all()
    results, summary = AB.run_benchmark()
    AB.build_report(results, summary)
    return results, summary


def test_all_four_models_ran(bench):
    _, summary = bench
    assert set(summary.index) == {"IsolationForest", "LocalOutlierFactor", "OneClassSVM", "ZScore_Mahalanobis"}


def test_auc_within_plausible_range(bench):
    """Ningún modelo debería dar AUC ~0.5 (no aprendió nada) ni ~1.0 (leakage/trivial)."""
    _, summary = bench
    for name, row in summary.iterrows():
        auc = float(row["auc_s0_vs_s3"])
        assert 0.55 < auc < 0.999, f"{name}: AUC sospechoso ({auc})"


def test_latency_production_viable(bench):
    """Ningún modelo debería tardar más de 100ms p95 por cliente (scoring uno-a-uno)."""
    _, summary = bench
    for name, row in summary.iterrows():
        p95 = float(row["latency_p95_ms"])
        assert p95 < 100, f"{name}: latencia p95 demasiado alta para producción ({p95} ms)"


def test_golden_g02_flagged_anomalous_but_no_contact(bench):
    """G02 (ingreso extraordinario) debe verse anómalo para al menos 2 de 4 modelos,
    reflejando 'anomalía != mora' (ver docs)."""
    _, summary = bench
    n_high = (summary["golden_g02_anomalia_benigna"].astype(float) > 0.5).sum()
    assert n_high >= 2


def test_models_persisted_and_reloadable():
    """Los modelos guardados deben poder cargarse desde otro proceso sin depender de __main__."""
    for name in ["IsolationForest", "LocalOutlierFactor", "OneClassSVM", "ZScore_Mahalanobis"]:
        path = C.MODELS / f"anomaly_{name}.joblib"
        assert path.exists(), f"falta {path}"
        model = joblib.load(path)
        assert hasattr(model, "score_samples") or hasattr(model, "decision_function")


def test_zscore_detector_importable_outside_main():
    """Regresión: ZScoreDetector debe vivir en su propio módulo, no en anomaly_benchmark,
    para que joblib pueda deserializarlo fuera del script que lo entrenó."""
    d = ZScoreDetector()
    X = pd.DataFrame(np.random.RandomState(0).normal(size=(50, 3)), columns=["a", "b", "c"])
    d.fit(X)
    scores = d.score_samples(X)
    assert len(scores) == 50
    assert ZScoreDetector.__module__ == "ba_a_tiempo.detectors"


def test_no_forbidden_feature_used(bench):
    """Ninguna feature usada por el benchmark debe estar en la lista de prohibidas."""
    for feat in C.IF_FEATURES:
        assert feat not in C.FORBIDDEN_FEATURES


def test_report_file_written(bench):
    path = C.OUTPUTS / "anomaly_benchmark_report.md"
    assert path.exists()
    text = path.read_text()
    assert "Veredicto" in text
    assert len(text) > 500
