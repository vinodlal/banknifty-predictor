from core.brief.status import market_status_text


def test_gap_up_and_bullish_pcr():
    snapshot = {"GIFTNIFTY": {"change_pct": 0.4}, "INDIAVIX": {"change_pct": -4.0},
                "BRENT": {"change_pct": 0.2}, "USDINR": {"change_pct": 0.1}}
    text = market_status_text(snapshot, pcr=1.3)
    assert "gap-up" in text
    assert "VIX easing" in text
    assert "put-heavy" in text


def test_gap_down_and_bearish_pcr():
    snapshot = {"GIFTNIFTY": {"change_pct": -0.5}, "INDIAVIX": {"change_pct": 5.0}}
    text = market_status_text(snapshot, pcr=0.5)
    assert "gap-down" in text
    assert "VIX up sharply" in text
    assert "call-heavy" in text


def test_giftnifty_unavailable_is_labelled_not_silent():
    text = market_status_text({}, pcr=None)
    assert "unavailable" in text.lower()


def test_flat_gift_nifty():
    snapshot = {"GIFTNIFTY": {"change_pct": 0.02}}
    text = market_status_text(snapshot, pcr=None)
    assert "flat" in text.lower()


def test_missing_pcr_omits_pcr_sentence():
    snapshot = {"GIFTNIFTY": {"change_pct": 0.5}}
    text = market_status_text(snapshot, pcr=None)
    assert "PCR" not in text
