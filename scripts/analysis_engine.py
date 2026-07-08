"""
analysis_engine.py — Section 4. Turn a raw day payload into a recommendation.

Public API:
    analyze(day_payload, weights, macro_flags=None) -> result dict

`analyze` is pure (no file I/O) so backtest.py can reuse it to reconstruct what
the engine would have said on any past day. main() wires it to the filesystem:
reads the newest data/history/<date>.json, model_weights.json and macro_flags.json,
and writes data/latest.json.

Composite score is 0-100, higher = more bullish. Components:
  - S/R proximity (weight w_sr): near support -> bullish, near resistance -> bearish
  - Gap zones     (weight w_gap): unfilled gap-up below = support (bullish),
                                  unfilled gap-down above = resistance (bearish)
  - PCR           (weight w_pcr): >1.2 bullish, <0.7 bearish, else neutral
  - VIX regime    (weight w_vix): rising VIX + falling Bank Nifty = caution.
                                  This DAMPENS conviction toward 50, never flips
                                  direction (per spec). w_vix sets damp strength.
"""

import json
import os
from datetime import date, datetime

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT, "data", "history")
WEIGHTS_FILE = os.path.join(ROOT, "data", "model_weights.json")
MACRO_FILE = os.path.join(ROOT, "data", "macro_flags.json")
LATEST_FILE = os.path.join(ROOT, "data", "latest.json")

DISCLAIMER = "Educational/informational only. Not SEBI-registered investment advice."
GAP_THRESHOLD_PCT = 0.3   # gap significant if |gap|/prev_close > 0.3%
SWING_WINDOW = 3          # local extrema over +-3 days


# ---------------------------------------------------------------------------
# small series helpers
# ---------------------------------------------------------------------------
def _closes_df(candles, name):
    """DataFrame indexed by date with a single close column named `name`."""
    if not candles:
        return pd.DataFrame(columns=[name])
    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df[["close"]].rename(columns={"close": name})


def _pct_corr(df, col_a, col_b, window):
    """Pearson correlation of daily % change of two aligned columns over last `window`."""
    if col_a not in df or col_b not in df:
        return None
    pair = df[[col_a, col_b]].dropna()
    if len(pair) < 3:
        return None
    pct = pair.pct_change().dropna()
    pct = pct.tail(window)
    if len(pct) < 3:
        return None
    c = pct[col_a].corr(pct[col_b])
    return None if pd.isna(c) else round(float(c), 3)


# ---------------------------------------------------------------------------
# support / resistance
# ---------------------------------------------------------------------------
def pivot_levels(high, low, close):
    p = (high + low + close) / 3.0
    r1 = 2 * p - low
    s1 = 2 * p - high
    r2 = p + (high - low)
    s2 = p - (high - low)
    return {"pivot": p, "r1": r1, "r2": r2, "s1": s1, "s2": s2}


def swing_points(candles, window=SWING_WINDOW):
    """Return (swing_highs, swing_lows) as sorted lists of price levels."""
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    n = len(candles)
    sh, sl = [], []
    for i in range(n):
        lo = max(0, i - window)
        hi = min(n, i + window + 1)
        if highs[i] == max(highs[lo:hi]) and hi - lo > window:
            sh.append(highs[i])
        if lows[i] == min(lows[lo:hi]) and hi - lo > window:
            sl.append(lows[i])
    return sorted(set(sh)), sorted(set(sl))


def nearest_levels(price, levels):
    """From a set of price levels, nearest one below and above `price`."""
    below = [l for l in levels if l < price]
    above = [l for l in levels if l > price]
    support = max(below) if below else None
    resistance = min(above) if above else None
    return support, resistance


