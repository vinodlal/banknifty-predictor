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

    # -- instrument dump (cached) -------------------------------------------------
    def instruments(self, exchange: str) -> pd.DataFrame:
        if exchange in self._instr_cache:
            return self._instr_cache[exchange]
        today = datetime.now(IST).strftime("%Y-%m-%d")
        path = INSTR_CACHE_DIR / f"{exchange}_{today}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
        else:
            rows = self.kite.instruments(exchange)
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
        rows = self.kite.historical_data(token, start, end, interval="day")
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
        q = self.kite.quote([key])[key]
        return {
            "symbol": symbol,
            "source": "kite",
            "last_price": q["last_price"],
            "prev_close": q["ohlc"]["close"],
            "ts": datetime.now(IST).isoformat(),
        }

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
        q = self.kite.quote([key])[key]
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
