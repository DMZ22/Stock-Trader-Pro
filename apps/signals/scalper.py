"""
Scalp trade signal engine.

Detects high-probability intraday scalp setups combining:
  - EMA-9/EMA-21 crossover (fast trend)
  - VWAP position (institutional bias)
  - Supertrend direction (trend filter)
  - RSI(14) for overbought/oversold
  - MACD histogram momentum
  - Volume confirmation
  - ADX trend strength

Every signal produces: entry, stop-loss, take-profit levels, risk-reward
ratio, and a confidence score (0-100). Stop-loss uses ATR (Wilder's) to
adapt to current volatility.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List
import pandas as pd
import numpy as np


# Risk management defaults
ATR_SL_MULT = 1.5   # Stop-loss distance = 1.5 * ATR
ATR_TP_MULT = 3.0   # Take-profit distance = 3.0 * ATR (2:1 R/R)
MIN_CONFIDENCE = 55  # Below this, flag as "Watch" rather than "Trade"


@dataclass
class ScalpSignal:
    symbol: str
    timestamp: str
    direction: str           # "LONG" | "SHORT" | "NEUTRAL"
    action: str              # "TRADE" | "WATCH" | "WAIT"
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    risk_pct: float
    reward_pct: float
    confidence: float        # 0-100
    strength: str            # "STRONG" | "MODERATE" | "WEAK"
    reasons: List[str] = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    position_size_hint: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _score_long(latest, prev) -> tuple:
    score = 0.0
    reasons = []

    if latest["EMA_9"] > latest["EMA_21"]:
        score += 15
        reasons.append("EMA-9 above EMA-21 (short trend up)")
        if prev["EMA_9"] <= prev["EMA_21"]:
            score += 10
            reasons.append("Fresh bullish EMA crossover")

    if latest["Close"] > latest["VWAP"]:
        score += 10
        reasons.append(f"Price above VWAP ({latest['VWAP']:.2f}) - institutional bias long")
        if prev["Close"] <= prev["VWAP"]:
            score += 5
            reasons.append("Just reclaimed VWAP")

    if latest.get("ST_Direction") == 1:
        score += 15
        reasons.append("Supertrend bullish")

    if latest["MACD_Hist"] > 0:
        score += 8
        reasons.append(f"MACD histogram positive ({latest['MACD_Hist']:.3f})")
        if latest["MACD_Hist"] > prev.get("MACD_Hist", 0):
            score += 7
            reasons.append("MACD momentum accelerating")

    rsi_v = latest["RSI_14"]
    if 40 <= rsi_v <= 65:
        score += 10
        reasons.append(f"RSI {rsi_v:.1f} (healthy uptrend range)")
    elif 30 <= rsi_v < 40:
        score += 15
        reasons.append(f"RSI {rsi_v:.1f} (oversold bounce setup)")
    elif rsi_v > 70:
        score -= 10
        reasons.append(f"RSI {rsi_v:.1f} overbought - caution")

    vr = latest.get("Vol_Ratio", 1.0)
    if vr and vr > 1.5:
        score += 10
        reasons.append(f"Volume {vr:.2f}x average (strong participation)")
    elif vr and vr > 1.2:
        score += 5
        reasons.append(f"Volume {vr:.2f}x average")

    adx_v = latest.get("ADX_14", 0)
    di_plus = latest.get("DI_PLUS", 0)
    di_minus = latest.get("DI_MINUS", 0)
    if adx_v > 25 and di_plus > di_minus:
        score += 10
        reasons.append(f"ADX {adx_v:.1f} confirms strong trend, +DI > -DI")
    elif adx_v < 20:
        score -= 5
        reasons.append(f"ADX {adx_v:.1f} (weak trend / ranging market)")

    sk = latest.get("Stoch_K", 50)
    sd = latest.get("Stoch_D", 50)
    if sk < 20 and sk > sd:
        score += 10
        reasons.append("Stochastic oversold reversal (%K crossing %D up)")
    elif sk > 80:
        score -= 5

    if latest.get("BB_PercentB") is not None:
        pb = latest["BB_PercentB"]
        if pb > 1.0:
            score += 5
            reasons.append(f"Price breaking above upper BB (%B={pb:.2f})")
        elif pb < 0:
            score += 10
            reasons.append(f"Price at/below lower BB - mean reversion buy")

    return score, reasons


def _score_short(latest, prev) -> tuple:
    score = 0.0
    reasons = []

    if latest["EMA_9"] < latest["EMA_21"]:
        score += 15
        reasons.append("EMA-9 below EMA-21 (short trend down)")
        if prev["EMA_9"] >= prev["EMA_21"]:
            score += 10
            reasons.append("Fresh bearish EMA crossover")

    if latest["Close"] < latest["VWAP"]:
        score += 10
        reasons.append(f"Price below VWAP ({latest['VWAP']:.2f}) - distribution bias")
        if prev["Close"] >= prev["VWAP"]:
            score += 5
            reasons.append("Just lost VWAP")

    if latest.get("ST_Direction") == -1:
        score += 15
        reasons.append("Supertrend bearish")

    if latest["MACD_Hist"] < 0:
        score += 8
        reasons.append(f"MACD histogram negative ({latest['MACD_Hist']:.3f})")
        if latest["MACD_Hist"] < prev.get("MACD_Hist", 0):
            score += 7
            reasons.append("MACD momentum accelerating down")

    rsi_v = latest["RSI_14"]
    if 35 <= rsi_v <= 60:
        score += 10
        reasons.append(f"RSI {rsi_v:.1f} (downtrend continuation range)")
    elif 60 < rsi_v <= 70:
        score += 15
        reasons.append(f"RSI {rsi_v:.1f} (overbought rejection setup)")
    elif rsi_v < 30:
        score -= 10
        reasons.append(f"RSI {rsi_v:.1f} oversold - caution")

    vr = latest.get("Vol_Ratio", 1.0)
    if vr and vr > 1.5:
        score += 10
        reasons.append(f"Volume {vr:.2f}x average (strong selling)")
    elif vr and vr > 1.2:
        score += 5

    adx_v = latest.get("ADX_14", 0)
    di_plus = latest.get("DI_PLUS", 0)
    di_minus = latest.get("DI_MINUS", 0)
    if adx_v > 25 and di_minus > di_plus:
        score += 10
        reasons.append(f"ADX {adx_v:.1f} confirms downtrend, -DI > +DI")
    elif adx_v < 20:
        score -= 5

    sk = latest.get("Stoch_K", 50)
    sd = latest.get("Stoch_D", 50)
    if sk > 80 and sk < sd:
        score += 10
        reasons.append("Stochastic overbought reversal (%K crossing %D down)")
    elif sk < 20:
        score -= 5

    if latest.get("BB_PercentB") is not None:
        pb = latest["BB_PercentB"]
        if pb < 0:
            score += 5
            reasons.append(f"Price breaking below lower BB (%B={pb:.2f})")
        elif pb > 1.0:
            score += 10
            reasons.append("Price at/above upper BB - mean reversion sell")

    return score, reasons


def _strength_label(confidence: float) -> str:
    if confidence >= 80: return "STRONG"
    if confidence >= 65: return "MODERATE"
    return "WEAK"


def detect_scalp(df_with_indicators: pd.DataFrame, symbol: str,
                 account_size: float = 10000.0, risk_per_trade_pct: float = 1.0) -> ScalpSignal:
    """
    Analyze most recent bar and produce a scalp trade signal.

    account_size: for position sizing hint
    risk_per_trade_pct: % of account risked per trade (1% is conventional)
    """
    if len(df_with_indicators) < 2:
        raise ValueError("Need at least 2 bars of indicator data")

    df = df_with_indicators.dropna(subset=["EMA_9", "EMA_21", "RSI_14", "ATR_14", "VWAP"])
    if len(df) < 2:
        raise ValueError("Insufficient indicator data (too many NaNs)")

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(latest["Close"])
    atr_val = float(latest["ATR_14"])
    timestamp = str(df.index[-1])

    long_score, long_reasons = _score_long(latest, prev)
    short_score, short_reasons = _score_short(latest, prev)

    if long_score > short_score and long_score >= 30:
        direction = "LONG"
        confidence = min(100, max(0, long_score))
        reasons = long_reasons
        entry = close
        stop_loss = entry - ATR_SL_MULT * atr_val
        take_profit = entry + ATR_TP_MULT * atr_val
    elif short_score > long_score and short_score >= 30:
        direction = "SHORT"
        confidence = min(100, max(0, short_score))
        reasons = short_reasons
        entry = close
        stop_loss = entry + ATR_SL_MULT * atr_val
        take_profit = entry - ATR_TP_MULT * atr_val
    else:
        direction = "NEUTRAL"
        confidence = max(long_score, short_score, 0)
        reasons = ["No clear directional setup - market consolidating"]
        entry = close
        stop_loss = close
        take_profit = close

    if direction != "NEUTRAL":
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        rr = reward / risk if risk > 0 else 0
        risk_pct = (risk / entry * 100) if entry else 0
        reward_pct = (reward / entry * 100) if entry else 0
    else:
        rr = 0; risk_pct = 0; reward_pct = 0

    if direction == "NEUTRAL":
        action = "WAIT"
    elif confidence >= MIN_CONFIDENCE:
        action = "TRADE"
    else:
        action = "WATCH"

    pos_size = None
    if direction != "NEUTRAL" and risk_pct > 0:
        dollar_risk = account_size * (risk_per_trade_pct / 100)
        risk_amt = abs(entry - stop_loss)
        shares = int(dollar_risk / risk_amt) if risk_amt > 0 else 0
        pos_size = {
            "account": account_size,
            "risk_per_trade_pct": risk_per_trade_pct,
            "dollar_risk": round(dollar_risk, 2),
            "shares": shares,
            "position_value": round(shares * entry, 2),
        }

    return ScalpSignal(
        symbol=symbol, timestamp=timestamp, direction=direction, action=action,
        entry=round(entry, 4), stop_loss=round(stop_loss, 4), take_profit=round(take_profit, 4),
        risk_reward=round(rr, 2), risk_pct=round(risk_pct, 2), reward_pct=round(reward_pct, 2),
        confidence=round(confidence, 1), strength=_strength_label(confidence),
        reasons=reasons,
        indicators={
            "price": round(close, 4),
            "ema_9": round(float(latest["EMA_9"]), 4),
            "ema_21": round(float(latest["EMA_21"]), 4),
            "vwap": round(float(latest["VWAP"]), 4),
            "rsi": round(float(latest["RSI_14"]), 2),
            "macd_hist": round(float(latest["MACD_Hist"]), 4),
            "adx": round(float(latest.get("ADX_14", 0)), 2),
            "atr": round(atr_val, 4),
            "supertrend_dir": int(latest.get("ST_Direction", 0)),
            "stoch_k": round(float(latest.get("Stoch_K", 0)), 2),
            "stoch_d": round(float(latest.get("Stoch_D", 0)), 2),
            "volume_ratio": round(float(latest.get("Vol_Ratio", 1.0)), 2),
            "bb_percent_b": round(float(latest.get("BB_PercentB", 0.5)), 3),
        },
        position_size_hint=pos_size,
    )


def backtest_signals(df_with_indicators: pd.DataFrame, symbol: str, lookback_bars: int = 100) -> List[dict]:
    """Replay detector over recent bars for historical validation."""
    signals = []
    df = df_with_indicators.dropna().copy()
    start = max(1, len(df) - lookback_bars)
    for i in range(start, len(df)):
        window = df.iloc[: i + 1]
        try:
            sig = detect_scalp(window, symbol)
            if sig.direction != "NEUTRAL" and sig.confidence >= MIN_CONFIDENCE:
                signals.append({
                    "time": str(df.index[i]),
                    "direction": sig.direction,
                    "price": sig.entry,
                    "confidence": sig.confidence,
                    "sl": sig.stop_loss, "tp": sig.take_profit,
                })
        except Exception:
            continue
    return signals
