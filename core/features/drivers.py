"""Cross-asset driver correlations (Crude, USD/INR, ...) and day-over-day
relationship reads. Ported/generalized from v1 scripts/analysis_engine.py
(_pct_corr + the per-driver relationship builder), which this engine never
carried over until now — see the M5 follow-up that added this module.
"""
from __future__ import annotations

import pandas as pd


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def align_by_date(target_df: pd.DataFrame, driver_df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Align two OHLCV frames on calendar date (not raw row position) before
    correlating — different instruments (e.g. NSE index vs. a commodity/FX
    proxy) can trade on different calendars, so positional alignment would
    silently pair the wrong days together."""
    t = target_df.assign(d=pd.to_datetime(target_df["ts"]).dt.date).set_index("d")["close"]
    d = driver_df.assign(d=pd.to_datetime(driver_df["ts"]).dt.date).set_index("d")["close"]
    joined = pd.concat([t.rename("target"), d.rename("driver")], axis=1, join="inner").sort_index()
    return joined["target"], joined["driver"]


def pct_corr(a: pd.Series, b: pd.Series, window: int) -> float | None:
    """Pearson correlation of daily % changes over the trailing `window` days."""
    pair = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(pair) < 3:
        return None
    pct = pair.pct_change().dropna().tail(window)
    if len(pct) < 3:
        return None
    c = pct["a"].corr(pct["b"])
    return None if pd.isna(c) else round(float(c), 3)


def driver_relationship(name: str, driver_df: pd.DataFrame, corr_20d: float | None,
                         corr_floor: float = 0.3, chg_floor: float = 0.05) -> dict | None:
    """How did the driver move day-over-day, and — given its correlation with
    the target — what does that imply for the target (bullish/bearish/neutral)?
    Weak correlation or a negligible move both collapse to 'neutral' (too
    little signal to act on), matching v1's exact thresholds."""
    if len(driver_df) < 2:
        return None
    prev, latest = driver_df.iloc[-2], driver_df.iloc[-1]
    if not prev["close"]:
        return None
    chg = (latest["close"] - prev["close"]) / prev["close"] * 100
    if corr_20d is None:
        relationship, implication = "unclear", "neutral"
    elif abs(corr_20d) < corr_floor or abs(chg) < chg_floor:
        relationship = "inverse" if corr_20d < 0 else "direct"
        implication = "neutral"
    else:
        relationship = "inverse" if corr_20d < 0 else "direct"
        direction = (1 if chg > 0 else -1) * (1 if corr_20d > 0 else -1)
        implication = "bullish" if direction > 0 else "bearish"
    return {
        "name": name, "prev_date": str(prev["ts"]), "prev": round(float(prev["close"]), 2),
        "date": str(latest["ts"]), "value": round(float(latest["close"]), 2),
        "change_pct": round(chg, 2), "corr_20d": corr_20d,
        "relationship": relationship, "implication": implication,
    }


def driver_subscore(relationships: list[dict], nudge: float = 8.0) -> float:
    """Each non-neutral driver nudges the read; ports v1's additive-nudge
    style (used for gaps) rather than a raw average, so one strong driver
    read isn't diluted by several silent/neutral ones."""
    score = 50.0
    for r in relationships:
        if r["implication"] == "bullish":
            score += nudge
        elif r["implication"] == "bearish":
            score -= nudge
    return _clamp(score)
