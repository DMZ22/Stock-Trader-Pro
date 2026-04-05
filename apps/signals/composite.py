"""
Composite signal engine combining:
  - Scalp trade signal (short-timeframe technicals)
  - LSTM price forecast (ML trend prediction)
  - News sentiment (optional)

Produces a unified trade recommendation with transparent component scoring.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from .scalper import ScalpSignal


def combine(scalp: ScalpSignal, lstm_forecast: Optional[list] = None,
            current_price: Optional[float] = None,
            sentiment: Optional[dict] = None) -> dict:
    """
    Blend scalp signal with LSTM forecast and sentiment.

    Returns dict with composite score (-100..+100), label, and breakdown.
    """
    breakdown = {}
    reasons = list(scalp.reasons)

    # Scalp direction contribution (core signal - 60%)
    if scalp.direction == "LONG":
        scalp_score = scalp.confidence * 0.6
    elif scalp.direction == "SHORT":
        scalp_score = -scalp.confidence * 0.6
    else:
        scalp_score = 0
    breakdown["Scalp Engine"] = round(scalp_score, 1)

    # LSTM forecast contribution (25%)
    lstm_score = 0
    if lstm_forecast and current_price and current_price > 0:
        final_pred = lstm_forecast[-1]
        pct_change = (final_pred - current_price) / current_price * 100
        # Map percentage to score (clamped)
        lstm_score = max(-25, min(25, pct_change * 5))
        reasons.append(f"LSTM forecasts {pct_change:+.2f}% over horizon")
    breakdown["LSTM Forecast"] = round(lstm_score, 1)

    # Sentiment contribution (15%)
    sent_score = 0
    if sentiment and sentiment.get("count", 0) > 0:
        pol = sentiment.get("avg_polarity", 0)
        sent_score = max(-15, min(15, pol * 15))
        reasons.append(f"News sentiment: {sentiment.get('label')} ({pol:+.2f}) from {sentiment.get('count')} articles")
    breakdown["Sentiment"] = round(sent_score, 1)

    composite = scalp_score + lstm_score + sent_score
    composite = max(-100, min(100, composite))

    # Map to label
    if composite >= 60: label = "STRONG BUY"
    elif composite >= 25: label = "BUY"
    elif composite > -25: label = "HOLD"
    elif composite > -60: label = "SELL"
    else: label = "STRONG SELL"

    # Action derived from scalp + composite
    if scalp.action == "TRADE" and abs(composite) >= 25:
        action = "TRADE"
    elif abs(composite) >= 40:
        action = "WATCH"
    else:
        action = "WAIT"

    return {
        "composite_score": round(composite, 1),
        "label": label,
        "action": action,
        "breakdown": breakdown,
        "reasons": reasons,
        "agreement": _agreement(scalp_score, lstm_score, sent_score),
    }


def _agreement(*scores) -> str:
    """Report whether components agree."""
    signs = [1 if s > 5 else -1 if s < -5 else 0 for s in scores]
    positives = sum(1 for s in signs if s == 1)
    negatives = sum(1 for s in signs if s == -1)
    total = len([s for s in signs if s != 0])
    if total == 0: return "No signal"
    if positives == total: return "Full bullish agreement"
    if negatives == total: return "Full bearish agreement"
    if positives > negatives: return "Mostly bullish"
    if negatives > positives: return "Mostly bearish"
    return "Mixed signals"
