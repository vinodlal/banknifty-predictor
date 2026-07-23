"""The integrative signal: confluence score + bias + confidence + reasons for
any instrument (index, future, or stock), on the standardized OHLCV DataFrame.

Pure function of its inputs — no file/network I/O — so the backtester (M4) and
paper-trading ledger (M6) can replay it identically to live use.
"""
from __future__ import annotations

import pandas as pd

from ..features import drivers as drivers_mod
from ..features import gaps as gaps_mod
from ..features import levels, moving_avg, options as options_mod, price_action
from ..features import momentum as momentum_mod
from . import decision, regime
from . import score as score_mod

DISCLAIMER = "Educational/informational only. Not SEBI-registered investment advice."

DEFAULT_WEIGHTS = {
    "sr": 20, "gap": 12, "pcr": 13, "momentum": 13, "ma": 13, "structure": 13,
    "drivers": 16, "vix": 10,
}
DEFAULT_FUTURES_WEIGHTS = {
    "sr": 18, "gap": 8, "pcr": 14, "momentum": 8, "ma": 8, "structure": 8,
    "oi": 14, "drivers": 14, "vix": 8,
}

_FACTOR_LABELS = {
    "sr": "Price near support/resistance", "gap": "Unfilled gap positioning",
    "pcr": "Option PCR positioning", "momentum": "RSI momentum",
    "ma": "Price vs. moving-average stack", "structure": "Swing structure (HH/HL vs LH/LL)",
    "oi": "Futures OI build-up", "drivers": "Crude/USD-INR driver correlation",
}


def _reasons(subscores: dict[str, float], weights: dict[str, float], bias: str,
             extra: list[str] | None = None, max_reasons: int = 5) -> list[str]:
    """`extra` (regime context, VIX caution) leads — it explains how the
    factor scores below should be READ (e.g. RSI is mean-reversion in a range
    regime) — so it must never be truncated off the end by max_reasons."""
    ranked = sorted(
        ((k, v) for k, v in subscores.items() if k in weights),
        key=lambda kv: abs(kv[1] - 50), reverse=True,
    )
    out = list(extra or [])
    for k, v in ranked:
        if abs(v - 50) < 5:
            continue
        direction = "bullish" if v > 50 else "bearish"
        out.append(f"{_FACTOR_LABELS.get(k, k)}: {direction} ({v:.0f}/100)")
    return out[:max_reasons]


