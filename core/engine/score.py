"""Confluence scoring: per-factor 0-100 sub-scores + a weighted composite.

sr_subscore/gap_subscore/pcr_subscore and the composite formula are ported
exactly from v1 scripts/analysis_engine.py so the engine reconciles against
v1's recorded output (see tests/test_engine_reconciliation.py) before new
factors (momentum, MA stack, OI, structure) are layered on top.
"""
from __future__ import annotations


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# -- ported v1 sub-scores -----------------------------------------------------
def sr_subscore(price: float, support: float | None, resistance: float | None) -> float:
    if support is None and resistance is None:
        return 50.0
    if support is None:
        return 20.0
    if resistance is None:
        return 80.0
    ds, dr = abs(price - support), abs(resistance - price)
    if ds + dr == 0:
        return 50.0
    return _clamp(50 + 50 * (dr - ds) / (ds + dr))


def gap_subscore(price: float, gaps: list[dict]) -> float:
    score = 50.0
    for g in gaps:
        if g["direction"] == "up" and g["level"] < price:
            score += 12.5
        elif g["direction"] == "down" and g["level"] > price:
            score -= 12.5
    return _clamp(score)


def pcr_subscore(pcr: float | None) -> float:
    if pcr is None:
        return 50.0
    if pcr >= 1.2:
        return _clamp(75 + (pcr - 1.2) * 50)
    if pcr <= 0.7:
        return _clamp(25 - (0.7 - pcr) * 50)
    return _clamp(25 + (pcr - 0.7) / 0.5 * 50)


# -- new sub-scores (confluence factors beyond v1) ----------------------------
def momentum_subscore(rsi: float | None, regime: str = "trend") -> float:
    """RSI's correct READING depends on regime, not just its value:
    - trend regime: high RSI = strong momentum = bullish continuation (as-is).
    - range regime: high RSI = overbought = due to revert = bearish, and vice
      versa — the mean-reversion interpretation, via a straight inversion.
    Using the trend-following read unconditionally (the pre-fix behaviour)
    is backwards in a range market and was a likely contributor to the ~50%
    directional accuracy measured in the M4 backtest."""
    if rsi is None:
        return 50.0
    if regime == "range":
        return _clamp(100 - rsi)
    return _clamp(rsi)


def ma_subscore(price: float, ma_values: dict[int, float | None]) -> float:
    valid = {w: v for w, v in ma_values.items() if v is not None}
    if not valid:
        return 50.0
    above = sum(1 for v in valid.values() if price >= v)
    return _clamp(above / len(valid) * 100)


def oi_subscore(buildup_label: str | None) -> float:
    mapping = {"long_buildup": 75.0, "short_covering": 65.0,
               "short_buildup": 25.0, "long_unwinding": 35.0, "neutral": 50.0}
    return mapping.get(buildup_label, 50.0)


def structure_subscore(structure_label: str) -> float:
    if "uptrend" in structure_label:
        return 70.0
    if "downtrend" in structure_label:
        return 30.0
    return 50.0


# -- composite -----------------------------------------------------------------
def composite_score(subscores: dict[str, float], weights: dict[str, float],
                     damp_flags: dict[str, bool] | None = None,
                     damp_keys: tuple[str, ...] = ("vix",)) -> int:
    """Weighted average of active (non-damping) sub-scores, then damping
    factors (e.g. VIX caution) pull the result toward 50 without flipping
    direction — exactly v1's behaviour, generalized to arbitrary factors."""
    damp_flags = damp_flags or {}
    active = {k: w for k, w in weights.items() if k in subscores and k not in damp_keys}
    denom = sum(active.values()) or 1
    base = sum(weights[k] * subscores[k] for k in active) / denom
    damp_weight = sum(weights.get(k, 0) for k in damp_keys if damp_flags.get(k))
    if damp_weight:
        base = 50 + (base - 50) * (1 - damp_weight / 100.0)
    return int(round(_clamp(base)))
