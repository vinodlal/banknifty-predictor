"""Kite Connect provider — historical candles, quotes, futures OI/basis.

Instrument dumps (kite.instruments(exchange)) are cached to parquet per exchange,
refreshed once per IST calendar day — they're large (thousands of rows) and stable
intraday.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from ..universe import IST as IST_NAME, resolve
from .base import OHLCV_COLS, MarketDataProvider
from .kite_auth import get_client

IST = ZoneInfo(IST_NAME)
ROOT = Path(__file__).resolve().parents[2]
INSTR_CACHE_DIR = ROOT / "data" / "cache" / "instruments"


class KiteProvider(MarketDataProvider):
    name = "kite"

    def __init__(self):
        self._kite = None
        self._instr_cache: dict[str, pd.DataFrame] = {}

    @property
    def kite(self):
        if self._kite is None:
            self._kite = get_client()
        return self._kite

    def _call(self, fn):
        """Run a zero-arg Kite call, auto-recovering once from an expired
        token. Kite invalidates access tokens at a fixed daily time (~6 AM
        IST) regardless of when they were generated — our day-string session
        cache (kite_auth.py) can't detect that boundary in advance, so any
        call can hit a live TokenException even on a "same calendar day"
        cached session. Retrying once after a forced fresh login handles it
        without callers needing to know or care."""
        from kiteconnect.exceptions import TokenException
        try:
            return fn()
        except TokenException:
            self._kite = get_client(force_refresh=True)
            return fn()

    # -- instrument dump (cached) -------------------------------------------------
    def instruments(self, exchange: str) -> pd.DataFrame:
        if exchange in self._instr_cache:
            return self._instr_cache[exchange]
        today = datetime.now(IST).strftime("%Y-%m-%d")
        path = INSTR_CACHE_DIR / f"{exchange}_{today}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
        else:
            rows = self._call(lambda: self.kite.instruments(exchange))
            df = pd.DataFrame(rows)
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(path, index=False)
        self._instr_cache[exchange] = df
        return df

    def _index_token(self, tradingsymbol: str) -> int:
        df = self.instruments("NSE")
        row = df[(df["tradingsymbol"] == tradingsymbol) & (df["segment"] == "INDICES")]
        if row.empty:
            raise ValueError(f"Index {tradingsymbol!r} not found in NSE instrument dump")
        return int(row.iloc[0]["instrument_token"])

    def _equity_token(self, tradingsymbol: str) -> int:
        df = self.instruments("NSE")
        row = df[(df["tradingsymbol"] == tradingsymbol) & (df["segment"] == "NSE")]
        if row.empty:
            raise ValueError(f"Equity {tradingsymbol!r} not found in NSE instrument dump")
        return int(row.iloc[0]["instrument_token"])

    def _resolve_token(self, symbol: str) -> tuple[int, str]:
        inst = resolve(symbol)
        if inst.kind == "index":
            ts = inst.kite.split(":", 1)[1]  # "NSE:NIFTY BANK" -> "NIFTY BANK"
            return self._index_token(ts), "day"
        return self._equity_token(symbol.upper()), "day"

    # -- MarketDataProvider ---------------------------------------------------
    def daily_candles(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        token, _ = self._resolve_token(symbol)
        rows = self._call(lambda: self.kite.historical_data(token, start, end, interval="day"))
        if not rows:
            return pd.DataFrame(columns=OHLCV_COLS)
        df = pd.DataFrame(rows)
        ts = pd.to_datetime(df["date"])
        ts = ts.dt.tz_convert(IST) if ts.dt.tz is not None else ts.dt.tz_localize(IST)
        out = pd.DataFrame({
            "ts": ts, "open": df["open"].astype(float), "high": df["high"].astype(float),
            "low": df["low"].astype(float), "close": df["close"].astype(float),
            "volume": df.get("volume", 0),
        })
        return out.sort_values("ts").reset_index(drop=True)[OHLCV_COLS]

    def quote(self, symbol: str) -> dict:
        inst = resolve(symbol)
        key = inst.kite if inst.kite else f"NSE:{symbol.upper()}"
        q = self._call(lambda: self.kite.quote([key]))[key]
        return {
            "symbol": symbol,
            "source": "kite",
            "last_price": q["last_price"],
            "prev_close": q["ohlc"]["close"],
            "ts": datetime.now(IST).isoformat(),
        }

    # -- holdings & search (stock desk, M5) -----------------------------------
    def holdings(self) -> list[dict]:
        return self._call(lambda: self.kite.holdings())

    def search_equity(self, query: str, limit: int = 10) -> list[dict]:
        """Case-insensitive substring match on tradingsymbol/name in NSE equities."""
        df = self.instruments("NSE")
        eq = df[df["instrument_type"] == "EQ"]
        q = query.upper().strip()
        hits = eq[eq["tradingsymbol"].str.contains(q, na=False)
                  | eq["name"].str.upper().str.contains(q, na=False)]
        return hits[["tradingsymbol", "name", "instrument_token"]].head(limit).to_dict("records")

    def has_futures(self, name: str) -> bool:
        df = self.instruments("NFO")
        return not df[(df["name"] == name) & (df["instrument_type"] == "FUT")].empty

    # -- futures: nearest contract, OI, basis ---------------------------------
    def nearest_future(self, name: str) -> dict | None:
        """Nearest not-yet-expired FUT contract for an index name (e.g. 'BANKNIFTY')."""
        df = self.instruments("NFO")
        futs = df[(df["name"] == name) & (df["instrument_type"] == "FUT")].copy()
        if futs.empty:
            return None
        futs["expiry"] = pd.to_datetime(futs["expiry"]).dt.date
        today = datetime.now(IST).date()
        upcoming = futs[futs["expiry"] >= today].sort_values("expiry")
        row = (upcoming.iloc[0] if not upcoming.empty else futs.sort_values("expiry").iloc[-1])
        return row.to_dict()

    def future_quote(self, name: str) -> dict | None:
        fut = self.nearest_future(name)
        if fut is None:
            return None
        key = f"NFO:{fut['tradingsymbol']}"
        q = self._call(lambda: self.kite.quote([key]))[key]
        return {
            "tradingsymbol": fut["tradingsymbol"],
            "expiry": str(fut["expiry"]),
            "last_price": q["last_price"],
            "oi": q.get("oi"),
            "volume": q.get("volume"),
            "prev_close": q["ohlc"]["close"],
            "source": "kite",
            "ts": datetime.now(IST).isoformat(),
        }

    # -- option chain (morning brief PCR, M7) ---------------------------------
    def option_chain(self, name: str, strike_window_pct: float = 8.0) -> dict | None:
        """Nearest-expiry option chain for `name` (e.g. 'BANKNIFTY'), filtered
        to strikes within strike_window_pct of spot — otherwise a single
        quote() batch call could span hundreds of far-OTM strikes."""
        spot_q = self.quote(name)
        spot = spot_q["last_price"]

        df = self.instruments("NFO")
        opts = df[(df["name"] == name) & (df["instrument_type"].isin(["CE", "PE"]))].copy()
        if opts.empty:
            return None
        opts["expiry"] = pd.to_datetime(opts["expiry"]).dt.date
        today = datetime.now(IST).date()
        upcoming = sorted(e for e in opts["expiry"].unique() if e >= today)
        if not upcoming:
            return None
        nearest_expiry = upcoming[0]
        chain = opts[opts["expiry"] == nearest_expiry]

        lo, hi = spot * (1 - strike_window_pct / 100), spot * (1 + strike_window_pct / 100)
        chain = chain[(chain["strike"] >= lo) & (chain["strike"] <= hi)]
        if chain.empty:
            return None

        keys = [f"NFO:{ts}" for ts in chain["tradingsymbol"]]
        quotes = {}
        for i in range(0, len(keys), 400):  # Kite caps instruments-per-call
            batch = keys[i:i + 400]
            quotes.update(self._call(lambda batch=batch: self.kite.quote(batch)))

        calls, puts = [], []
        for _, row in chain.iterrows():
            q = quotes.get(f"NFO:{row['tradingsymbol']}")
            if not q:
                continue
            entry = {"strike": float(row["strike"]), "tradingsymbol": row["tradingsymbol"],
                      "oi": q.get("oi", 0) or 0, "last_price": q.get("last_price")}
            (calls if row["instrument_type"] == "CE" else puts).append(entry)

        return {
            "expiry": str(nearest_expiry), "spot": spot,
            "calls": sorted(calls, key=lambda c: c["strike"]),
            "puts": sorted(puts, key=lambda p: p["strike"]),
        }
