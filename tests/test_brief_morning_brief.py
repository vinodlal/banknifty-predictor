from core.brief.morning_brief import assemble_brief


def test_assemble_brief_shape():
    snapshot = {"NIFTY": {"last_price": 23800.0, "change_pct": 0.3},
                "GIFTNIFTY": {"last_price": None, "change_pct": None}}
    news = {"india": [{"title": "X", "sentiment": "neutral"}], "global": []}
    signals = [{"symbol": "BANKNIFTY", "bias": "Long", "score": 70, "confidence": "high"}]
    brief = assemble_brief(snapshot, pcr=0.9, news_digest=news, top_signals=signals)

    assert brief["snapshot"] == snapshot
    assert brief["pcr"] == 0.9
    assert brief["news"] == news
    assert brief["top_signals"] == signals
    assert "generated_at" in brief
    assert brief["disclaimer"]
    assert isinstance(brief["status"], str) and len(brief["status"]) > 0
