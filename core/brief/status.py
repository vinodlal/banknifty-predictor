"""Plain-English market-status paragraph from the 7-tile snapshot + PCR."""
from __future__ import annotations


def market_status_text(snapshot: dict, pcr: float | None) -> str:
    """snapshot: {name: {"last_price":, "change_pct": float|None}} for at
    least NIFTY/GIFTNIFTY/BANKNIFTY/BRENT/USDINR/INDIAVIX (missing/None
    tiles are skipped gracefully, not treated as zero)."""
    parts = []

    gift = snapshot.get("GIFTNIFTY")
    if gift and gift.get("change_pct") is not None:
        cp = gift["change_pct"]
        if cp > 0.15:
            parts.append(f"GIFT Nifty points to a gap-up open ({cp:+.2f}%)")
        elif cp < -0.15:
            parts.append(f"GIFT Nifty points to a gap-down open ({cp:+.2f}%)")
        else:
            parts.append("GIFT Nifty is flat, a muted open likely")
    else:
        parts.append("GIFT Nifty data unavailable — no clean free feed yet")

    vix = snapshot.get("INDIAVIX")
    if vix and vix.get("change_pct") is not None:
        cp = vix["change_pct"]
        if cp > 3:
            parts.append(f"India VIX up sharply ({cp:+.1f}%), caution warranted")
        elif cp < -3:
            parts.append(f"India VIX easing ({cp:+.1f}%), supportive for conviction")

    brent = snapshot.get("BRENT")
    if brent and brent.get("change_pct") is not None:
        cp = brent["change_pct"]
        if abs(cp) > 1.5:
            direction = "up" if cp > 0 else "down"
            parts.append(f"Brent crude {direction} {abs(cp):.1f}% overnight")

    usdinr = snapshot.get("USDINR")
    if usdinr and usdinr.get("change_pct") is not None:
        cp = usdinr["change_pct"]
        if abs(cp) > 0.3:
            direction = "weaker" if cp > 0 else "stronger"
            parts.append(f"Rupee {direction} against the dollar ({cp:+.2f}%)")

    if pcr is not None:
        if pcr >= 1.2:
            parts.append(f"Bank Nifty PCR at {pcr} — put-heavy, bullish positioning tilt")
        elif pcr <= 0.7:
            parts.append(f"Bank Nifty PCR at {pcr} — call-heavy, bearish positioning tilt")
        else:
            parts.append(f"Bank Nifty PCR at {pcr} — balanced option positioning")

    if not parts:
        return "No clear directional cues from the overnight snapshot."
    return ". ".join(parts) + "."