# ---------------------------------------------------------------------------
# gaps
# ---------------------------------------------------------------------------
def unfilled_gaps(candles, threshold_pct=GAP_THRESHOLD_PCT):
    """
    List unfilled gaps. A gap at day t: gap = open[t] - close[t-1].
    Significant if |gap|/close[t-1] > threshold. The gap 'level' is close[t-1];
    it is filled once a later day's range crosses back through that level.
    """
    gaps = []
    for t in range(1, len(candles)):
        prev_close = candles[t - 1]["close"]
        open_t = candles[t]["open"]
        gap = open_t - prev_close
        if prev_close <= 0 or abs(gap) / prev_close * 100 <= threshold_pct:
            continue
        level = prev_close
        direction = "up" if gap > 0 else "down"
        filled = False
        for later in candles[t + 1:]:
            if later["low"] <= level <= later["high"]:
                filled = True
                break
        if not filled:
            gaps.append({"date": candles[t]["date"], "level": level,
                         "direction": direction, "gap_pct": round(gap / prev_close * 100, 3)})
    return gaps


# ---------------------------------------------------------------------------
# PCR
# ---------------------------------------------------------------------------
def compute_pcr(option_chain, atm_window=5):
    calls = option_chain.get("calls", [])
    puts = option_chain.get("puts", [])
    spot = option_chain.get("spot") or 0
    if not calls or not puts or not spot:
        return None, None
    strikes = sorted({c["strike"] for c in calls} & {p["strike"] for p in puts})
    if not strikes:
        return None, None
    atm = min(strikes, key=lambda s: abs(s - spot))
    idx = strikes.index(atm)
    lo, hi = max(0, idx - atm_window), min(len(strikes), idx + atm_window + 1)
    window = set(strikes[lo:hi])
    call_oi = sum(c["oi"] for c in calls if c["strike"] in window)
    put_oi = sum(p["oi"] for p in puts if p["strike"] in window)
    if call_oi <= 0:
        return None, atm
    return round(put_oi / call_oi, 3), atm


# ---------------------------------------------------------------------------
# component sub-scores (0-100, higher = more bullish)
# ---------------------------------------------------------------------------
def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def sr_subscore(price, support, resistance):
    if support is None and resistance is None:
        return 50.0
    if support is None:
        return 20.0  # only resistance overhead -> bearish tilt
    if resistance is None:
        return 80.0  # only support below -> bullish tilt
    ds = abs(price - support)
    dr = abs(resistance - price)
    if ds + dr == 0:
        return 50.0
    return _clamp(50 + 50 * (dr - ds) / (dr + dr if False else (ds + dr)))


def gap_subscore(price, gaps):
    score = 50.0
    for g in gaps:
        if g["direction"] == "up" and g["level"] < price:
            score += 12.5   # unfilled gap-up below acts as support (bullish)
        elif g["direction"] == "down" and g["level"] > price:
            score -= 12.5   # unfilled gap-down above acts as resistance (bearish)
    return _clamp(score)


def pcr_subscore(pcr):
    if pcr is None:
        return 50.0
    if pcr >= 1.2:
        return _clamp(75 + (pcr - 1.2) * 50)      # deeper put-heavy -> more bullish
    if pcr <= 0.7:
        return _clamp(25 - (0.7 - pcr) * 50)      # call-heavy -> more bearish
    # linear bridge between 0.7 (->25) and 1.2 (->75)
    return _clamp(25 + (pcr - 0.7) / 0.5 * 50)


def vix_caution(bn_candles, vix_candles, lookback=3):
    """True if VIX rose and Bank Nifty fell over the last `lookback` sessions."""
    if len(bn_candles) < lookback + 1 or len(vix_candles) < lookback + 1:
        return False, None
    bn_chg = (bn_candles[-1]["close"] - bn_candles[-1 - lookback]["close"]) / bn_candles[-1 - lookback]["close"]
    vix_chg = (vix_candles[-1]["close"] - vix_candles[-1 - lookback]["close"]) / vix_candles[-1 - lookback]["close"]
    caution = vix_chg > 0 and bn_chg < 0
    return caution, round(vix_chg * 100, 2)


