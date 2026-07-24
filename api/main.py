"""FastAPI backend — a thin HTTP layer over the already-tested core engine.

No business logic lives here; every endpoint calls straight into core/.
Run: uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from core.engine.futures import analyze_futures
from core.engine.signal import DEFAULT_FUTURES_WEIGHTS
from core.engine.stock import analyze_stock
from core.paper.ledger import get_closed_trades, get_open_trades
from core.paper.scoreboard import compute_scoreboard, scoreboard_by
from core.providers.kite_provider import KiteProvider
from core.providers.public_provider import PublicProvider
from core.universe import drivers_for

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

app = FastAPI(title="MarketDawn API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # web/ dev server; widen for production in M9
    allow_methods=["GET"], allow_headers=["*"],
)

kp = KiteProvider()
pp = PublicProvider()

FUTURES_INSTRUMENTS = {"BANKNIFTY", "NIFTY"}
HISTORY_DAYS = 400


def _trade_to_dict(t) -> dict:
    return {
        "id": t.id, "symbol": t.symbol, "kind": t.kind, "horizon": t.horizon,
        "strategy": t.strategy, "bias": t.bias, "opened_at": t.opened_at,
        "entry": t.entry, "stop": t.stop, "target1": t.target1, "target2": t.target2,
        "size": t.size, "status": t.status, "closed_at": t.closed_at,
        "close_price": t.close_price, "close_reason": t.close_reason,
        "r_multiple": t.r_multiple, "pnl": t.pnl,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/brief")
def get_brief():
    path = DATA_DIR / "brief.json"
    if not path.exists():
        raise HTTPException(404, "No brief generated yet — run `python -m core.brief.run` first.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/futures/{name}")
def get_futures(name: str):
    name = name.upper()
    if name not in FUTURES_INSTRUMENTS:
        raise HTTPException(404, f"Unknown futures instrument {name!r}. Use one of {sorted(FUTURES_INSTRUMENTS)}.")
    start, end = date.today() - timedelta(days=HISTORY_DAYS), date.today()
    df = kp.daily_candles(name, start, end)
    if df.empty:
        raise HTTPException(502, f"No historical data returned for {name}.")
    vix_df = kp.daily_candles("INDIAVIX", start, end)
    future_quote, spot_quote = kp.future_quote(name), kp.quote(name)
    drivers = {n: pp.daily_candles(n, start, end) for n in drivers_for(name)}
    return analyze_futures(name, df, future_quote=future_quote, spot_quote=spot_quote,
                            vix_df=vix_df, drivers=drivers, weights=DEFAULT_FUTURES_WEIGHTS)


@app.get("/stock/search")
def search_stock(q: str = Query(..., min_length=1)):
    return {"query": q, "results": kp.search_equity(q)}


@app.get("/stock/holdings")
def get_holdings():
    return {"holdings": kp.holdings()}


@app.get("/stock/{symbol}")
def get_stock(symbol: str):
    symbol = symbol.upper()
    start, end = date.today() - timedelta(days=HISTORY_DAYS), date.today()
    df = kp.daily_candles(symbol, start, end)
    if df.empty:
        raise HTTPException(404, f"No historical data for {symbol!r} — check the symbol.")
    vix_df = kp.daily_candles("INDIAVIX", start, end)
    has_fut = kp.has_futures(symbol)
    future_quote = kp.future_quote(symbol) if has_fut else None
    is_holding = any(h["tradingsymbol"] == symbol for h in kp.holdings())
    drivers = {n: pp.daily_candles(n, start, end) for n in drivers_for(symbol)}
    return analyze_stock(symbol, df, vix_df=vix_df, drivers=drivers, has_futures=has_fut,
                          future_quote=future_quote, is_holding=is_holding)


@app.get("/paper/scoreboard")
def get_scoreboard(by: str | None = Query(None, pattern="^(strategy|symbol|horizon)$")):
    if by:
        return scoreboard_by(by)
    return compute_scoreboard()


@app.get("/paper/trades")
def get_trades(status: str = Query("open", pattern="^(open|closed)$")):
    trades = get_open_trades() if status == "open" else get_closed_trades()
    return {"status": status, "trades": [_trade_to_dict(t) for t in trades]}


@app.get("/backtest")
def get_backtest():
    path = DATA_DIR / "backtest_report.json"
    if not path.exists():
        raise HTTPException(404, "No backtest report found.")
    return json.loads(path.read_text(encoding="utf-8"))
