"""
AI-style narrative insights. Generates human-readable trade analysis
from signal + regime + patterns + expected-move data.

This is rule-based (not LLM) but produces natural-sounding prose that
explains *why* each signal exists and what to watch for.
"""


def generate_insight(sig, em: dict = None) -> str:
    """Create a 1-3 sentence narrative for a trade signal."""
    if sig.direction == "NEUTRAL":
        regime = (sig.regime or {}).get("regime", "")
        if regime == "VOLATILE_CHOP":
            return "Market is choppy with no clear directional bias. Better to wait for a cleaner setup than trade against the noise."
        if regime == "TIGHT_RANGE":
            return "Price is coiling in a tight range. A breakout is likely soon — watch for volume expansion as the trigger."
        return "No high-probability setup detected. Indicators are mixed or conflicting."

    direction_word = "upside" if sig.direction == "LONG" else "downside"
    strength_word = {"STRONG": "high-conviction", "MODERATE": "moderate", "WEAK": "tentative"}.get(sig.strength, "")

    # Opening statement
    parts = []
    parts.append(
        f"{strength_word.capitalize()} {sig.direction.lower()} setup with {sig.confidence:.0f}% confidence. "
        f"Risk-reward of {sig.risk_reward}:1 targets {direction_word} to {sig.take_profit}."
    )

    # Technical context
    ind = sig.indicators
    context_bits = []
    rsi = ind.get("rsi", 50)
    if sig.direction == "LONG":
        if rsi < 35:
            context_bits.append(f"RSI at {rsi:.0f} signals oversold conditions ripe for a bounce")
        elif rsi > 65:
            context_bits.append(f"RSI at {rsi:.0f} shows strong momentum but watch for exhaustion")
        else:
            context_bits.append(f"RSI at {rsi:.0f} is in healthy uptrend territory")
    else:
        if rsi > 65:
            context_bits.append(f"RSI at {rsi:.0f} indicates overbought conditions primed for reversal")
        elif rsi < 35:
            context_bits.append(f"RSI at {rsi:.0f} is oversold — caution shorting here")
        else:
            context_bits.append(f"RSI at {rsi:.0f} supports continued weakness")

    vol_ratio = ind.get("volume_ratio", 1.0)
    if vol_ratio > 1.5:
        context_bits.append(f"volume is {vol_ratio:.1f}x the average — strong participation")
    elif vol_ratio < 0.7:
        context_bits.append(f"volume is below average ({vol_ratio:.1f}x) — conviction is thin")

    if sig.htf_trend and sig.htf_trend != "NEUTRAL":
        aligned = ((sig.direction == "LONG" and sig.htf_trend == "UP") or
                    (sig.direction == "SHORT" and sig.htf_trend == "DOWN"))
        if aligned:
            context_bits.append(f"the higher-timeframe trend is {sig.htf_trend.lower()}, reinforcing the setup")
        else:
            context_bits.append(f"be aware the higher-timeframe trend is {sig.htf_trend.lower()}, so this is counter-trend")

    if context_bits:
        parts.append(" Key context: " + "; ".join(context_bits) + ".")

    # Patterns
    patterns = sig.patterns or {}
    aligned_patterns = (patterns.get("bullish", []) if sig.direction == "LONG"
                         else patterns.get("bearish", []))
    if aligned_patterns:
        parts.append(f" Confirming pattern: {aligned_patterns[0]}.")

    # Regime warning
    regime = (sig.regime or {}).get("regime", "")
    if regime == "VOLATILE_CHOP":
        parts.append(" ⚠ Regime is volatile chop — consider tighter stops or reduced size.")
    elif regime == "STRONG_TREND":
        parts.append(" Strong trend regime favors trailing stops to ride the move.")

    # Expected move context
    if em and em.get("ok"):
        pct = em.get("expected_move_pct", 0)
        if em.get("fits_2_5_pct_target"):
            parts.append(f" Expected {pct}% move over next 10 bars aligns with the 2-5% target band.")
        elif pct > 0:
            parts.append(f" Expected ±{pct}% range over 10 bars.")

    return "".join(parts)