# ---------------------------------------------------------------------------
# main analysis
# ---------------------------------------------------------------------------
def analyze(day_payload, weights, macro_flags=None):
    macro_flags = macro_flags or []
    bn = day_payload["banknifty"]["candles"]
    vix = day_payload.get("vix", {}).get("candles", [])
    crude = day_payload.get("crude_proxy_mcx", {}).get("candles", [])
    usdinr = day_payload.get("usdinr_proxy_futures", {}).get("candles", [])
    option_chain = day_payload.get("option_chain", {})

    if not bn:
        raise ValueError("No Bank Nifty candles in payload")

    last = bn[-1]
    price = last["close"]

    # --- correlations
    df = _closes_df(bn, "bn")
    for c, nm in [(vix, "vix"), (crude, "crude"), (usdinr, "usdinr")]:
        df = df.join(_closes_df(c, nm), how="outer")
    df = df.sort_index()
    correlations = {
        "vix_20d": _pct_corr(df, "bn", "vix", 20),
        "vix_90d": _pct_corr(df, "bn", "vix", 90),
        "crude_20d": _pct_corr(df, "bn", "crude", 20),
        "crude_90d": _pct_corr(df, "bn", "crude", 90),
        "usdinr_20d": _pct_corr(df, "bn", "usdinr", 20),
        "usdinr_90d": _pct_corr(df, "bn", "usdinr", 90),
    }

    # --- support / resistance
    piv = pivot_levels(last["high"], last["low"], last["close"])
    sh, sl = swing_points(bn)
    # Pivot is the zones' shared anchor, so it is NOT itself a support/resistance
    # candidate — otherwise a level sitting on the pivot collapses a zone to zero width.
    level_set = [piv["r1"], piv["r2"], piv["s1"], piv["s2"], *sh, *sl]
    support, resistance = nearest_levels(price, level_set)
    if support is None:
        support = min(piv["s1"], price * 0.99)
    if resistance is None:
        resistance = max(piv["r1"], price * 1.01)

    # --- gaps
    gaps = unfilled_gaps(bn)

    # --- pcr
    pcr, atm = compute_pcr(option_chain)

    # --- vix regime
    caution, vix_chg_pct = vix_caution(bn, vix)

    # --- sub-scores & weighted composite
    sr = sr_subscore(price, support, resistance)
    gap_s = gap_subscore(price, gaps)
    pcr_s = pcr_subscore(pcr)
    w = weights
    denom = (w["sr"] + w["gap"] + w["pcr"]) or 1
    base = (w["sr"] * sr + w["gap"] * gap_s + w["pcr"] * pcr_s) / denom
    if caution:
        base = 50 + (base - 50) * (1 - w["vix"] / 100.0)   # dampen conviction
    score = int(round(_clamp(base)))

    # --- classification & zones
    pivot = piv["pivot"]
    buy_zone = sorted([round(support, 2), round(pivot, 2)])
    sell_zone = sorted([round(pivot, 2), round(resistance, 2)])
    if score >= 65:
        recommendation = "Buy Zone"
    elif score <= 35:
        recommendation = "Sell Zone"
    else:
        recommendation = "Neutral"

    # --- reasoning bullets (2-4)
    reasons = []
    ds_pct = abs(price - support) / price * 100
    dr_pct = abs(resistance - price) / price * 100
    if ds_pct <= dr_pct:
        reasons.append(f"Price is within {ds_pct:.1f}% of support ({support:,.0f}).")
    else:
        reasons.append(f"Price is within {dr_pct:.1f}% of resistance ({resistance:,.0f}).")
    if pcr is not None:
        if pcr >= 1.2:
            reasons.append(f"PCR at {pcr} — put-heavy positioning (bullish tilt).")
        elif pcr <= 0.7:
            reasons.append(f"PCR at {pcr} — call-heavy positioning (bearish tilt).")
        else:
            reasons.append(f"PCR at {pcr} — balanced option positioning.")
    unfilled_up = [g for g in gaps if g["direction"] == "up" and g["level"] < price]
    unfilled_dn = [g for g in gaps if g["direction"] == "down" and g["level"] > price]
    if unfilled_up:
        reasons.append(f"Unfilled gap-up support near {unfilled_up[-1]['level']:,.0f}.")
    elif unfilled_dn:
        reasons.append(f"Unfilled gap-down resistance near {unfilled_dn[0]['level']:,.0f}.")
    if caution:
        reasons.append(f"VIX up {vix_chg_pct}% while Bank Nifty fell — conviction reduced.")
    reasons = reasons[:4]

    # --- macro flags today / upcoming
    today = day_payload.get("date")
    macro_today = [m for m in macro_flags if m.get("date") == today]

    # --- day change vs prior close
    prev_close = bn[-2]["close"] if len(bn) >= 2 else price
    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0

    # --- score label so a mid-scale number isn't misread as "low"
    # (0-100, 50 = neutral). 65+ = Buy, 35- = Sell.
    if score >= 65:
        score_label = "Bullish (Buy trigger)"
    elif score >= 55:
        score_label = "Mildly bullish (below Buy trigger)"
    elif score > 45:
        score_label = "Neutral"
    elif score > 35:
        score_label = "Mildly bearish (above Sell trigger)"
    else:
        score_label = "Bearish (Sell trigger)"

    # --- projected next-day levels: pivots from TODAY's OHLC apply to next session
    projection = {
        "next_day_pivot": round(piv["pivot"], 2),
        "next_day_upside": round(piv["r1"], 2),      # projected resistance / buy target
        "next_day_downside": round(piv["s1"], 2),    # projected support / sell target
        "next_day_range": [round(piv["s1"], 2), round(piv["r1"], 2)],
    }

    return {
        "date": today,
        "banknifty_close": round(price, 2),
        "ohlc": {
            "open": round(last["open"], 2), "high": round(last["high"], 2),
            "low": round(last["low"], 2), "close": round(price, 2),
        },
        "prev_close": round(prev_close, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "recommendation": recommendation,
        "score": score,
        "score_label": score_label,
        "buy_trigger": 65,
        "sell_trigger": 35,
        "buy_zone": buy_zone,
        "sell_zone": sell_zone,
        "projection": projection,
        "reasons": reasons,
        "correlations": correlations,
        "pcr": pcr,
        "levels": {
            "pivot": round(pivot, 2),
            "nearest_support": round(support, 2),
            "nearest_resistance": round(resistance, 2),
            "r1": round(piv["r1"], 2), "r2": round(piv["r2"], 2),
            "s1": round(piv["s1"], 2), "s2": round(piv["s2"], 2),
            "atm_strike": atm,
        },
        "components": {
            "sr": round(sr, 1), "gap": round(gap_s, 1),
            "pcr": round(pcr_s, 1), "vix_caution": caution,
        },
        "weights": weights,
        "macro_today": macro_today,
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# filesystem wiring
# ---------------------------------------------------------------------------
def load_weights():
    with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["weights"]


def load_macro_flags():
    if not os.path.exists(MACRO_FILE):
        return []
    with open(MACRO_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("flags", [])


def load_history_files():
    if not os.path.isdir(HISTORY_DIR):
        return []
    files = sorted(fn for fn in os.listdir(HISTORY_DIR) if fn.endswith(".json"))
    return [os.path.join(HISTORY_DIR, fn) for fn in files]


def main():
    files = load_history_files()
    if not files:
        raise SystemExit("No history files found. Run fetch_data.py first.")
    with open(files[-1], "r", encoding="utf-8") as f:
        day_payload = json.load(f)

    result = analyze(day_payload, load_weights(), load_macro_flags())
    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {LATEST_FILE}: {result['recommendation']} "
          f"(score {result['score']}) for {result['date']}")


if __name__ == "__main__":
    main()
