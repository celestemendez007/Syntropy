import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from nba_priority import compute_priority_table, rank_alternatives, GROUP_COLS


def _conv(situation_hint, barrier, channel, offered, accepted, paid, tone="NEUTRAL", turns=3):
    return {"situation_hint": situation_hint, "barrier_detected": barrier, "channel": channel,
            "alternatives_offered": offered, "alternative_accepted": accepted,
            "paid_on_time_after": paid, "tone_overall": tone, "turns_total": turns}


def test_bayesian_smoothing_formula():
    """3 ofrecidas, 2 pagaron a tiempo -> success_rate = (2+1)/(3+2) = 0.6 exacto."""
    rows = [
        _conv("S1", "FORGOT", "CALL", "ALT-A", "ALT-A", True),
        _conv("S1", "FORGOT", "CALL", "ALT-A", "ALT-A", True),
        _conv("S1", "FORGOT", "CALL", "ALT-A", "", False),
    ]
    table = compute_priority_table(pd.DataFrame(rows))
    row = table[table["alt_id"] == "ALT-A"].iloc[0]
    assert row["n_offered"] == 3
    assert row["n_accepted"] == 2
    assert row["n_paid_on_time_after"] == 2
    assert row["success_rate"] == pytest.approx(0.6, abs=1e-9)


def test_no_evidence_gives_neutral_prior_score():
    """1 ofrecida, ninguna aceptada -> success_rate = (0+1)/(1+2) = 1/3, no 0."""
    rows = [_conv("S2", "DATE_MISMATCH", "SMS", "ALT-B", "", False)]
    table = compute_priority_table(pd.DataFrame(rows))
    row = table[table["alt_id"] == "ALT-B"].iloc[0]
    assert row["success_rate"] == pytest.approx(1 / 3, abs=1e-4)


def test_empty_conversations_returns_empty_table():
    table = compute_priority_table(pd.DataFrame(columns=["situation_hint", "barrier_detected", "channel",
                                                          "alternatives_offered", "alternative_accepted",
                                                          "paid_on_time_after", "tone_overall", "turns_total"]))
    assert table.empty
    assert list(table.columns[:4]) == GROUP_COLS


def test_missing_alternatives_offered_does_not_produce_nan_alt_id():
    """Regresión: un campo vacío en CSV se lee como NaN, no como string vacío;
    `nan or ''` es verdadero en Python y colaba un alt_id literal 'nan'."""
    rows = [_conv("S1", "ALREADY_PAID", "SMS", None, None, False),
            _conv("S1", "FORGOT", "CALL", "ALT-A", "ALT-A", True)]
    table = compute_priority_table(pd.DataFrame(rows))
    assert "nan" not in table["alt_id"].astype(str).values


def test_rank_alternatives_orders_by_learned_success_rate(monkeypatch):
    rows = [
        _conv("S1", "FORGOT", "CALL", "ALT-LOW", "", False),
        _conv("S1", "FORGOT", "CALL", "ALT-LOW", "", False),
        _conv("S1", "FORGOT", "CALL", "ALT-HIGH", "ALT-HIGH", True),
        _conv("S1", "FORGOT", "CALL", "ALT-HIGH", "ALT-HIGH", True),
        _conv("S1", "FORGOT", "CALL", "ALT-HIGH", "ALT-HIGH", True),
    ]
    table = compute_priority_table(pd.DataFrame(rows))
    import nba_priority
    monkeypatch.setattr(nba_priority, "_priority_table_cache", table)

    eligible = [{"alt_id": "ALT-LOW"}, {"alt_id": "ALT-HIGH"}]
    ranked = rank_alternatives(eligible, "S1", "CALL")
    assert [a["alt_id"] for a in ranked] == ["ALT-HIGH", "ALT-LOW"]


def test_rank_alternatives_never_drops_an_alternative(monkeypatch):
    """Sin evidencia para una combinación, debe quedar con el prior neutro, no
    desaparecer de la lista."""
    import nba_priority
    monkeypatch.setattr(nba_priority, "_priority_table_cache", pd.DataFrame(columns=GROUP_COLS + ["success_rate"]))
    eligible = [{"alt_id": "ALT-X"}, {"alt_id": "ALT-Y"}]
    ranked = rank_alternatives(eligible, "S9", "UNKNOWN_CHANNEL")
    assert {a["alt_id"] for a in ranked} == {"ALT-X", "ALT-Y"}
