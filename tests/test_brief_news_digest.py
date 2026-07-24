from core.brief.news_digest import tag_sentiment


def test_bearish_context_beats_bullish_word():
    # "surge" is a bullish word in isolation, but bearish in an oil context
    assert tag_sentiment("Oil prices surge as tensions escalate") == "bearish"


def test_war_headline_is_bearish():
    assert tag_sentiment("Congress splits on war powers resolutions") == "bearish"


def test_plain_bearish_word():
    assert tag_sentiment("Dow warns of Middle East uncertainty") == "bearish"


def test_plain_bullish_word():
    assert tag_sentiment("Markets rally as tech stocks jump") == "bullish"


def test_neutral_when_no_signal_words():
    assert tag_sentiment("Ahead of Market: 10 things to watch on Friday") == "neutral"


def test_known_negation_limitation_documented_behaviour():
    # Known limitation: keyword matching can't detect negation. This headline
    # is actually reassuring (the feared spike didn't happen) but still tags
    # bearish because "oil spike" is present -- documenting the behaviour so
    # a future fix (or the optional LLM path) has a clear regression baseline.
    assert tag_sentiment("The oil spike everyone feared never showed up") == "bearish"
