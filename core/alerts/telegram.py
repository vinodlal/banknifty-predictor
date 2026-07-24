"""Telegram push: the morning brief, formatted for a phone notification.

Credentials come from the encrypted keyring (core.security.credentials) —
never printed, never logged. The bot token/chat id are optional secrets; if
unset, send_brief() raises a clear error rather than failing silently.
"""
from __future__ import annotations

import requests

from ..security import credentials as creds

API_BASE = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 4096

_SENTIMENT_MARK = {"bullish": "[+]", "bearish": "[-]", "neutral": "[ ]"}


def send_message(text: str, parse_mode: str | None = None) -> dict:
    token = creds.require("TELEGRAM_BOT_TOKEN")
    chat_id = creds.require("TELEGRAM_CHAT_ID")
    url = API_BASE.format(token=token, method="sendMessage")
    payload = {"chat_id": chat_id, "text": text[:MAX_LEN]}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def format_brief_message(brief: dict) -> str:
    lines = ["MarketDawn — Pre-open Brief", brief["generated_at"], ""]
    lines.append(brief["status"])
    lines.append("")

    lines.append("Snapshot")
    for name, tile in brief.get("snapshot", {}).items():
        price = tile.get("last_price")
        cp = tile.get("change_pct")
        if price is None:
            lines.append(f"  {name}: unavailable")
        elif cp is None:
            lines.append(f"  {name}: {price:,.2f}")
        else:
            arrow = "^" if cp > 0 else ("v" if cp < 0 else "-")
            lines.append(f"  {name}: {price:,.2f} {arrow} {cp:+.2f}%")
    if brief.get("pcr") is not None:
        lines.append(f"  Bank Nifty PCR: {brief['pcr']}")
    lines.append("")

    if brief.get("top_signals"):
        lines.append("Top signals")
        for sig in brief["top_signals"]:
            lines.append(f"  {sig['symbol']}: {sig['bias']} (score {sig['score']}, "
                          f"{sig['confidence']} confidence)")
        lines.append("")

    news = brief.get("news", {})
    for label, key in (("India news", "india"), ("Global news", "global")):
        headlines = news.get(key, [])[:3]
        if headlines:
            lines.append(label)
            for h in headlines:
                mark = _SENTIMENT_MARK.get(h["sentiment"], "")
                lines.append(f"  {mark} {h['title']}")
            lines.append("")

    lines.append(brief["disclaimer"])
    return "\n".join(lines)


def send_brief(brief: dict) -> dict:
    return send_message(format_brief_message(brief))
