from core.engine.stock import analyze_stock, btst_verdict, holding_guidance
from tests.conftest import make_df


def _last_bar_df(o, h, l, c):
    return make_df([{"o": o, "h": h, "l": l, "c": c},
                     {"o": o, "h": h, "l": l, "c": c}])


def test_holding_guidance_mentions_levels_by_bias():
    long_msg = holding_guidance("Long", 100, support=90, resistance=110)
    assert "110" in long_msg and "bullish" in long_msg.lower()
    short_msg = holding_guidance("Short", 100, support=90, resistance=110)
    assert "90" in short_msg and "bearish" in short_msg.lower()
    neutral_msg = holding_guidance("Neutral", 100, support=90, resistance=110)
    assert "neutral" in neutral_msg.lower()


def test_btst_buy_on_strong_bullish_close():
    df = _last_bar_df(o=104, h=110, l=100, c=108)  # closed at 80% of the day's range
    out = btst_verdict(df, bias="Long")
    assert out["verdict"] == "Buy"


def test_btst_sell_on_weak_bearish_close():
    df = _last_bar_df(o=105, h=110, l=100, c=101)  # closed at 10% of the day's range
    out = btst_verdict(df, bias="Short")
    assert out["verdict"] == "Sell (BTST short)"


def test_btst_avoids_weak_confluence():
    df = _last_bar_df(o=104, h=110, l=100, c=103)  # closed mid-range, not strong
    out = btst_verdict(df, bias="Long")
    assert out["verdict"] == "Avoid"


def test_btst_avoids_on_upcoming_event_regardless_of_setup():
    df = _last_bar_df(o=104, h=110, l=100, c=108)  # would otherwise be a Buy
    out = btst_verdict(df, bias="Long", event_soon=True)
    assert out["verdict"] == "Avoid"
    assert "event" in out["reason"].lower()


def _uptrend_df(n=60, start=100.0, step=1.0):
    closes = [start + i * step for i in range(n)]
    rows = [{"o": c - 0.3, "h": c + 0.5, "l": c - 0.6, "c": c} for c in closes]
    return make_df(rows)


def test_analyze_stock_holding_with_futures():
    df = _uptrend_df()
    sig = analyze_stock("TESTSTK", df, has_futures=True, is_holding=True)
    assert sig["is_holding"] is True
    assert sig["has_futures"] is True
    assert "holding" in sig["strategies"]
    assert "btst" in sig["strategies"]
    if sig["bias"] != "Neutral":
        assert sig["strategies"]["futures"] is not None
        assert sig["strategies"]["futures"]["risk_reward"] >= 2.0


def test_analyze_stock_no_futures_no_holding():
    df = _uptrend_df()
    sig = analyze_stock("TESTSTK2", df, has_futures=False, is_holding=False)
    assert sig["has_futures"] is False
    assert sig["strategies"]["futures"] is None
    assert "holding" not in sig["strategies"]
