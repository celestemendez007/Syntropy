import numpy as np
import pandas as pd
import pytest

from ba_a_tiempo import generator as G
from ba_a_tiempo import config as C


@pytest.fixture(scope="module")
def data():
    return G.run_all(seed=C.SEED)


def test_reproducibility():
    r1 = G.run_all(seed=42)["snapshot"]
    r2 = G.run_all(seed=42)["snapshot"]
    pd.testing.assert_frame_equal(r1, r2)


def test_different_seed_gives_different_data():
    r1 = G.run_all(seed=1)["snapshot"]
    r2 = G.run_all(seed=2)["snapshot"]
    assert not r1["current_balance"].equals(r2["current_balance"])
    G.run_all(seed=C.SEED)  # restaurar estado canónico en disco para los tests siguientes


def test_snapshot_shape_and_no_core_nulls(data):
    snap = data["snapshot"]
    assert len(snap) == C.N_CUSTOMERS
    for col in C.IF_FEATURES + C.LR_FEATURES:
        assert col in snap.columns, f"falta columna {col}"
        assert snap[col].isna().sum() == 0, f"{col} tiene nulos (debería estar imputado)"


def test_ranges(data):
    snap = data["snapshot"]
    assert snap["balance_ratio"].between(0, 10).all()
    assert snap["min_balance_ratio_30d"].between(0, 10).all()
    assert snap["income_variation"].between(-1, 3).all()
    assert snap["expense_variation_30d"].between(-1, 3).all()
    assert snap["payment_punctuality"].between(0, 1).all()
    assert snap["recent_balance_drop"].between(-1, 1).all()
    assert snap[C.LABEL].isin([0, 1]).all()


def test_label_not_degenerate(data):
    """La etiqueta no debe ser ~0%, ~100% ni exactamente 50/50 (indicaría regla trivial)."""
    rate = data["snapshot"][C.LABEL].mean()
    assert 0.15 < rate < 0.55, f"tasa de etiqueta sospechosa: {rate:.3f}"


def test_forbidden_features_not_in_lr_or_if_lists():
    for feat in C.IF_FEATURES + C.LR_FEATURES:
        assert feat not in C.FORBIDDEN_FEATURES, f"{feat} está prohibida y en la lista de features"


def test_generator_state_not_in_snapshot(data):
    forbidden_leak_cols = {"latent_stress_index", "synthetic_situation_truth",
                            "aff_app", "aff_sms", "aff_whatsapp", "aff_call", "hour_star", "days_star"}
    assert forbidden_leak_cols.isdisjoint(set(data["snapshot"].columns))


def test_golden_customers_count_and_situations(data):
    golden = data["golden"]
    assert len(golden) == 14
    counts = golden["golden_expected_situation"].value_counts()
    for sit in ["S0", "S1", "S2", "S3"]:
        assert counts.get(sit, 0) >= 2, f"faltan casos de {sit}"


def test_golden_g02_looks_anomalous_but_should_not_contact(data):
    g02 = data["golden"].set_index("customer_id").loc["GOLD-G02"]
    assert g02["income_variation"] > 1.0          # ingreso extraordinario
    assert g02["golden_expected_intervene"] == False


def test_golden_g12_new_customer_neutral_baseline(data):
    g12 = data["golden"].set_index("customer_id").loc["GOLD-G12"]
    assert g12["baseline_unreliable"] == 1
    assert g12["hist_cycles_available"] == 0


def test_contacts_log_has_required_columns(data):
    contacts = data["contacts"]
    for col in ["channel", "hour_sent", "days_before_due_at_contact", "responded", "outcome"]:
        assert col in contacts.columns
    assert contacts["channel"].isin(C.CHANNELS).all()
    assert contacts["responded"].isin([True, False]).all()


def test_contact_response_correlates_with_customer_affinity(data):
    """La afinidad oculta del cliente hacia el canal usado debe predecir la respuesta.
    (El promedio agregado por canal se cancela porque el canal dominante se asigna
    uniformemente entre clientes; lo que importa es la afinidad propia de cada cliente.)"""
    contacts = data["contacts"].merge(data["gen_state"], on="customer_id", how="left")
    aff_col = {"APP_PUSH": "aff_app", "SMS": "aff_sms", "WHATSAPP": "aff_whatsapp", "CALL": "aff_call"}
    contacts["own_affinity"] = contacts.apply(lambda r: r[aff_col[r["channel"]]], axis=1)
    corr = contacts["own_affinity"].corr(contacts["responded"].astype(float))
    assert corr > 0.15, f"correlación afinidad-respuesta demasiado baja: {corr:.3f}"
