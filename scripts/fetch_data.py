"""
fetch_data.py — Section 3. Fetch the day's raw data and save it.

Pulls, using the access token from generate_token.py:
  - Bank Nifty index: last 90 daily candles
  - India VIX: last 90 daily candles
  - MCX Crude Oil near-month future: last 90 daily candles   (field: crude_proxy_mcx)
  - USDINR near-month future: last 90 daily candles           (field: usdinr_proxy_futures)
  - Bank Nifty option chain (nearest expiry): OI for CE/PE within +-10% of spot

Writes the combined raw dict to data/history/<today>.json.
"""

import json
import os
from datetime import date, datetime, timedelta

import kite_utils as ku

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT, "data", "history")

CANDLE_DAYS = 90
STRIKE_WINDOW_PCT = 10  # +-10% of spot for the option chain


def _serialize_candles(rows):
    out = []
    for r in rows:
        d = r["date"]
        out.append({
            "date": (d.date() if isinstance(d, datetime) else d).isoformat()
            if not isinstance(d, str) else d,
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": r.get("volume", 0),
        })
    return out


def _fetch_candles(kite, instrument_token, days=CANDLE_DAYS):
    to_d = date.today()
    from_d = to_d - timedelta(days=days * 2 + 15)  # pad for weekends/holidays, then trim
    rows = kite.historical_data(instrument_token, from_d, to_d, "day")
    rows = rows[-days:] if len(rows) > days else rows
    return _serialize_candles(rows)


def _chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_option_chain(kite, spot):
    expiry, chain = ku.resolve_option_chain(kite)
    if not chain:
        return {"expiry": None, "spot": spot, "strike_window_pct": STRIKE_WINDOW_PCT,
                "calls": [], "puts": []}

    lo = spot * (1 - STRIKE_WINDOW_PCT / 100.0)
    hi = spot * (1 + STRIKE_WINDOW_PCT / 100.0)
    in_window = [i for i in chain if lo <= i.get("strike", 0) <= hi]

    symbols = [f"NFO:{i['tradingsymbol']}" for i in in_window]
    quotes = {}
    for batch in _chunked(symbols, 200):
        quotes.update(kite.quote(batch))

    calls, puts = [], []
    for i in in_window:
        sym = f"NFO:{i['tradingsymbol']}"
        q = quotes.get(sym, {})
        row = {
            "strike": i["strike"],
            "tradingsymbol": i["tradingsymbol"],
            "oi": q.get("oi", 0),
            "last_price": q.get("last_price", 0),
        }
        (calls if i["instrument_type"] == "CE" else puts).append(row)

    calls.sort(key=lambda x: x["strike"])
    puts.sort(key=lambda x: x["strike"])
    return {
        "expiry": expiry.isoformat() if expiry else None,
        "spot": spot,
        "strike_window_pct": STRIKE_WINDOW_PCT,
        "calls": calls,
        "puts": puts,
    }


def _override_today_close(kite, candles, exch_symbol, today):
    """
    Kite's CURRENT-day daily candle close is the last traded tick, not NSE's
    official (last-30-min weighted) index close. After market close the live
    quote's last_price already reflects the official close, so overwrite the
    latest candle's close with it. No-op if the last candle isn't today.
    Matters most for indices (NIFTY BANK / INDIA VIX); futures barely differ.
    """
    if not candles or candles[-1]["date"] != today:
        return
    try:
        ltp = kite.ltp([exch_symbol]).get(exch_symbol, {}).get("last_price")
    except Exception:
        ltp = None
    if ltp:
        candles[-1]["close"] = ltp
        candles[-1]["high"] = max(candles[-1]["high"], ltp)
        candles[-1]["low"] = min(candles[-1]["low"], ltp)


def main():
    kite = ku.make_kite()

    bn_inst = ku.resolve_index(kite, "NIFTY BANK")
    vix_inst = ku.resolve_index(kite, "INDIA VIX")
    crude_inst = ku.resolve_crude(kite)
    usdinr_inst = ku.resolve_usdinr(kite)
    for name, inst in [("NIFTY BANK", bn_inst), ("INDIA VIX", vix_inst),
                       ("MCX CRUDEOIL", crude_inst), ("CDS USDINR", usdinr_inst)]:
        if not inst:
            raise SystemExit(f"Could not resolve instrument: {name}. Run verify_sources.py.")

    banknifty = _fetch_candles(kite, bn_inst["instrument_token"])
    vix = _fetch_candles(kite, vix_inst["instrument_token"])
    crude = _fetch_candles(kite, crude_inst["instrument_token"])
    usdinr = _fetch_candles(kite, usdinr_inst["instrument_token"])

    # Correct the provisional current-day close with the official last_price —
    # equity indices ONLY. Only fires when the last candle IS today (a same-day
    # run before settlement). For the recommended next-morning refresh the last
    # candle is the prior, already-settled session, so this safely no-ops. MCX
    # crude (till ~23:30) and CDS USDINR (till 17:00) are excluded — a same-day
    # run would inject an intraday value; a full re-pull self-corrects them.
    today_iso = date.today().isoformat()
    _override_today_close(kite, banknifty, "NSE:NIFTY BANK", today_iso)
    _override_today_close(kite, vix, "NSE:INDIA VIX", today_iso)

    spot = banknifty[-1]["close"] if banknifty else 0.0
    option_chain = fetch_option_chain(kite, spot)

    # Date the record by the latest actual candle, not the wall clock, so a
    # morning refresh is labelled with the (settled) prior session, not "today".
    session_date = banknifty[-1]["date"] if banknifty else date.today().isoformat()
    payload = {
        "date": session_date,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "banknifty": {
            "instrument_token": bn_inst["instrument_token"],
            "tradingsymbol": "NIFTY BANK",
            "candles": banknifty,
        },
        "vix": {
            "instrument_token": vix_inst["instrument_token"],
            "tradingsymbol": "INDIA VIX",
            "candles": vix,
        },
        "crude_proxy_mcx": {
            "instrument_token": crude_inst["instrument_token"],
            "tradingsymbol": crude_inst["tradingsymbol"],
            "expiry": str(crude_inst.get("expiry")),
            "candles": crude,
        },
        "usdinr_proxy_futures": {
            "instrument_token": usdinr_inst["instrument_token"],
            "tradingsymbol": usdinr_inst["tradingsymbol"],
            "expiry": str(usdinr_inst.get("expiry")),
            "candles": usdinr,
        },
        "option_chain": option_chain,
    }

    os.makedirs(HISTORY_DIR, exist_ok=True)
    out_path = os.path.join(HISTORY_DIR, f"{session_date}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Saved raw fetch -> {out_path}")
    print(f"  banknifty={len(banknifty)} candles, vix={len(vix)}, "
          f"crude={len(crude)}, usdinr={len(usdinr)}, "
          f"options={len(option_chain['calls'])}CE/{len(option_chain['puts'])}PE, spot={spot}")


if __name__ == "__main__":
    main()
