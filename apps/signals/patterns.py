"""
Price action pattern detection and market regime classification.

Patterns: Bullish/Bearish Engulfing, Hammer, Shooting Star, Doji,
Inside Bar, Three White Soldiers, Three Black Crows, Morning/Evening Star.
"""
import numpy as np
import pandas as pd


def body(c):
    return abs(c["Close"] - c["Open"])


def upper_wick(c):
    return c["High"] - max(c["Open"], c["Close"])


def lower_wick(c):
    return min(c["Open"], c["Close"]) - c["Low"]


def range_(c):
    return c["High"] - c["Low"] + 1e-9


def is_bullish(c):
    return c["Close"] > c["Open"]


def is_bearish(c):
    return c["Close"] < c["Open"]


# =============================================================================
# SINGLE-CANDLE PATTERNS
# =============================================================================

def is_hammer(c) -> bool:
    """Bullish reversal: small body top, long lower wick."""
    r = range_(c)
    b = body(c)
    if r == 0 or b / r > 0.35:
        return False
    return lower_wick(c) > 2 * b and upper_wick(c) < b


def is_shooting_star(c) -> bool:
    """Bearish reversal: small body bottom, long upper wick."""
    r = range_(c)
    b = body(c)
    if r == 0 or b / r > 0.35:
        return False
    return upper_wick(c) > 2 * b and lower_wick(c) < b


def is_doji(c) -> bool:
    """Indecision: tiny body."""
    r = range_(c)
    return r > 0 and body(c) / r < 0.1


# =============================================================================
# TWO-CANDLE PATTERNS
# =============================================================================

def is_bullish_engulfing(prev, cur) -> bool:
    """Bullish candle body fully engulfs prior bearish body."""
    return (is_bearish(prev) and is_bullish(cur) and
            cur["Close"] > prev["Open"] and cur["Open"] < prev["Close"])


def is_bearish_engulfing(prev, cur) -> bool:
    return (is_bullish(prev) and is_bearish(cur) and
            cur["Close"] < prev["Open"] and cur["Open"] > prev["Close"])


def is_inside_bar(prev, cur) -> bool:
    return cur["High"] < prev["High"] and cur["Low"] > prev["Low"]


# =============================================================================
# THREE-CANDLE PATTERNS
# =============================================================================

def is_morning_star(c1, c2, c3) -> bool:
    """Bullish reversal: bearish, small body, bullish closing > midpoint of c1."""
    mid1 = (c1["Open"] + c1["Close"]) / 2
    return (is_bearish(c1) and body(c2) < body(c1) * 0.5 and
            is_bullish(c3) and c3["Close"] > mid1)


def is_evening_star(c1, c2, c3) -> bool:
    mid1 = (c1["Open"] + c1["Close"]) / 2
    return (is_bullish(c1) and body(c2) < body(c1) * 0.5 and
            is_bearish(c3) and c3["Close"] < mid1)


def is_three_white_soldiers(c1, c2, c3) -> bool:
    """Three consecutive bullish closes, each higher."""
    return (is_bullish(c1) and is_bullish(c2) and is_bullish(c3) and
            c2["Close"] > c1["Close"] and c3["Close"] > c2["Close"] and
            c2["Open"] > c1["Open"] and c3["Open"] > c2["Open"])


def is_three_black_crows(c1, c2, c3) -> bool:
    return (is_bearish(c1) and is_bearish(c2) and is_bearish(c3) and
            c2["Close"] < c1["Close"] and c3["Close"] < c2["Close"] and
            c2["Open"] < c1["Open"] and c3["Open"] < c2["Open"])


# =============================================================================
# MASTER DETECTION
# =============================================================================