def analyze(symbol: str, kind: str, df: pd.DataFrame, *,
            vix_df: pd.DataFrame | None = None,
            drivers: dict[str, pd.DataFrame] | None = None,
            option_chain: dict | None = None,
            oi_buildup: str | None = None,
            horizon: str = "swing",
            weights: dict[str, float] | None = None) -> dict:
    """kind: 'index' | 'future' | 'equity'. df must have >= ~30 rows for a
    meaningful MA/RSI/structure read; pivots/gaps work with fewer.

    `drivers` is an arbitrary {name: OHLCV DataFrame} map of macro/cross-asset
    series to correlate against — the SET of relevant drivers differs by
    sector (Bank Nifty cares about Crude/USD-INR; IT stocks care about
    Nasdaq/semiconductor-index/KOSPI) — see core.universe.drivers_for(sector)
    for the config-driven mapping. The correlation strength itself is always
    recomputed on a trailing window each call, so it adapts automatically as
    relationships strengthen/weaken over time; discovering NEW candidate
    drivers (vs. reading configured ones) is not yet automated — see the
    note in core/universe.py's SECTOR_DRIVERS."""
    weights = weights or (DEFAULT_FUTURES_WEIGHTS if kind == "future" else DEFAULT_WEIGHTS)
    last = df.iloc[-1]
    price = float(last["close"])

    piv = levels.pivot_levels(last["high"], last["low"], last["close"])
    sh, sl = levels.swing_points(df)
    level_set = [piv["r1"], piv["r2"], piv["s1"], piv["s2"], *sh, *sl]
    support, resistance = levels.nearest_levels(price, level_set)
    if support is None:
        support = min(piv["s1"], price * 0.99)
    if resistance is None:
        resistance = max(piv["r1"], price * 1.01)

    gap_list = gaps_mod.unfilled_gaps(df)

    # VIX regime read comes first — the momentum sub-score's correct READING
    # (trend-following vs. mean-reverting) depends on it.
    damp_flags: dict[str, bool] = {}
    vix_chg_pct = None
    if vix_df is not None:
        caution, vix_chg_pct = regime.vix_caution(df, vix_df)
        damp_flags["vix"] = caution

    adx_series = momentum_mod.adx(df)
    adx_val = None if adx_series.empty or pd.isna(adx_series.iloc[-1]) else float(adx_series.iloc[-1])
    market_regime = regime.classify_regime(adx_val, vix_chg_pct)

    subscores: dict[str, float] = {
        "sr": score_mod.sr_subscore(price, support, resistance),
        "gap": score_mod.gap_subscore(price, gap_list),
    }

    pcr_val = atm = None
    if option_chain:
        pcr_val, atm = options_mod.compute_pcr(option_chain["calls"], option_chain["puts"],
                                                option_chain["spot"])
        subscores["pcr"] = score_mod.pcr_subscore(pcr_val)

    rsi_series = momentum_mod.rsi(df["close"])
    rsi_val = None if rsi_series.empty or pd.isna(rsi_series.iloc[-1]) else float(rsi_series.iloc[-1])
    subscores["momentum"] = score_mod.momentum_subscore(rsi_val, regime=market_regime)

    ma = moving_avg.ma_stack(df)
    subscores["ma"] = score_mod.ma_subscore(price, ma["values"])

    seq = price_action.swing_sequence(df)
    structure_label = price_action.structure_trend(seq)
    subscores["structure"] = score_mod.structure_subscore(structure_label)

    relationships = []
    for name, driver_df in (drivers or {}).items():
        if driver_df is None or len(driver_df) < 4:
            continue
        t_aligned, d_aligned = drivers_mod.align_by_date(df, driver_df)
        corr = drivers_mod.pct_corr(t_aligned, d_aligned, window=20)
        rel = drivers_mod.driver_relationship(name, driver_df, corr)
        if rel:
            relationships.append(rel)
    if relationships:
        subscores["drivers"] = drivers_mod.driver_subscore(relationships)

    if kind == "future" and oi_buildup:
        subscores["oi"] = score_mod.oi_subscore(oi_buildup)

    composite = score_mod.composite_score(subscores, weights, damp_flags=damp_flags)
    bias = decision.classify_bias(composite)
    confidence = decision.confidence_from_agreement(subscores, weights, bias)

    extra_reasons = [f"Regime: {market_regime}"
                      + (f" (ADX {adx_val:.0f})" if adx_val is not None else "")
                      + (" — RSI read as mean-reversion" if market_regime == "range" else "")]
    if damp_flags.get("vix"):
        extra_reasons.append(f"VIX rising ({vix_chg_pct:+.1f}%) while price falls — conviction reduced")
    for rel in relationships:
        if rel["implication"] != "neutral":
            extra_reasons.append(f"{rel['name']} {rel['change_pct']:+.1f}% ({rel['relationship']} "
                                  f"corr {rel['corr_20d']}) — {rel['implication']} read")
    reasons = _reasons(subscores, weights, bias, extra=extra_reasons)

    return {
        "symbol": symbol, "kind": kind, "horizon": horizon,
        "date": str(last["ts"]), "price": round(price, 2),
        "score": composite, "bias": bias, "confidence": confidence,
        "component_scores": {k: round(v, 1) for k, v in subscores.items()},
        "reasons": reasons,
        "levels": {
            "pivot": round(piv["pivot"], 2), "support": round(support, 2),
            "resistance": round(resistance, 2), "r1": round(piv["r1"], 2),
            "s1": round(piv["s1"], 2), "atm_strike": atm,
        },
        "pcr": pcr_val, "ma": ma, "structure": structure_label,
        "regime": market_regime, "adx": round(adx_val, 1) if adx_val is not None else None,
        "relationships": relationships,
        "weights": weights, "disclaimer": DISCLAIMER,
    }
