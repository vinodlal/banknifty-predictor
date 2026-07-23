from core.paper.ledger import (
    get_closed_trades, get_open_trades, open_trade, open_trade_from_signal, settle_trades,
)
from core.paper.scoreboard import compute_scoreboard, scoreboard_by


def test_open_trade_creates_open_row(paper_db):
    tid = open_trade("BANKNIFTY", "future", "Long",
                      {"entry": 100, "stop": 95, "target1": 110, "size": 5},
                      opened_at="2026-01-01T09:00:00+05:30")
    assert tid is not None
    open_trades = get_open_trades()
    assert len(open_trades) == 1
    assert open_trades[0].symbol == "BANKNIFTY"
    assert open_trades[0].status == "open"


def test_open_trade_from_signal_neutral_returns_none(paper_db):
    sig = {"symbol": "X", "kind": "index", "bias": "Neutral", "trade_plan": None}
    assert open_trade_from_signal(sig) is None
    assert get_open_trades() == []


def test_open_trade_from_signal_opens_when_directional(paper_db):
    sig = {
        "symbol": "TCS", "kind": "equity", "bias": "Long", "horizon": "swing",
        "score": 70, "confidence": "high",
        "trade_plan": {"entry": 100, "stop": 95, "target1": 110, "size": 3},
    }
    tid = open_trade_from_signal(sig, strategy="trend")
    assert tid is not None
    t = get_open_trades()[0]
    assert t.predicted_score == 70 and t.predicted_confidence == "high" and t.strategy == "trend"


def test_settle_trades_hits_target(paper_db):
    open_trade("BANKNIFTY", "future", "Long", {"entry": 100, "stop": 95, "target1": 110, "size": 10},
               opened_at="2026-01-01T09:00:00+05:30")
    bar_lookup = {"BANKNIFTY": {"high": 112, "low": 108, "close": 110}}
    closed = settle_trades(bar_lookup, as_of="2026-01-02T15:30:00+05:30")
    assert len(closed) == 1
    t = get_closed_trades()[0]
    assert t.close_reason == "target"
    assert t.r_multiple == 2.0
    assert t.pnl == 100.0
    assert get_open_trades() == []


def test_settle_trades_stop_takes_priority_when_both_touch(paper_db):
    open_trade("BANKNIFTY", "future", "Long", {"entry": 100, "stop": 95, "target1": 110, "size": 10},
               opened_at="2026-01-01T09:00:00+05:30")
    bar_lookup = {"BANKNIFTY": {"high": 115, "low": 90, "close": 112}}  # both touched
    settle_trades(bar_lookup, as_of="2026-01-02T15:30:00+05:30")
    t = get_closed_trades()[0]
    assert t.close_reason == "stop"
    assert t.r_multiple == -1.0
    assert t.pnl == -50.0


def test_settle_trades_time_exit(paper_db):
    open_trade("BANKNIFTY", "future", "Long", {"entry": 100, "stop": 90, "target1": 120, "size": 10},
               opened_at="2026-01-01T09:00:00+05:30")
    bar_lookup = {"BANKNIFTY": {"high": 105, "low": 98, "close": 102}}  # neither touched
    closed = settle_trades(bar_lookup, as_of="2026-01-10T15:30:00+05:30", max_days=3)
    assert len(closed) == 1
    t = get_closed_trades()[0]
    assert t.close_reason == "time_exit"
    assert t.close_price == 102
    assert t.r_multiple == 0.2


def test_settle_trades_does_not_close_before_target_stop_or_time(paper_db):
    open_trade("BANKNIFTY", "future", "Long", {"entry": 100, "stop": 90, "target1": 120, "size": 10},
               opened_at="2026-01-01T09:00:00+05:30")
    bar_lookup = {"BANKNIFTY": {"high": 105, "low": 98, "close": 102}}
    closed = settle_trades(bar_lookup, as_of="2026-01-02T15:30:00+05:30", max_days=10)
    assert closed == []
    assert len(get_open_trades()) == 1


def test_scoreboard_end_to_end_matches_known_values(paper_db):
    # trade1: target hit -> +2.0R; trade2: stop hit -> -1.0R; trade3: target hit -> +1.5R
    open_trade("A", "future", "Long", {"entry": 100, "stop": 95, "target1": 110, "size": 1},
               opened_at="2026-01-01T09:00:00+05:30")
    open_trade("B", "future", "Long", {"entry": 100, "stop": 99, "target1": 105, "size": 1},
               opened_at="2026-01-01T09:00:00+05:30")
    open_trade("C", "future", "Long", {"entry": 100, "stop": 96, "target1": 106, "size": 1},
               opened_at="2026-01-01T09:00:00+05:30")
    settle_trades({"A": {"high": 112, "low": 108, "close": 110}}, as_of="2026-01-02T15:30:00+05:30")
    settle_trades({"B": {"high": 100, "low": 98, "close": 99}}, as_of="2026-01-02T15:30:00+05:30")
    settle_trades({"C": {"high": 107, "low": 105, "close": 106}}, as_of="2026-01-02T15:30:00+05:30")

    out = compute_scoreboard()
    assert out["trades"] == 3
    assert out["win_rate"] == round(2 / 3, 3)
    assert out["avg_r"] == round(2.5 / 3, 3)
    assert out["profit_factor"] == 3.5
    assert out["max_drawdown_r"] == -1.0
    assert out["equity_curve_r"] == [2.0, 1.0, 2.5]


def test_scoreboard_by_strategy_groups_correctly(paper_db):
    open_trade("A", "future", "Long", {"entry": 100, "stop": 95, "target1": 110, "size": 1},
               strategy="trend", opened_at="2026-01-01T09:00:00+05:30")
    open_trade("B", "future", "Long", {"entry": 100, "stop": 95, "target1": 105, "size": 1},
               strategy="mean_reversion", opened_at="2026-01-01T09:00:00+05:30")
    settle_trades({"A": {"high": 112, "low": 108, "close": 110}}, as_of="2026-01-02T15:30:00+05:30")
    settle_trades({"B": {"high": 107, "low": 104, "close": 105}}, as_of="2026-01-02T15:30:00+05:30")

    by_strategy = scoreboard_by("strategy")
    assert set(by_strategy) == {"trend", "mean_reversion"}
    assert by_strategy["trend"]["trades"] == 1
    assert by_strategy["mean_reversion"]["trades"] == 1
