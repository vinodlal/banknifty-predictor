"""Bank Nifty / Nifty futures desk: OI-build-up + basis layered on the base
signal, plus an attached futures trade plan. Pure function — data is passed
in, not fetched here (keeps the engine offline-testable)."""
from __future__ import annotations

import pandas as pd

from ..features import basis as basis_mod
from ..features import momentum as momentum_mod
from ..features import oi as oi_mod
from ..trade_plan.plan import build_trade_plan
from . import signal as signal_mod


def analyze_futures(name: str, df: pd.DataFrame, *,
                     future_quote: dict, spot_quote: dict,
                     vix_df: pd.DataFrame | None = None,
                     drivers: dict[str, pd.DataFrame] | None = None,
                     option_chain: dict | None = None,
                     oi_prev: int | None = None,
                     horizon: str = "swing",
                     weights: dict[str, float] | None = None,
                     capital: float = 100_000, risk_pct: float = 1.0) -> dict:
    price_chg_pct = (
        (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2] * 100
        if len(df) >= 2 else 0.0
    )
    oi_now = future_quote.get("oi")
    oi_chg_pct = ((oi_now - oi_prev) / oi_prev * 100) if oi_prev and oi_now is not None else 0.0
    buildup = oi_mod.classify_buildup(price_chg_pct, oi_chg_pct)

    sig = signal_mod.analyze(name, kind="future", df=df, vix_df=vix_df, drivers=drivers,
                              option_chain=option_chain, oi_buildup=buildup,
                              horizon=horizon, weights=weights)

    basis_pct = basis_mod.compute_basis(future_quote["last_price"], spot_quote["last_price"])
    sig["oi"] = {
        "buildup": buildup, "implication": oi_mod.IMPLICATION[buildup],
        "oi": oi_now, "oi_chg_pct": round(oi_chg_pct, 2),
    }
    sig["basis"] = {
        "pct": round(basis_pct, 3), "reading": basis_mod.basis_reading(basis_pct),
        "future_price": future_quote["last_price"], "spot_price": spot_quote["last_price"],
    }
    sig["reasons"].insert(0, f"Futures OI: {buildup.replace('_', ' ')} "
                              f"({oi_mod.IMPLICATION[buildup]}), basis {sig['basis']['reading']} "
                              f"({basis_pct:+.2f}%)")
    sig["reasons"] = sig["reasons"][:6]

    atr_series = momentum_mod.atr(df)
    atr_val = float(atr_series.iloc[-1]) if pd.notna(atr_series.iloc[-1]) else future_quote["last_price"] * 0.01
    sig["trade_plan"] = build_trade_plan(
        sig["bias"], price=future_quote["last_price"],
        support=sig["levels"]["support"], resistance=sig["levels"]["resistance"],
        atr_val=atr_val, capital=capital, risk_pct=risk_pct,
    )
    return sig