def detect_patterns(df: pd.DataFrame) -> dict:
    """Scan the last few candles for patterns."""
    if len(df) < 3:
        return {"bullish": [], "bearish": [], "neutral": []}
    bullish, bearish, neutral = [], [], []
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]

    # Single candle (most recent)
    if is_hammer(c3): bullish.append("Hammer")
    if is_shooting_star(c3): bearish.append("Shooting Star")
    if is_doji(c3): neutral.append("Doji")

    # Two-candle
    if is_bullish_engulfing(c2, c3): bullish.append("Bullish Engulfing")
    if is_bearish_engulfing(c2, c3): bearish.append("Bearish Engulfing")
    if is_inside_bar(c2, c3): neutral.append("Inside Bar")

    # Three-candle
    if is_morning_star(c1, c2, c3): bullish.append("Morning Star")
    if is_evening_star(c1, c2, c3): bearish.append("Evening Star")
    if is_three_white_soldiers(c1, c2, c3): bullish.append("Three White Soldiers")
    if is_three_black_crows(c1, c2, c3): bearish.append("Three Black Crows")

    return {"bullish": bullish, "bearish": bearish, "neutral": neutral}


# =============================================================================
# MARKET REGIME
# =============================================================================

def classify_regime(df: pd.DataFrame) -> dict:
    """
    Classify current market regime based on ADX and Bollinger Band width.

    Regimes:
      - "STRONG_TREND": ADX > 25, high volatility → trade breakouts
      - "WEAK_TREND": ADX 20-25 → cautious trend-following
      - "RANGING": ADX < 20 → mean-reversion setups favored
      - "VOLATILE_CHOP": ADX < 20 AND high BB width → avoid
    """
    if "ADX_14" not in df.columns or "BB_Width" not in df.columns:
        return {"regime": "UNKNOWN", "adx": 0, "volatility": "unknown"}
    latest = df.iloc[-1]
    adx_v = float(latest.get("ADX_14", 0) or 0)
    bb_w = float(latest.get("BB_Width", 0) or 0)

    # Historical BB width percentile for context
    bb_series = df["BB_Width"].dropna().tail(100)
    bb_pctile = 0
    if len(bb_series) > 10:
        bb_pctile = float((bb_series < bb_w).sum() / len(bb_series) * 100)

    high_vol = bb_pctile > 70
    low_vol = bb_pctile < 30

    if adx_v >= 25:
        regime = "STRONG_TREND"
        desc = "Strong directional trend - follow momentum"
    elif adx_v >= 20:
        regime = "WEAK_TREND"
        desc = "Emerging trend - confirm before entry"
    elif high_vol:
        regime = "VOLATILE_CHOP"
        desc = "Ranging with high volatility - avoid or use wide stops"
    elif low_vol:
        regime = "TIGHT_RANGE"
        desc = "Low volatility squeeze - breakout imminent"
    else:
        regime = "RANGING"
        desc = "Sideways market - mean-reversion setups favored"

    return {
        "regime": regime,
        "description": desc,
        "adx": round(adx_v, 2),
        "bb_width": round(bb_w, 4),
        "bb_width_percentile": round(bb_pctile, 1),
        "volatility": "high" if high_vol else "low" if low_vol else "normal",
    }


# =============================================================================
# SUPPORT / RESISTANCE
# =============================================================================

def find_levels(df: pd.DataFrame, window: int = 5, max_levels: int = 5) -> dict:
    """
    Find recent swing highs (resistance) and lows (support).
    Uses fractal detection: a high is a local max over +/- window bars.
    """
    highs = df["High"].values
    lows = df["Low"].values
    resistance, support = [], []
    for i in range(window, len(df) - window):
        if all(highs[i] >= highs[i - window:i]) and all(highs[i] >= highs[i + 1:i + window + 1]):
            resistance.append((df.index[i], float(highs[i])))
        if all(lows[i] <= lows[i - window:i]) and all(lows[i] <= lows[i + 1:i + window + 1]):
            support.append((df.index[i], float(lows[i])))
    # Keep most recent levels
    resistance = [p for _, p in resistance[-max_levels:]]
    support = [p for _, p in support[-max_levels:]]
    current = float(df["Close"].iloc[-1])
    # Find nearest levels above/below
    above = sorted([r for r in resistance if r > current])
    below = sorted([s for s in support if s < current], reverse=True)
    return {
        "resistance": sorted(set([round(r, 4) for r in resistance]), reverse=True),
        "support": sorted(set([round(s, 4) for s in support]), reverse=True),
        "nearest_resistance": round(above[0], 4) if above else None,
        "nearest_support": round(below[0], 4) if below else None,
    }
