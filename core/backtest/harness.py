"""Walk-forward backtest harness.

For each day t, the signal is computed using ONLY data available through day t
(no lookahead), then graded against what actually happened next. Reuses
core.engine.signal.analyze() directly — the exact same function used live —
so backtest results are a genuine measure of the live engine's behaviour.

Scope note: PCR/OI factors need point-in-time option-chain snapshots that
Kite's REST API cannot reconstruct for arbitrary past dates (it only exposes
the live chain). BACKTEST_WEIGHTS therefore excludes "pcr"/"oi" and reweights
the factors that ARE reconstructable from historical OHLC (S/R, gaps,
momentum, MA stack, structure, VIX, and now cross-asset drivers like
Crude/USD-INR/Nasdaq — those DO have deep public daily history via
PublicProvider, unlike options data). PCR/OI are fully live in production
(signal.py/futures.py) and will be exercised going forward by the M6
paper-trading ledger, which needs no historical reconstruction.
"""
from __future__ import annotations

import pandas as pd

from ..engine import signal as signal_mod
from ..features import momentum as momentum_mod
from ..trade_plan.plan import build_trade_plan

BACKTEST_WEIGHTS = {"sr": 20, "gap": 12, "momentum": 16, "ma": 16, "structure": 16,
                     "drivers": 16, "vix": 10}

OUTLIER_MIN_MOVE_PCT = 3.0
OUTLIER_VOL_MULT = 2.0


def _realized_vol_pct(closes: pd.Series, window: int = 20) -> float:
    tail = closes.iloc[-(window + 1):]
    if len(tail) < 3:
        return 0.0
    rets = tail.pct_change().dropna()
    return float(rets.std() * 100)


def _is_outlier(move_pct: float, closes_so_far: pd.Series) -> bool:
    vol = _realized_vol_pct(closes_so_far)
    threshold = max(OUTLIER_MIN_MOVE_PCT, OUTLIER_VOL_MULT * vol)
    return abs(move_pct) > threshold


def _simulate_trade_outcome(df: pd.DataFrame, t: int, plan: dict, max_days: int = 10) -> float | None:
    """Walk forward day-by-day from t+1: whichever of stop/target is touched
    first wins; if both touch the same day, conservatively assume stop first;
    if neither within max_days, close out at the last available price."""
    entry, stop, target = plan["entry"], plan["stop"], plan["target1"]
    risk = abs(entry - stop)
    if risk == 0:
        return None
    bias = plan["bias"]
    end = min(len(df), t + 1 + max_days)
    if end <= t + 1:
        return None
    for i in range(t + 1, end):
        hi, lo = df["high"].iloc[i], df["low"].iloc[i]
        hit_target = hi >= target if bias == "Long" else lo <= target
        hit_stop = lo <= stop if bias == "Long" else hi >= stop
        if hit_stop:
            return -1.0
        if hit_target:
            reward = (target - entry) if bias == "Long" else (entry - target)
            return round(reward / risk, 2)
    last_close = df["close"].iloc[end - 1]
    reward = (last_close - entry) if bias == "Long" else (entry - last_close)
    return round(reward / risk, 2)


def walk_forward(symbol: str, df: pd.DataFrame, vix_df: pd.DataFrame | None = None, *,
                  drivers: dict[str, pd.DataFrame] | None = None,
                  kind: str = "index", weights: dict | None = None,
                  min_window: int = 210, horizon_days: int = 1,
                  trade_max_days: int = 10) -> list[dict]:
    weights = weights or BACKTEST_WEIGHTS
    rows = []
    for t in range(min_window, len(df) - horizon_days):
        hist = df.iloc[:t + 1].reset_index(drop=True)
        cur_date = hist["ts"].iloc[-1]
        vix_hist = None
        if vix_df is not None:
            v = vix_df[vix_df["ts"] <= cur_date]
            vix_hist = v.reset_index(drop=True) if len(v) >= 4 else None

        drivers_hist = None
        if drivers:
            drivers_hist = {}
            for dname, ddf in drivers.items():
                dv = ddf[ddf["ts"] <= cur_date]
                if len(dv) >= 4:
                    drivers_hist[dname] = dv.reset_index(drop=True)

        sig = signal_mod.analyze(symbol, kind, hist, vix_df=vix_hist, drivers=drivers_hist,
                                  weights=weights)

        now_close = float(df["close"].iloc[t])
        future_close = float(df["close"].iloc[t + horizon_days])
        move_pct = (future_close - now_close) / now_close * 100

        directional_correct = None
        if sig["bias"] == "Long":
            directional_correct = move_pct > 0
        elif sig["bias"] == "Short":
            directional_correct = move_pct < 0

        r_multiple = None
        if sig["bias"] != "Neutral":
            atr_val = momentum_mod.atr(hist).iloc[-1]
            atr_val = float(atr_val) if pd.notna(atr_val) else now_close * 0.01
            plan = build_trade_plan(sig["bias"], price=now_close,
                                     support=sig["levels"]["support"],
                                     resistance=sig["levels"]["resistance"], atr_val=atr_val)
            if plan:
                r_multiple = _simulate_trade_outcome(df, t, plan, max_days=trade_max_days)

        outlier = _is_outlier(move_pct, df["close"].iloc[:t + 1])

        rows.append({
            "date": str(cur_date), "score": sig["score"], "bias": sig["bias"],
            "confidence": sig["confidence"], "close": round(now_close, 2),
            "next_close": round(future_close, 2), "move_pct": round(move_pct, 3),
            "directional_correct": directional_correct, "r_multiple": r_multiple,
            "outlier": outlier,
        })
    return rows
