import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from build_synthetic_conversations import generate, write_csvs, TRUE_ACCEPTANCE_PROB


SAMPLE_N = 150


@pytest.fixture(scope="module")
def data():
    return generate(n_customers=SAMPLE_N, seed=1)


def test_generates_interventions_for_every_sampled_customer(data):
    interventions, _ = data
    assert len(interventions) == SAMPLE_N


def test_no_contact_decisions_are_recorded_not_dropped(data):
    """La métrica 'sabe cuándo no molestar' depende de que NO_CONTACT también
    quede en interventions_log, no solo las intervenciones reales."""
    interventions, _ = data
    decisions = {i["decision"] for i in interventions}
    assert "NO_CONTACT" in decisions
    assert "INTERVENE" in decisions


def test_conversations_only_exist_for_intervened_customers(data):
    interventions, conversations = data
    intervened_ids = {i["intervention_id"] for i in interventions if i["decision"] == "INTERVENE"}
    conversation_ids = {c["intervention_id"] for c in conversations}
    assert conversation_ids <= intervened_ids


def test_human_only_alternatives_only_offered_on_escalation(data):
    _, conversations = data
    for c in conversations:
        offered = c["alternatives_offered"].split(";") if c["alternatives_offered"] else []
        if "ALT-PAYMENT-PLAN" in offered:
            assert c["escalation_triggered"] is True


def test_accepted_alternative_is_always_among_offered(data):
    _, conversations = data
    for c in conversations:
        if c["alternative_accepted"]:
            offered = c["alternatives_offered"].split(";")
            assert c["alternative_accepted"] in offered


def test_reproducible_with_same_seed():
    iv1, cv1 = generate(n_customers=60, seed=42)
    iv2, cv2 = generate(n_customers=60, seed=42)
    assert iv1 == iv2
    assert cv1 == cv2


def test_write_csvs_produces_readable_files():
    import pandas as pd
    iv_path, cv_path = write_csvs(n_customers=100, seed=1)
    iv_df = pd.read_csv(iv_path)
    cv_df = pd.read_csv(cv_path)
    assert len(iv_df) == 100
    assert set(TRUE_ACCEPTANCE_PROB.keys()) & set(";".join(cv_df["alternatives_offered"].dropna()).split(";"))
