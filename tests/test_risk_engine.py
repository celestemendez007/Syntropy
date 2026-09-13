import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/ml')))
from risk_engine import get_risk_profile, load_dataset, load_golden


def test_dataset_loads_with_real_columns():
    df = load_dataset()
    assert len(df) > 100
    assert "balance_ratio" in df.columns
    assert "synthetic_late_payment_next_cycle" in df.columns  # existe pero nunca se usa como feature


def test_golden_customers_lookup_works():
    """Regresión: los golden viven en un CSV aparte (prefijo GOLD-); si el lookup
    solo mira dataset.csv, caen todos al fallback por defecto sin dar error."""
    golden = load_golden()
    assert len(golden) == 16  # 14 golden + GOLD-G15 con 2 créditos (product_seq 1 y 2)
    profile = get_risk_profile("GOLD-G01")
    assert "_warning" not in profile, "el golden no se encontró y cayó al fallback silencioso"


def test_real_customer_gets_real_scores_not_default():
    df = load_dataset()
    sample_id = df["customer_id"].iloc[0]
    profile = get_risk_profile(sample_id)
    assert "_warning" not in profile
    assert 0 <= profile["anomaly_score"] <= 1
    assert profile["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert profile["situation_hint"] in {"S0", "S1", "S2", "S3"}


def test_unknown_customer_falls_back_gracefully():
    profile = get_risk_profile("NO_EXISTE_9999")
    assert "_warning" in profile
    assert profile["risk_level"] == "MEDIUM"


def test_risk_score_combines_lr_and_anomaly():
    """Fase 3: risk_score ya no es un proxy de anomaly_score -- combina risk_prob_lr
    (Logistic Regression) y anomaly_score (Isolation Forest) con pesos 0.6/0.4."""
    df = load_dataset()
    profile = get_risk_profile(df["customer_id"].iloc[0])
    assert "_pending" not in profile
    assert 0 <= profile["risk_prob_lr"] <= 1
    # tolerancia de 1e-4: risk_score interno se calcula con los valores SIN redondear
    # de risk_prob_lr/anomaly_score, mientras que aquí solo tenemos las versiones ya
    # redondeadas del profile -- pueden diferir en el último dígito por orden de redondeo.
    expected = round(0.6 * profile["risk_prob_lr"] + 0.4 * profile["anomaly_score"], 4)
    assert abs(profile["risk_score"] - expected) <= 1e-4


def test_golden_g02_benign_anomaly_not_misclassified_as_liquidity_crisis():
    """G02: ingreso extraordinario, anómalo pero no debería verse como S3."""
    profile = get_risk_profile("GOLD-G02")
    assert profile["situation_hint"] != "S3"


def test_golden_g09_low_digital_response_detected():
    """G09: baja respuesta digital debe capturarse en el flag aparte,
    no forzada dentro de situation_hint (S4 no es parte del enum S0-S3 por diseño)."""
    profile = get_risk_profile("GOLD-G09")
    assert profile["low_digital_response"] is True


def test_top_factors_returns_list_of_known_features():
    from risk_engine import IF_FEATURES
    df = load_dataset()
    profile = get_risk_profile(df["customer_id"].iloc[0])
    for f in profile["top_factors"]:
        assert f in IF_FEATURES
