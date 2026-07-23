"""Stock desk: the base signal plus three distinct strategies —
holding/delivery guidance, a futures trade plan (if the stock has F&O), and a
BTST (buy-today-sell-tomorrow) verdict. Pure function — data passed in."""
from __future__ import annotations

import pandas as pd

from ..features import momentum as momentum_mod
from ..trade_plan.plan import build_trade_plan
from . import signal as signal_mod


def holding_guidance(bias: str, price: float, support: float, resistance: float) -> str:
    if bias == "Long":
        return (f"Bias bullish. Consider trimming into strength toward {resistance:,.2f}; "
                f"key support {support:,.2f} — reassess on a daily close below it.")
    if bias == "Short":
        return (f"Bias bearish. Watch support {support:,.2f} closely; a daily close below "
                f"it would strengthen the case to reduce or exit the position.")
    return (f"Bias neutral. Range {support:,.2f}–{resistance:,.2f} — no strong signal "
            f"either way; hold and monitor.")


def btst_verdict(df: pd.DataFrame, bias: str, event_soon: bool = False) -> dict:
    """BTST needs a strong directional bias AND a strong close in that
    direction's favour (the classic 'closed near the high on a bullish day'
    momentum setup) — and no near-term event risk."""
    last = df.iloc[-1]
    rng = max(last["high"] - last["low"], 1e-9)
    close_pos_pct = (last["close"] - last["low"]) / rng * 100  # 100 = closed at the high

    if event_soon:
        return {"verdict": "Avoid", "reason": "Upcoming event (results/corporate action) — "
                                               "event risk too high for an overnight BTST hold."}
    if bias == "Long" and close_pos_pct >= 70:
        return {"verdict": "Buy", "reason": f"Bullish bias with a strong close near the day's "
                                             f"high ({close_pos_pct:.0f}% of the day's range)."}
    if bias == "Short" and close_pos_pct <= 30:
        return {"verdict": "Sell (BTST short)", "reason": f"Bearish bias with a weak close "
                                                            f"near the day's low ({close_pos_pct:.0f}% of range)."}
    return {"verdict": "Avoid", "reason": "No strong bias + strong-close confluence for a "
                                           "BTST setup."}


def analyze_stock(symbol: str, df: pd.DataFrame, *,
                   vix_df: pd.DataFrame | None = None,
                   drivers: dict[str, pd.DataFrame] | None = None,
                   has_futures: bool = False,
                   future_quote: dict | None = None,
                   is_holding: bool = False,
                   event_soon: bool = False,
                   weights: dict | None = None,
                   capital: float = 100_000, risk_pct: float = 1.0) -> dict:
    sig = signal_mod.analyze(symbol, kind="equity", df=df, vix_df=vix_df, drivers=drivers,
                              weights=weights)

    atr_series = momentum_mod.atr(df)
    atr_val = float(atr_series.iloc[-1]) if pd.notna(atr_series.iloc[-1]) else sig["price"] * 0.01

    strategies: dict = {}
    if is_holding:
        strategies["holding"] = holding_guidance(
            sig["bias"], sig["price"], sig["levels"]["support"], sig["levels"]["resistance"])

    if has_futures:
        fut_price = future_quote["last_price"] if future_quote else sig["price"]
        strategies["futures"] = build_trade_plan(
            sig["bias"], price=fut_price, support=sig["levels"]["support"],
            resistance=sig["levels"]["resistance"], atr_val=atr_val,
            capital=capital, risk_pct=risk_pct)
    else:
        strategies["futures"] = None

    strategies["btst"] = btst_verdict(df, sig["bias"], event_soon=event_soon)

    sig["is_holding"] = is_holding
    sig["has_futures"] = has_futures
    sig["strategies"] = strategies
    return sig
