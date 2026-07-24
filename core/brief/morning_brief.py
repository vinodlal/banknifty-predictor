"""Assemble the pre-open morning brief from already-fetched data.

Pure function — snapshot/news/signals are fetched by core.brief.run (the
thin I/O orchestrator) and passed in here, keeping the assembly itself
testable without network access.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .status import market_status_text

IST = ZoneInfo("Asia/Kolkata")
DISCLAIMER = "Educational/informational only. Not SEBI-registered investment advice."


def assemble_brief(snapshot: dict, pcr: float | None, news_digest: dict,
                    top_signals: list[dict]) -> dict:
    return {
        "generated_at": datetime.now(IST).isoformat(),
        "snapshot": snapshot,
        "pcr": pcr,
        "status": market_status_text(snapshot, pcr),
        "news": news_digest,
        "top_signals": top_signals,
        "disclaimer": DISCLAIMER,
    }
