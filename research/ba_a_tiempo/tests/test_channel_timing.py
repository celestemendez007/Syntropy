import pytest

from ba_a_tiempo import generator as G
from ba_a_tiempo import channel_timing as CT
from ba_a_tiempo import config as C


@pytest.fixture(scope="module")
def bench():
    G.run_all()
    results = CT.run_benchmark()
    CT.build_report(results)
    return results


def test_channel_model_auc_plausible(bench):
    """No debe ser NaN ni un AUC absurdo (>0.99 sería leakage: la afinidad oculta
    del generador nunca es una feature del nivel 2)."""
    assert 0.4 < bench["channel_model_auc"] < 0.99


def test_latency_production_viable(bench):
    assert bench["channel_latency_p95_ms"] < 100
    assert bench["timing_latency_p95_ms"] < 100


def test_channel_source_distribution_sums_to_one(bench):
    dist = bench["channel_source_distribution"]
    assert abs(sum(dist.values()) - 1.0) < 1e-6


def test_channel_pref_model_persisted():
    assert (C.MODELS / "channel_pref_v1.joblib").exists()
    assert (C.MODELS / "timing_stats_v1.json").exists()


def test_get_channel_preference_always_resolves_to_real_channel():
    """Nunca debe devolver un canal inexistente: si es UNDETERMINED, channel_used
    debe caer al fallback CALL (regla de producto), nunca quedar vacío."""
    snap = CT.load_snapshot()
    for cid in snap["customer_id"].iloc[:20]:
        result = CT.get_channel_preference(cid)
        assert result["channel_used"] in C.CHANNELS
        if result["channel_pref_model"] == "UNDETERMINED":
            assert result["channel_used"] == C.DEFAULT_CHANNEL
            assert result["channel_source"] == "FALLBACK_CALL"


def test_get_timing_always_returns_valid_window():
    snap = CT.load_snapshot()
    for cid in snap["customer_id"].iloc[:20]:
        timing = CT.get_timing(cid)
        assert "-" in timing["best_hour_window"]
        assert 1 <= timing["best_days_before_due"] <= 15
        assert 0 <= timing["timing_confidence"] <= 1


def test_golden_g09_channel_confidence_is_low(bench):
    """G09 (contact_response_rate=0) no debería dar al modelo evidencia fuerte de
    ningún canal -- es el caso que debe activar el fallback a CALL."""
    g09 = bench["golden_g09_low_digital_response_channel"]
    assert g09 is not None
    assert g09["confidence"] < C.CHANNEL_CONF_MIN


def test_report_file_written(bench):
    path = C.OUTPUTS / "channel_timing_report.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Veredicto" in text
    assert len(text) > 500
