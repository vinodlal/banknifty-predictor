"""Instrument registry: logical name -> per-provider symbols + metadata.

Kite tradingsymbols and lot sizes are refreshed from the Kite instruments dump
in M1 (kept as None here until then, to avoid asserting stale values). yfinance
symbols are used by the public provider and the accuracy cross-check.
"""
from __future__ import annotations

from dataclasses import dataclass

IST = "Asia/Kolkata"


@dataclass(frozen=True)
class Instrument:
    name: str
    kind: str                 # "index" | "global" | "equity"
    yf: str | None            # yfinance symbol (public provider / cross-check)
    kite: str | None          # kite "EXCH:TRADINGSYMBOL"
    lot_size: int | None = None


INDICES: dict[str, Instrument] = {
    "BANKNIFTY": Instrument("BANKNIFTY", "index", "^NSEBANK", "NSE:NIFTY BANK"),
    "NIFTY": Instrument("NIFTY", "index", "^NSEI", "NSE:NIFTY 50"),
    "INDIAVIX": Instrument("INDIAVIX", "index", "^INDIAVIX", "NSE:INDIA VIX"),
}

# Overnight / global drivers. GIFT Nifty has no clean free feed — handled by a
# dedicated public source later; kept here as a known gap.
GLOBAL: dict[str, Instrument] = {
    "BRENT": Instrument("BRENT", "global", "BZ=F", None),
    "USDINR": Instrument("USDINR", "global", "INR=X", "CDS:USDINR"),
    "GIFTNIFTY": Instrument("GIFTNIFTY", "global", None, None),
    "NASDAQ": Instrument("NASDAQ", "global", "^IXIC", None),
    "SEMICONDUCTOR": Instrument("SEMICONDUCTOR", "global", "^SOX", None),  # Philadelphia SOX index
    "KOSPI": Instrument("KOSPI", "global", "^KS11", None),
}


def equity(symbol: str) -> Instrument:
    s = symbol.upper().strip()
    return Instrument(s, "equity", f"{s}.NS", f"NSE:{s}")


def resolve(name: str) -> Instrument:
    n = name.upper().strip()
    return INDICES.get(n) or GLOBAL.get(n) or equity(n)


SNAPSHOT = ["NIFTY", "GIFTNIFTY", "BANKNIFTY", "BRENT", "USDINR", "INDIAVIX"]

# -- sector -> candidate driver map -------------------------------------------
# Config-driven so coverage can expand without touching engine code. Note what
# this DOES and DOESN'T do: core.features.drivers.pct_corr always recomputes
# correlation STRENGTH live on a trailing window every call, so an existing
# driver's influence adapts automatically as relationships shift (e.g. IT's
# sensitivity to Nasdaq/semiconductors strengthening or weakening over time).
# What ISN'T automated yet is discovering NEW candidate drivers nobody
# configured — that's a natural extension for M6's optimizer (systematically
# testing a broader universe of macro series against each sector and
# promoting the ones with a persistent, significant correlation), not yet built.
SECTOR_DRIVERS: dict[str, list[str]] = {
    "BANKING": ["BRENT", "USDINR"],
    "IT": ["NASDAQ", "SEMICONDUCTOR", "KOSPI"],
    "ENERGY": ["BRENT", "USDINR"],
    "AUTO": ["BRENT", "USDINR"],
    "PHARMA": ["USDINR"],
    "GENERAL": ["BRENT", "USDINR"],
}

# Starter symbol -> sector map. Deliberately small — extend as needed; any
# unmapped symbol falls back to GENERAL (Crude/USD-INR).
STOCK_SECTOR: dict[str, str] = {
    "HDFCBANK": "BANKING", "ICICIBANK": "BANKING", "SBIN": "BANKING",
    "AXISBANK": "BANKING", "KOTAKBANK": "BANKING",
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
    "RELIANCE": "ENERGY", "ONGC": "ENERGY",
    "MARUTI": "AUTO", "TATAMOTORS": "AUTO", "M&M": "AUTO",
    "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "CIPLA": "PHARMA",
}


def sector_for(symbol: str) -> str:
    return STOCK_SECTOR.get(symbol.upper().strip(), "GENERAL")


def drivers_for(sector_or_symbol: str) -> list[str]:
    """Accepts a sector name directly, or a stock symbol (resolved to its
    sector first). BANKNIFTY/NIFTY use GENERAL (Crude/USD-INR)."""
    key = sector_or_symbol.upper().strip()
    sector = key if key in SECTOR_DRIVERS else sector_for(key)
    return SECTOR_DRIVERS.get(sector, SECTOR_DRIVERS["GENERAL"])
