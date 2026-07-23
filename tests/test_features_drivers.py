import pandas as pd
import pytest

from core.features.drivers import driver_relationship, driver_subscore, pct_corr


def test_pct_corr_perfect_inverse():
    a = pd.Series([100, 110, 99, 108.9])       # returns: +10%, -10%, +10%
    b = pd.Series([100, 90, 99, 89.1])         # returns: -10%, +10%, -10% (exact opposite)
    assert pct_corr(a, b, window=3) == pytest.approx(-1.0)


def test_pct_corr_insufficient_data_is_none():
    assert pct_corr(pd.Series([100, 101]), pd.Series([50, 49]), window=20) is None


def _driver_df(prev_close, latest_close):
    return pd.DataFrame({
        "ts": ["2026-01-01", "2026-01-02"],
        "close": [prev_close, latest_close],
    })


def test_relationship_inverse_driver_down_reads_bullish():
    # e.g. crude falling, historically inverse to Bank Nifty -> bullish implication
    out = driver_relationship("Crude", _driver_df(100, 95), corr_20d=-0.5)
    assert out["relationship"] == "inverse"
    assert out["implication"] == "bullish"
    assert out["change_pct"] == -5.0


def test_relationship_inverse_driver_up_reads_bearish():
    out = driver_relationship("Crude", _driver_df(100, 105), corr_20d=-0.5)
    assert out["implication"] == "bearish"


def test_relationship_weak_correlation_is_neutral():
    out = driver_relationship("USDINR", _driver_df(100, 95), corr_20d=0.1, corr_floor=0.3)
    assert out["implication"] == "neutral"


def test_relationship_tiny_move_is_neutral():
    out = driver_relationship("USDINR", _driver_df(100, 100.01), corr_20d=0.6, chg_floor=0.05)
    assert out["implication"] == "neutral"


def test_relationship_no_correlation_data_is_unclear():
    out = driver_relationship("Crude", _driver_df(100, 95), corr_20d=None)
    assert out["relationship"] == "unclear"
    assert out["implication"] == "neutral"


def test_driver_subscore_nudges():
    assert driver_subscore([]) == 50.0
    assert driver_subscore([{"implication": "bullish"}, {"implication": "bearish"}]) == 50.0
    assert driver_subscore([{"implication": "bullish"}, {"implication": "bullish"}]) == 66.0
    assert driver_subscore([{"implication": "bearish"}], nudge=10) == 40.0
