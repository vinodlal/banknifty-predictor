"""Live orchestration: fetch snapshot/news/signals, assemble the brief, write
data/brief.json, and (if Telegram credentials are set) send it.

The one place in core/brief/ that does I/O — assembly itself (morning_brief.py)
stays pure/testable; this is the thin wiring layer, same pattern as
core/providers/*.py.

Run: python -m core.brief.run
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from ..alerts import telegram
from ..engine.futures import analyze_futures
from ..engine.signal import DEFAULT_FUTURES_WEIGHTS
from ..features.options import compute_pcr
from ..providers.kite_provider import KiteProvider
from ..providers.public_provider import PublicProvider
from ..universe import drivers_for
from .morning_brief import assemble_brief
from .news_digest import build_digest

ROOT = Path(__file__).resolve().parents[2]
BRIEF_FILE = ROOT / "data" / "brief.json"

SNAPSHOT_VIA_KITE = ["NIFTY", "BANKNIFTY", "INDIAVIX"]
SNAPSHOT_VIA_PUBLIC = ["BRENT", "USDINR"]


def _tile(provider, name: str) -> dict:
    try:
        q = provider.quote(name)
        prev, last = q.get("prev_close"), q.get("last_price")
        cp = ((last - prev) / prev * 100) if prev else None
        return {"last_price": last, "prev_close": prev,
                "change_pct": round(cp, 2) if cp is not None else None, "source": q.get("source")}
    except Exception:
        return {"last_price": None, "prev_close": None, "change_pct": None, "source": None}


def fetch_snapshot(kp: KiteProvider, pp: PublicProvider) -> dict:
    snapshot = {name: _tile(kp, name) for name in SNAPSHOT_VIA_KITE}
    snapshot.update({name: _tile(pp, name) for name in SNAPSHOT_VIA_PUBLIC})
    # Known gap (see core/universe.py) — no clean free GIFT Nifty feed yet.
    snapshot["GIFTNIFTY"] = {"last_price": None, "prev_close": None,
                              "change_pct": None, "source": None}
    return snapshot


def fetch_pcr(kp: KiteProvider) -> float | None:
    try:
        oc = kp.option_chain("BANKNIFTY")
        if not oc:
            return None
        pcr, _atm = compute_pcr(oc["calls"], oc["puts"], oc["spot"])
        return pcr
    except Exception:
        return None


def fetch_top_signals(kp: KiteProvider, pp: PublicProvider) -> list[dict]:
    start, end = date.today() - timedelta(days=400), date.today()
    vix_df = kp.daily_candles("INDIAVIX", start, end)
    signals = []
    for name in ["BANKNIFTY", "NIFTY"]:
        df = kp.daily_candles(name, start, end)
        future_quote, spot_quote = kp.future_quote(name), kp.quote(name)
        driver_names = drivers_for(name)  # indices fall back to GENERAL: Crude/USDINR
        drivers = {n: pp.daily_candles(n, start, end) for n in driver_names}
        sig = analyze_futures(name, df, future_quote=future_quote, spot_quote=spot_quote,
                               vix_df=vix_df, drivers=drivers, weights=DEFAULT_FUTURES_WEIGHTS)
        signals.append(sig)
    return signals


def main(send_telegram: bool = True) -> dict:
    kp, pp = KiteProvider(), PublicProvider()

    snapshot = fetch_snapshot(kp, pp)
    pcr = fetch_pcr(kp)
    news = build_digest()
    top_signals = fetch_top_signals(kp, pp)
    brief = assemble_brief(snapshot, pcr, news, top_signals)

    BRIEF_FILE.parent.mkdir(parents=True, exist_ok=True)
    BRIEF_FILE.write_text(json.dumps(brief, indent=2, default=str), encoding="utf-8")

    if send_telegram:
        try:
            telegram.send_brief(brief)
            brief["_telegram_sent"] = True
        except RuntimeError as e:  # missing credentials — clear, not silent
            brief["_telegram_sent"] = False
            brief["_telegram_error"] = str(e)
    return brief


if __name__ == "__main__":
    result = main()
    print(f"Brief written to {BRIEF_FILE}")
    print(f"Status: {result['status']}")
    print(f"Telegram sent: {result.get('_telegram_sent')}"
          + (f" ({result['_telegram_error']})" if result.get("_telegram_error") else ""))
