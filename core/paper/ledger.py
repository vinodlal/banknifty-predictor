"""Virtual-trade ledger: open a paper trade from a Signal's trade plan, then
settle it daily against real bars (target/stop/time-exit)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .db import PaperTrade, get_session

IST = ZoneInfo("Asia/Kolkata")


def open_trade(symbol: str, kind: str, bias: str, trade_plan: dict, *,
                horizon: str = "swing", strategy: str | None = None,
                predicted_score: int | None = None,
                predicted_confidence: str | None = None,
                opened_at: str | None = None) -> int:
    """Opens a virtual trade from a trade_plan dict (entry/stop/target1/size).
    Returns the new trade's id."""
    opened_at = opened_at or datetime.now(IST).isoformat()
    s = get_session()
    try:
        t = PaperTrade(
            symbol=symbol, kind=kind, horizon=horizon, strategy=strategy, bias=bias,
            opened_at=opened_at, entry=trade_plan["entry"], stop=trade_plan["stop"],
            target1=trade_plan["target1"], target2=trade_plan.get("target2"),
            size=trade_plan.get("size", 0), predicted_score=predicted_score,
            predicted_confidence=predicted_confidence, status="open",
        )
        s.add(t)
        s.commit()
        s.refresh(t)
        return t.id
    finally:
        s.close()


def open_trade_from_signal(sig: dict, *, strategy: str | None = None) -> int | None:
    """Convenience: opens a trade from a Signal dict's trade_plan (futures.py/
    stock.py output). Returns None if bias is Neutral (no trade plan exists)."""
    plan = sig.get("trade_plan") or (sig.get("strategies") or {}).get("futures")
    if not plan or sig["bias"] == "Neutral":
        return None
    return open_trade(
        sig["symbol"], sig["kind"], sig["bias"], plan,
        horizon=sig.get("horizon", "swing"), strategy=strategy,
        predicted_score=sig.get("score"), predicted_confidence=sig.get("confidence"),
    )


def get_open_trades(symbol: str | None = None) -> list[PaperTrade]:
    s = get_session()
    try:
        stmt = select(PaperTrade).where(PaperTrade.status == "open")
        if symbol:
            stmt = stmt.where(PaperTrade.symbol == symbol)
        return list(s.scalars(stmt))
    finally:
        s.close()


def get_closed_trades(symbol: str | None = None, strategy: str | None = None,
                       horizon: str | None = None) -> list[PaperTrade]:
    s = get_session()
    try:
        stmt = select(PaperTrade).where(PaperTrade.status == "closed")
        if symbol:
            stmt = stmt.where(PaperTrade.symbol == symbol)
        if strategy:
            stmt = stmt.where(PaperTrade.strategy == strategy)
        if horizon:
            stmt = stmt.where(PaperTrade.horizon == horizon)
        return list(s.scalars(stmt.order_by(PaperTrade.closed_at)))
    finally:
        s.close()


def _r_and_pnl(trade: PaperTrade, close_price: float) -> tuple[float | None, float | None]:
    risk = abs(trade.entry - trade.stop)
    reward = (close_price - trade.entry) if trade.bias == "Long" else (trade.entry - close_price)
    r = round(reward / risk, 3) if risk else None
    pnl = round(reward * trade.size, 2) if trade.size else round(reward, 2)
    return r, pnl


def settle_trades(bar_lookup: dict[str, dict], *, as_of: str | None = None,
                   max_days: int = 10) -> list[int]:
    """bar_lookup: {symbol: {"high":, "low":, "close":, "date": "YYYY-MM-DD"}}
    for the settlement day. Closes any open trade whose target/stop is
    touched today (stop takes priority if both touch the same day — the
    conservative assumption used consistently in core.backtest.harness too),
    or that has been open >= max_days (closes at today's price, time exit).
    Returns the ids of trades closed this call."""
    as_of = as_of or datetime.now(IST).isoformat()
    as_of_date = datetime.fromisoformat(as_of).date()
    closed_ids: list[int] = []

    s = get_session()
    try:
        open_trades = list(s.scalars(select(PaperTrade).where(PaperTrade.status == "open")))
        for t in open_trades:
            bar = bar_lookup.get(t.symbol)
            if not bar:
                continue
            hi, lo, close = bar["high"], bar["low"], bar["close"]
            hit_stop = lo <= t.stop if t.bias == "Long" else hi >= t.stop
            hit_target = hi >= t.target1 if t.bias == "Long" else lo <= t.target1
            opened_date = datetime.fromisoformat(t.opened_at).date()
            days_open = (as_of_date - opened_date).days

            if hit_stop:
                r, pnl = _r_and_pnl(t, t.stop)
                reason, price = "stop", t.stop
            elif hit_target:
                r, pnl = _r_and_pnl(t, t.target1)
                reason, price = "target", t.target1
            elif days_open >= max_days:
                r, pnl = _r_and_pnl(t, close)
                reason, price = "time_exit", close
            else:
                continue

            t.status, t.closed_at, t.close_price = "closed", as_of, price
            t.close_reason, t.r_multiple, t.pnl = reason, r, pnl
            closed_ids.append(t.id)
        s.commit()
    finally:
        s.close()
    return closed_ids
