"""Shared test helpers."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def paper_db():
    """Isolated in-memory ledger DB per test — never touches the real
    data/app.db. Any test that opens/settles/reads paper trades should
    request this fixture."""
    from core.paper import db as paper_db_module
    paper_db_module.configure("sqlite:///:memory:")
    yield
    # Reset to uninitialized rather than eagerly (re)binding the real DB —
    # that would create data/app.db as a side effect of merely running tests.
    paper_db_module._engine = None
    paper_db_module._SessionLocal = None


def make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a standardized OHLCV DataFrame from short dict rows.

    Each row: {"o":.., "h":.., "l":.., "c":.., "v": optional}. Dates are
    sequential calendar days from a fixed anchor (gaps/weekends don't matter
    for these unit tests — only order and spacing do).
    """
    start = datetime(2026, 1, 1, tzinfo=IST)
    ts = [start + timedelta(days=i) for i in range(len(rows))]
    return pd.DataFrame({
        "ts": ts,
        "open": [r["o"] for r in rows],
        "high": [r["h"] for r in rows],
        "low": [r["l"] for r in rows],
        "close": [r["c"] for r in rows],
        "volume": [r.get("v", 1000) for r in rows],
    })


def flat_series(value: float, n: int) -> list[dict]:
    """n candles with identical OHLC (zero range) — for constant-input checks."""
    return [{"o": value, "h": value, "l": value, "c": value} for _ in range(n)]
