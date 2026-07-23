"""Data-accuracy gate — M1's confirm-gate deliverable.

A source is not used for signals until this passes. Checks, per instrument:
  - cross-source agreement: Kite vs public (yfinance) daily closes, within tolerance
  - structural integrity: IST tz-aware, strictly ascending dates, no duplicates/weekends
  - derivatives integrity: futures OI > 0, basis (fut-spot) within a plausible band

Run:  python -m core.providers.verify_accuracy
Writes data/accuracy_report.json (non-secret; kept as milestone evidence).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from ..universe import IST as IST_NAME
from .kite_provider import KiteProvider
from .public_provider import PublicProvider

IST = ZoneInfo(IST_NAME)
ROOT = Path(__file__).resolve().parents[2]
REPORT_FILE = ROOT / "data" / "accuracy_report.json"

CROSS_CHECK_SYMBOLS = ["BANKNIFTY", "NIFTY", "INDIAVIX"]
CLOSE_TOLERANCE_PCT = 0.5      # flag any day where Kite vs public close differs beyond this
BASIS_BAND_PCT = (-1.0, 3.0)   # futures premium/discount plausible band vs spot


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    data: dict = field(default_factory=dict)


def _structural_checks(symbol: str, df: pd.DataFrame) -> CheckResult:
    if df.empty:
        return CheckResult(f"structural[{symbol}]", False, "no rows returned")
    issues = []
    if df["ts"].dt.tz is None:
        issues.append("timestamps not tz-aware")
    elif str(df["ts"].dt.tz) not in (str(IST), "Asia/Kolkata"):
        issues.append(f"timestamps not IST (got {df['ts'].dt.tz})")
    if not df["ts"].is_monotonic_increasing:
        issues.append("dates not strictly ascending")
    if df["ts"].duplicated().any():
        issues.append("duplicate dates present")
    weekends = df["ts"].dt.dayofweek.isin([5, 6]).sum()
    if weekends:
        issues.append(f"{weekends} weekend rows present")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        issues.append("non-positive OHLC values present")
    ok = not issues
    return CheckResult(f"structural[{symbol}]", ok,
                        "clean" if ok else "; ".join(issues), {"rows": len(df)})


def _cross_source_check(symbol: str, kite_df: pd.DataFrame, public_df: pd.DataFrame) -> CheckResult:
    if kite_df.empty or public_df.empty:
        return CheckResult(f"cross_source[{symbol}]", False,
                            f"missing data (kite={len(kite_df)} rows, public={len(public_df)} rows)")
    k = kite_df.assign(d=kite_df["ts"].dt.date).set_index("d")["close"]
    p = public_df.assign(d=public_df["ts"].dt.date).set_index("d")["close"]
    common = k.index.intersection(p.index)
    if len(common) < 3:
        return CheckResult(f"cross_source[{symbol}]", False,
                            f"only {len(common)} overlapping dates — can't cross-check")
    diff_pct = ((k.loc[common] - p.loc[common]).abs() / p.loc[common] * 100)
    worst = diff_pct.sort_values(ascending=False)
    max_diff = float(worst.iloc[0])
    ok = max_diff <= CLOSE_TOLERANCE_PCT
    worst_day = str(worst.index[0])
    detail = (f"{len(common)} days compared, max diff {max_diff:.3f}% on {worst_day} "
              f"(tolerance {CLOSE_TOLERANCE_PCT}%)")
    return CheckResult(f"cross_source[{symbol}]", ok, detail,
                        {"days_compared": len(common), "max_diff_pct": round(max_diff, 4),
                         "worst_day": worst_day})


def _basis_check(name: str, fut: dict | None, spot: dict | None) -> CheckResult:
    """True basis = futures price vs the SPOT index's live price (not the future's
    own previous close, which would just be its day-over-day change)."""
    if not fut or not spot:
        return CheckResult(f"basis[{name}]", False, "no futures contract or spot quote resolved")
    spot_price = spot["last_price"]
    basis_pct = (fut["last_price"] - spot_price) / spot_price * 100
    lo, hi = BASIS_BAND_PCT
    ok = lo <= basis_pct <= hi
    return CheckResult(f"basis[{name}]", ok,
                        f"basis {basis_pct:+.2f}% vs spot {spot_price:,.2f} (band {lo}%..{hi}%)",
                        {"basis_pct": round(basis_pct, 3), "future": fut["tradingsymbol"],
                         "spot_price": spot_price})


def _oi_check(name: str, fut: dict | None) -> CheckResult:
    if not fut:
        return CheckResult(f"oi[{name}]", False, "no futures contract resolved")
    oi = fut.get("oi")
    ok = oi is not None and oi > 0
    return CheckResult(f"oi[{name}]", ok, f"OI={oi}", {"oi": oi})


def run(lookback_days: int = 60) -> dict:
    kp, pp = KiteProvider(), PublicProvider()
    start, end = date.today() - timedelta(days=lookback_days), date.today()

    results: list[CheckResult] = []
    for sym in CROSS_CHECK_SYMBOLS:
        kite_df = kp.daily_candles(sym, start, end)
        public_df = pp.daily_candles(sym, start, end)
        results.append(_structural_checks(f"{sym}/kite", kite_df))
        results.append(_structural_checks(f"{sym}/public", public_df))
        results.append(_cross_source_check(sym, kite_df, public_df))

    for name in ["BANKNIFTY", "NIFTY"]:
        fut = kp.future_quote(name)
        spot = kp.quote(name)
        results.append(_basis_check(name, fut, spot))
        results.append(_oi_check(name, fut))

    all_pass = all(r.passed for r in results)
    report = {
        "generated_at": datetime.now(IST).isoformat(),
        "lookback_days": lookback_days,
        "overall": "PASS" if all_pass else "FAIL",
        "checks": [
            {"name": r.name, "passed": r.passed, "detail": r.detail, **r.data}
            for r in results
        ],
    }
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run()
    print(f"Data accuracy gate: {report['overall']}  ({report['generated_at']})\n")
    for c in report["checks"]:
        mark = "PASS" if c["passed"] else "FAIL"
        print(f"  [{mark}] {c['name']:<26} {c['detail']}")
    print(f"\nFull report written to {REPORT_FILE.relative_to(ROOT)}")
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
