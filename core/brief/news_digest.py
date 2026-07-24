"""News digest: bucket headlines (India/global) + a keyword-based sentiment tag.

Rule-based by design — zero LLM cost, works standalone with no API key (per
the plan's token-efficiency principle). KNOWN LIMITATION: simple keyword
matching cannot detect negation — "the oil spike everyone feared never
showed up" reads as bearish (it contains "oil spike") despite being
reassuring news. An optional Claude-API summarization pass can layer better
nuance on top of this later; this version is the free, always-available
baseline, not a claim of full sentiment accuracy.
"""
from __future__ import annotations

from ..providers.news_provider import fetch_headlines

# Checked first — words like "surge"/"jump" are bullish in isolation but
# bearish in an oil/war/geopolitical context ("oil prices surge").
BEARISH_CONTEXT_PHRASES = [
    "oil surge", "crude surge", "oil spike", "crude spike", "oil prices surge",
    "war", "conflict", "sanctions", "tension", "tensions", "recession", "crisis",
]
BEARISH_WORDS = [
    "crash", "plunge", "plunges", "tumble", "tumbles", "selloff", "sell-off",
    "downgrade", "downgraded", "miss", "misses", "slump", "slumps", "weak",
    "warns", "warning", "cut", "cuts", "layoffs", "default", "fear", "fears",
    "drops", "falls", "fell", "decline", "declines", "loss", "losses",
]
BULLISH_WORDS = [
    "rally", "rallies", "surge", "surges", "gain", "gains", "jump", "jumps",
    "soar", "soars", "upgrade", "upgraded", "beat", "beats", "record high",
    "outperform", "rebound", "recovery", "boost", "rises", "rose", "climb", "climbs",
]


def tag_sentiment(headline: str) -> str:
    text = headline.lower()
    if any(p in text for p in BEARISH_CONTEXT_PHRASES):
        return "bearish"
    if any(w in text for w in BEARISH_WORDS):
        return "bearish"
    if any(w in text for w in BULLISH_WORDS):
        return "bullish"
    return "neutral"


def build_digest(max_age_hours: int = 48, limit_per_bucket: int = 8) -> dict:
    digest = {}
    for bucket in ("india", "global"):
        headlines = fetch_headlines(bucket, max_age_hours=max_age_hours, limit=limit_per_bucket)
        digest[bucket] = [
            {
                "title": h["title"], "link": h["link"], "source": h["source"],
                "published": h["published"].isoformat() if h["published"] else None,
                "sentiment": tag_sentiment(h["title"]),
            }
            for h in headlines
        ]
    return digest
