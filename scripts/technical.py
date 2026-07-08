"""
technical.py — build data/technical.json for the Technical Analysis tab.

Reads data/bn_daily.json (extended Bank Nifty daily OHLC, ~1yr+ so the 200-DMA
is meaningful) and computes:
  - 20 / 50 / 100 / 200-day simple moving averages
  - support / resistance levels (clustered swing highs & lows)
  - candlestick patterns (engulfing, hammer, shooting star, doji)
  - golden / death crosses (50-DMA vs 200-DMA)
  - a moving-average summary (price vs each DMA, overall trend)

Daily refresh: append the new settled day to data/bn_daily.json, re-run this.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "bn_daily.json")
OUT = os.path.join(ROOT, "data", "technical.json")

MAS = [20, 50, 100, 200]
SWING_WIN = 5            # local extremum lookback each side
CLUSTER_PCT = 0.6       # merge S/R levels within this % of each other
PATTERN_LOOKBACK = 70   # only surface patterns within the last N sessions


def sma(closes, n, i):
    if i < n - 1:
        return None
    return round(sum(closes[i - n + 1:i + 1]) / n, 2)


def swing_levels(c):
    highs = [x["h"] for x in c]
    lows = [x["l"] for x in c]
    n = len(c)
    levels = []  # (price, kind)
    for i in range(SWING_WIN, n - SWING_WIN):
        win_h = highs[i - SWING_WIN:i + SWING_WIN + 1]
        win_l = lows[i - SWING_WIN:i + SWING_WIN + 1]
        if highs[i] == max(win_h):
            levels.append([highs[i], "R"])
        if lows[i] == min(win_l):
            levels.append([lows[i], "S"])
    return levels


def cluster(levels, price):
    levels.sort(key=lambda x: x[0])
    clusters = []
    for lv, kind in levels:
        if clusters and abs(lv - clusters[-1]["sum"] / clusters[-1]["n"]) / lv * 100 <= CLUSTER_PCT:
            clusters[-1]["sum"] += lv
            clusters[-1]["n"] += 1
        else:
            clusters.append({"sum": lv, "n": 1})
    out = []
    for cl in clusters:
        lvl = cl["sum"] / cl["n"]
        out.append({
            "price": round(lvl, 2),
            "type": "support" if lvl < price else "resistance",
            "touches": cl["n"],
        })
    # rank by touches then closeness to price; keep the strongest few each side
    sup = sorted([l for l in out if l["type"] == "support"],
                 key=lambda l: (-l["touches"], abs(l["price"] - price)))[:4]
    res = sorted([l for l in out if l["type"] == "resistance"],
                 key=lambda l: (-l["touches"], abs(l["price"] - price)))[:4]
    return sorted(sup + res, key=lambda l: l["price"])


def _body(o, c): return abs(c - o)
def _rng(h, l): return max(h - l, 1e-9)


def detect_patterns(c):
    out = []
    n = len(c)
    for i in range(1, n):
        d, p = c[i], c[i - 1]
        o, cl, h, l = d["o"], d["c"], d["h"], d["l"]
        body = _body(o, cl)
        rng = _rng(h, l)
        upper = h - max(o, cl)
        lower = min(o, cl) - l
        trend_up = i >= 5 and cl > c[i - 5]["c"]
        trend_dn = i >= 5 and cl < c[i - 5]["c"]

        pat = None
        # engulfing
        if cl > o and p["c"] < p["o"] and o <= p["c"] and cl >= p["o"] and body > _body(p["o"], p["c"]):
            pat = ("Bullish engulfing", "bull")
        elif cl < o and p["c"] > p["o"] and o >= p["c"] and cl <= p["o"] and body > _body(p["o"], p["c"]):
            pat = ("Bearish engulfing", "bear")
        # hammer / shooting star (single candle)
        elif body <= 0.4 * rng and lower >= 2 * body and upper <= body and trend_dn:
            pat = ("Hammer", "bull")
        elif body <= 0.4 * rng and upper >= 2 * body and lower <= body and trend_up:
            pat = ("Shooting star", "bear")
        # doji
        elif body <= 0.001 * o and rng > 0.004 * o:
            pat = ("Doji", "neutral")

        if pat and i >= n - PATTERN_LOOKBACK:
            out.append({"date": d["date"], "type": pat[0], "dir": pat[1]})
    return out


def detect_crosses(c, ma_series):
    out = []
    m50, m200 = ma_series[50], ma_series[200]
    for i in range(1, len(c)):
        if None in (m50[i], m200[i], m50[i - 1], m200[i - 1]):
            continue
        if m50[i - 1] <= m200[i - 1] and m50[i] > m200[i]:
            out.append({"date": c[i]["date"], "type": "golden"})
        elif m50[i - 1] >= m200[i - 1] and m50[i] < m200[i]:
            out.append({"date": c[i]["date"], "type": "death"})
    return out


def main():
    with open(SRC, encoding="utf-8") as f:
        c = json.load(f)
    c.sort(key=lambda x: x["date"])
    closes = [x["c"] for x in c]

    ma_series = {n: [sma(closes, n, i) for i in range(len(c))] for n in MAS}
    candles = []
    for i, d in enumerate(c):
        row = {"date": d["date"], "o": d["o"], "h": d["h"], "l": d["l"], "c": d["c"]}
        for n in MAS:
            row[f"ma{n}"] = ma_series[n][i]
        candles.append(row)

    price = closes[-1]
    levels = cluster(swing_levels(c), price)
    patterns = detect_patterns(c)
    crosses = detect_crosses(c, ma_series)

    above = [n for n in MAS if ma_series[n][-1] and price >= ma_series[n][-1]]
    below = [n for n in MAS if ma_series[n][-1] and price < ma_series[n][-1]]
    if len(above) == len([n for n in MAS if ma_series[n][-1]]):
        trend = "Strong uptrend — price above all moving averages"
    elif len(below) == len([n for n in MAS if ma_series[n][-1]]):
        trend = "Strong downtrend — price below all moving averages"
    elif price >= (ma_series[200][-1] or 0):
        trend = "Uptrend bias — price above the 200-DMA"
    else:
        trend = "Downtrend bias — price below the 200-DMA"

    out = {
        "as_of": c[-1]["date"],
        "candles": candles,
        "levels": levels,
        "patterns": patterns,
        "crosses": crosses,
        "ma_summary": {
            "price": round(price, 2),
            **{f"ma{n}": ma_series[n][-1] for n in MAS},
            "above": above, "below": below, "trend": trend,
        },
        "disclaimer": "Educational/informational only. Not investment advice.",
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT}: {len(candles)} candles, {len(levels)} levels, "
          f"{len(patterns)} patterns, {len(crosses)} crosses")
    print("  trend:", trend)
    print("  MAs:", {n: ma_series[n][-1] for n in MAS})


if __name__ == "__main__":
    main()
