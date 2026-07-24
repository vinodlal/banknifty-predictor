from core.alerts.telegram import format_brief_message, MAX_LEN
from core.brief.morning_brief import assemble_brief


def _sample_brief():
    snapshot = {
        "NIFTY": {"last_price": 23800.55, "change_pct": 0.34},
        "GIFTNIFTY": {"last_price": None, "change_pct": None},
        "BANKNIFTY": {"last_price": 56592.0, "change_pct": -0.94},
    }
    news = {
        "india": [{"title": "Markets rally on strong earnings", "sentiment": "bullish"}],
        "global": [{"title": "Oil prices surge as war tensions rise", "sentiment": "bearish"}],
    }
    signals = [{"symbol": "BANKNIFTY", "bias": "Long", "score": 66, "confidence": "high"}]
    return assemble_brief(snapshot, pcr=0.97, news_digest=news, top_signals=signals)


def test_format_brief_message_contains_key_sections():
    msg = format_brief_message(_sample_brief())
    assert "MarketDawn" in msg
    assert "NIFTY: 23,800.55" in msg
    assert "GIFTNIFTY: unavailable" in msg
    assert "Bank Nifty PCR: 0.97" in msg
    assert "BANKNIFTY: Long (score 66, high confidence)" in msg
    assert "Markets rally on strong earnings" in msg
    assert "Oil prices surge as war tensions rise" in msg
    assert "Not SEBI-registered investment advice" in msg


def test_format_brief_message_within_telegram_length_limit():
    msg = format_brief_message(_sample_brief())
    assert len(msg) <= MAX_LEN


def test_format_brief_message_handles_no_signals_or_news():
    from core.brief.morning_brief import assemble_brief as ab
    brief = ab({}, pcr=None, news_digest={"india": [], "global": []}, top_signals=[])
    msg = format_brief_message(brief)
    assert "MarketDawn" in msg
    assert "Top signals" not in msg
