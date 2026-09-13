import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/ml')))
from channel_timing_engine import (get_channel_preference, get_timing, get_channel_and_timing,
                                    load_dataset, load_contacts, CHANNELS, DEFAULT_CHANNEL, CHANNEL_CONF_MIN)


def test_contacts_log_loads():
    df = load_contacts()
    assert len(df) > 100
    assert {"customer_id", "channel", "responded", "hour_sent", "days_before_due_at_contact"} <= set(df.columns)


def test_channel_preference_always_resolves_to_real_channel():
    df = load_dataset()
    for cid in df["customer_id"].iloc[:20]:
        result = get_channel_preference(cid)
        assert result["channel_used"] in CHANNELS
        if result["channel_pref_model"] == "UNDETERMINED":
            assert result["channel_used"] == DEFAULT_CHANNEL
            assert result["channel_source"] == "FALLBACK_CALL"
        else:
            assert result["channel_pref_confidence"] >= CHANNEL_CONF_MIN


def test_timing_returns_valid_window():
    df = load_dataset()
    sample_id = df["customer_id"].iloc[0]
    timing = get_timing(sample_id)
    assert "-" in timing["best_hour_window"]
    assert 1 <= timing["best_days_before_due"] <= 15
    assert 0 <= timing["timing_confidence"] <= 1


def test_get_channel_and_timing_merges_both_contracts():
    df = load_dataset()
    sample_id = df["customer_id"].iloc[0]
    combined = get_channel_and_timing(sample_id)
    for key in ["channel_pref_model", "channel_pref_confidence", "channel_used", "channel_source",
                "best_hour_window", "best_days_before_due", "timing_confidence"]:
        assert key in combined


def test_golden_g09_low_digital_response_falls_back_to_call():
    """G09 (contact_response_rate=0, baja respuesta digital) no debe generar
    confianza suficiente en ningún canal del modelo -- debe caer al fallback CALL,
    el caso de diseño que el golden customer prueba (v1 §9)."""
    result = get_channel_preference("GOLD-G09")
    assert result["channel_used"] == "CALL"
    assert result["channel_pref_confidence"] < CHANNEL_CONF_MIN


def test_unknown_customer_still_falls_back_gracefully():
    result = get_channel_preference("NO_EXISTE_9999")
    assert result["channel_used"] == DEFAULT_CHANNEL
    assert result["channel_source"] == "FALLBACK_CALL"
