from core.engine.score import (
    composite_score, gap_subscore, ma_subscore, momentum_subscore, oi_subscore,
    pcr_subscore, sr_subscore, structure_subscore,
)


def test_sr_subscore_symmetric_and_bounds():
    assert sr_subscore(100, None, None) == 50.0
    assert sr_subscore(100, None, 110) == 20.0
    assert sr_subscore(100, 90, None) == 80.0
    assert sr_subscore(100, 90, 110) == 50.0   # equidistant -> neutral
    assert sr_subscore(95, 90, 110) > 50.0      # closer to support -> bullish tilt


def test_gap_subscore_bull_and_bear():
    price = 100
    up_gap = [{"direction": "up", "level": 95}]
    dn_gap = [{"direction": "down", "level": 105}]
    assert gap_subscore(price, up_gap) == 62.5
    assert gap_subscore(price, dn_gap) == 37.5
    assert gap_subscore(price, []) == 50.0


def test_pcr_subscore_thresholds():
    assert pcr_subscore(None) == 50.0
    assert pcr_subscore(1.2) == 75.0
    assert pcr_subscore(0.7) == 25.0
    assert pcr_subscore(0.95) == 50.0  # midpoint of the 0.7->1.2 bridge


def test_momentum_subscore_trend_vs_range_regime():
    # trend regime: high RSI stays bullish (momentum continues)
    assert momentum_subscore(80, regime="trend") == 80.0
    # range regime: high RSI inverts to bearish (overbought, due to revert)
    assert momentum_subscore(80, regime="range") == 20.0
    assert momentum_subscore(30, regime="range") == 70.0
    assert momentum_subscore(None) == 50.0


def test_ma_subscore_fraction_above():
    assert ma_subscore(100, {20: 90, 50: 95}) == 100.0   # above both
    assert ma_subscore(100, {20: 110, 50: 95}) == 50.0   # above one of two
    assert ma_subscore(100, {}) == 50.0


def test_oi_subscore_mapping():
    assert oi_subscore("long_buildup") == 75.0
    assert oi_subscore("short_buildup") == 25.0
    assert oi_subscore(None) == 50.0


def test_structure_subscore_mapping():
    assert structure_subscore("uptrend (higher highs, higher lows)") == 70.0
    assert structure_subscore("downtrend (lower highs, lower lows)") == 30.0
    assert structure_subscore("range/unclear structure") == 50.0


def test_composite_score_matches_v1_formula():
    # weights sr=40,gap=25,pcr=20,vix=15; damp vix -> pulls toward 50
    subscores = {"sr": 61.3, "gap": 75.0, "pcr": 37.1}
    weights = {"sr": 40, "gap": 25, "pcr": 20, "vix": 15}
    no_damp = composite_score(subscores, weights, damp_flags={"vix": False})
    damped = composite_score(subscores, weights, damp_flags={"vix": True})
    assert no_damp == 60  # matches the v1 reconciliation value
    assert damped != no_damp
    assert 35 < damped < 65  # damping pulls toward 50, doesn't flip direction
