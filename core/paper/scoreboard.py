"""Paper-trading scoreboard: win rate, expectancy, profit factor, drawdown,
equity curve — overall and broken down by strategy/symbol/horizon."""
from __future__ import annotations

from .db import PaperTrade
from .ledger import get_closed_trades


def compute_scoreboard(trades: list[PaperTrade] | None = None) -> dict:
    trades = trades if trades is not None else get_closed_trades()
    r_values = [t.r_multiple for t in trades if t.r_multiple is not None]
    wins = [r for r in r_values if r > 0]
    losses = [r for r in r_values if r <= 0]

    win_rate = len(wins) / len(r_values) if r_values else None
    avg_r = sum(r_values) / len(r_values) if r_values else None
    profit_factor = (sum(wins) / abs(sum(losses))
                      if losses and sum(losses) != 0 else None)

    equity, cum, peak, max_dd = [], 0.0, float("-inf"), 0.0
    for r in r_values:
        cum += r
        equity.append(round(cum, 2))
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    return {
        "trades": len(r_values),
        "win_rate": round(win_rate, 3) if win_rate is not None else None,
        "avg_r": round(avg_r, 3) if avg_r is not None else None,
        "expectancy_r": round(avg_r, 3) if avg_r is not None else None,
        "profit_factor": round(profit_factor, 3) if profit_factor is not None else None,
        "max_drawdown_r": round(max_dd, 2),
        "equity_curve_r": equity,
    }


def scoreboard_by(field: str) -> dict[str, dict]:
    """Break down the scoreboard by 'strategy', 'symbol', or 'horizon'."""
    groups: dict[str, list[PaperTrade]] = {}
    for t in get_closed_trades():
        key = getattr(t, field, None) or "unknown"
        groups.setdefault(key, []).append(t)
    return {k: compute_scoreboard(v) for k, v in groups.items()}
