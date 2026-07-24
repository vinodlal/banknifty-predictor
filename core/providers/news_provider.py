"""Public news headlines (RSS) — global + India buckets for the morning brief.

Sources are hand-verified working feeds (2026-07-23), deliberately broad (6
sources: 4 US-origin, 2 India) for cross-source completeness. Two candidates
were caught serving badly stale content while claiming to be live and were
excluded: Moneycontrol (headlines dated April 2024, ~2yr stale) and WSJ
Markets (~1.5yr stale). NDTV Profit's feed was dropped for apparent
mislabeling (returned unrelated general-news content, not business/markets).
A staleness filter (max_age_hours) is applied to EVERY source as a general
safeguard, not just a one-off fix for those two.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (MarketDawn/1.0)"}
TIMEOUT = 10

FEEDS = {
    "india": {
        "ET Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "Livemint Markets": "https://www.livemint.com/rss/markets",
    },
    "global": {
        "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
        "CNBC World": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "MarketWatch": "https://www.marketwatch.com/rss/topstories",
        "Seeking Alpha": "https://seekingalpha.com/market_currents.xml",
    },
}


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fetch_one(source: str, url: str) -> list[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError):
        return []
    out = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        out.append({
            "title": title, "link": (item.findtext("link") or "").strip(),
            "source": source, "published": _parse_date(item.findtext("pubDate")),
        })
    return out


def fetch_headlines(bucket: str, max_age_hours: int = 48, limit: int = 15) -> list[dict]:
    """bucket: 'india' | 'global'. Filters out stale/undated items, dedupes
    by title, sorts most-recent first."""
    feeds = FEEDS.get(bucket, {})
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)

    items: list[dict] = []
    for source, url in feeds.items():
        items.extend(_fetch_one(source, url))

    fresh = [it for it in items if it["published"] and it["published"] >= cutoff]
    seen: set[str] = set()
    deduped = []
    for it in sorted(fresh, key=lambda x: x["published"], reverse=True):
        key = it["title"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    return deduped[:limit]
