import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from export_dashboard_data import build_dashboard_data, write_dashboard_data

EXPECTED_TOP_KEYS = {"generated_at", "models", "golden_customers", "golden_conversations", "portfolio",
                     "conversation_metrics", "nba_priority_table_top", "sample_scored_customers"}


@pytest.fixture(scope="module")
def data():
    return build_dashboard_data()


def test_top_level_shape(data):
    assert EXPECTED_TOP_KEYS <= set(data.keys())


def test_all_twelve_golden_customers_present_and_pass(data):
    """Con las dos excepciones documentadas (G09 S4->low_digital_response, G06
    income_date_unknown desactiva la regla S2), los 12 golden deben pasar --
    si esto falla, alguien cambió una regla de situation_hint sin actualizar la
    excepción documentada aquí y en el diseño."""
    assert len(data["golden_customers"]) == 12
    failed = [g["customer_id"] for g in data["golden_customers"] if not g["passed"]]
    assert failed == [], f"golden customers fallando: {failed}"


def test_portfolio_distributions_sum_to_one(data):
    portfolio = data["portfolio"]
    assert abs(sum(portfolio["situation_hint_distribution"].values()) - 1.0) < 1e-6
    assert abs(sum(portfolio["risk_level_distribution"].values()) - 1.0) < 1e-6


def test_ten_golden_conversations_present(data):
    assert len(data["golden_conversations"]) == 10


def test_models_section_has_all_phases(data):
    models = data["models"]
    assert "anomaly_detection" in models
    assert "supervised_risk" in models
    assert "channel_preference" in models
    assert "score_customer_latency" in models
    assert models["supervised_risk"]["winner"] == "LogisticRegression"


def test_sample_scored_customers_use_real_contract(data):
    samples = data["sample_scored_customers"]
    assert len(samples) > 0
    for s in samples:
        assert "risk" in s and "situation" in s and "nba" in s


def test_write_dashboard_data_creates_readable_json():
    import json
    path = write_dashboard_data()
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    assert EXPECTED_TOP_KEYS <= set(payload.keys())
