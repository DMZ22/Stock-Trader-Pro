"""
Scalp trade signal engine with confluence across:
  - Core indicators (EMA, VWAP, Supertrend, RSI, MACD, Volume, ADX, Stochastic)
  - Price action patterns (engulfing, hammer, stars)
  - Market regime (trending vs ranging adjusts strategy)
  - Support/resistance levels (dynamic SL/TP snapping)
  - Higher-timeframe trend (optional, boosts confidence when aligned)
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List
import pandas as pd
import math
from .patterns import detect_patterns, classify_regime, find_levels


def _safe_float(v, default=0.0, ndigits=4):
    """Convert to float, replacing NaN/Inf with default."""
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return round(f, ndigits)
    except (TypeError, ValueError):
        return default


# Risk management defaults
ATR_SL_MULT = 1.5   # Stop-loss distance = 1.5 * ATR
ATR_TP_MULT = 3.0   # Take-profit distance = 3.0 * ATR (2:1 R/R)
MIN_CONFIDENCE = 55


@dataclass
class ScalpSignal:
    symbol: str
    timestamp: str
    direction: str
    action: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    risk_pct: float
    reward_pct: float
    confidence: float
    strength: str
    reasons: List[str] = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    position_size_hint: Optional[dict] = None
    patterns: dict = field(default_factory=dict)
    regime: dict = field(default_factory=dict)
    levels: dict = field(default_factory=dict)
    htf_trend: Optional[str] = None

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

    adx_v = latest.get("ADX_14", 0)
    di_plus = latest.get("DI_PLUS", 0)
    di_minus = latest.get("DI_MINUS", 0)
    if adx_v > 25 and di_plus > di_minus:
        score += 10
        reasons.append(f"ADX {adx_v:.1f} confirms strong trend, +DI > -DI")
    elif adx_v < 20:
        score -= 5

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


def _strength_label(c: float) -> str:
    if c >= 80: return "STRONG"
    if c >= 65: return "MODERATE"
    return "WEAK"


def _apply_patterns(direction: str, patterns: dict, score: float, reasons: list) -> float:
    """Adjust score based on price action patterns aligning with direction."""
    if direction == "LONG":
        for p in patterns.get("bullish", []):
            score += 8; reasons.append(f"Pattern: {p} (bullish)")
        for p in patterns.get("bearish", []):
            score -= 10; reasons.append(f"Warning: {p} (bearish pattern against LONG)")
    elif direction == "SHORT":
        for p in patterns.get("bearish", []):
            score += 8; reasons.append(f"Pattern: {p} (bearish)")
        for p in patterns.get("bullish", []):
            score -= 10; reasons.append(f"Warning: {p} (bullish pattern against SHORT)")
    return score


def _apply_regime(direction: str, regime: dict, score: float, reasons: list) -> float:
    r = regime.get("regime", "UNKNOWN")
    if r == "STRONG_TREND":
        score += 5; reasons.append("Regime: strong trend (momentum favored)")
    elif r == "VOLATILE_CHOP":
        score -= 10; reasons.append("Regime: volatile chop (avoid - low edge)")
    elif r == "TIGHT_RANGE":
        reasons.append("Regime: tight range (breakout pending)")
    return score


def _apply_htf_trend(direction: str, htf_trend: Optional[str], score: float, reasons: list) -> float:
    """Higher-timeframe alignment is a major confidence booster."""
    if not htf_trend:
        return score
    if (direction == "LONG" and htf_trend == "UP") or (direction == "SHORT" and htf_trend == "DOWN"):
        score += 12
        reasons.append(f"HTF trend: {htf_trend} (aligned with entry - strong confluence)")
    elif (direction == "LONG" and htf_trend == "DOWN") or (direction == "SHORT" and htf_trend == "UP"):
        score -= 15
        reasons.append(f"HTF trend: {htf_trend} (counter to entry - trade against trend)")
    return score


def compute_htf_trend(htf_df: pd.DataFrame) -> str:
    """Determine higher-timeframe trend from EMA stack + ADX."""
    if htf_df is None or len(htf_df) < 20:
        return "NEUTRAL"
    latest = htf_df.iloc[-1]
    ema9 = latest.get("EMA_9", 0)
    ema21 = latest.get("EMA_21", 0)
    sma50 = latest.get("SMA_50", 0)
    if ema9 > ema21 > sma50: return "UP"
    if ema9 < ema21 < sma50: return "DOWN"
    return "NEUTRAL"


def detect_scalp(df: pd.DataFrame, symbol: str,
                 account_size: float = 10000.0, risk_per_trade_pct: float = 1.0,
                 htf_df: Optional[pd.DataFrame] = None,
                 snap_to_levels: bool = True) -> ScalpSignal:
    """
    Analyze most recent bar and produce a scalp trade signal.

    htf_df: optional higher-timeframe DataFrame with indicators for confluence.
    snap_to_levels: adjust SL/TP to nearby support/resistance if within 50% ATR.
    """
    if len(df) < 2:
        raise ValueError("Need at least 2 bars")

    df_clean = df.dropna(subset=["EMA_9", "EMA_21", "RSI_14", "ATR_14", "VWAP"])
    if len(df_clean) < 2:
        raise ValueError("Insufficient indicator data")

    latest = df_clean.iloc[-1]
    prev = df_clean.iloc[-2]
    close = float(latest["Close"])
    atr_val = float(latest["ATR_14"])
    timestamp = str(df_clean.index[-1])

    # Core scoring
    long_score, long_reasons = _score_long(latest, prev)
    short_score, short_reasons = _score_short(latest, prev)

    # Context modules
    patterns = detect_patterns(df_clean)
    regime = classify_regime(df_clean)
    levels = find_levels(df_clean)
    htf_trend = compute_htf_trend(htf_df) if htf_df is not None else None

    # Apply context adjustments
    long_score = _apply_patterns("LONG", patterns, long_score, long_reasons)
    long_score = _apply_regime("LONG", regime, long_score, long_reasons)
    long_score = _apply_htf_trend("LONG", htf_trend, long_score, long_reasons)
    short_score = _apply_patterns("SHORT", patterns, short_score, short_reasons)
    short_score = _apply_regime("SHORT", regime, short_score, short_reasons)
    short_score = _apply_htf_trend("SHORT", htf_trend, short_score, short_reasons)

    # Decide direction
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
        entry = close; stop_loss = close; take_profit = close

    # Snap SL/TP to nearby support/resistance
    if snap_to_levels and direction != "NEUTRAL":
        snap_threshold = atr_val * 0.5
        if direction == "LONG":
            ns = levels.get("nearest_support")
            nr = levels.get("nearest_resistance")
            if ns and abs(stop_loss - ns) < snap_threshold and ns < entry:
                stop_loss = ns * 0.999; reasons.append(f"SL snapped to support {ns:.2f}")
            if nr and abs(take_profit - nr) < snap_threshold and nr > entry:
                take_profit = nr * 0.999; reasons.append(f"TP snapped to resistance {nr:.2f}")
        else:
            ns = levels.get("nearest_support")
            nr = levels.get("nearest_resistance")
            if nr and abs(stop_loss - nr) < snap_threshold and nr > entry:
                stop_loss = nr * 1.001; reasons.append(f"SL snapped to resistance {nr:.2f}")
            if ns and abs(take_profit - ns) < snap_threshold and ns < entry:
                take_profit = ns * 1.001; reasons.append(f"TP snapped to support {ns:.2f}")

    # Risk/reward
    if direction != "NEUTRAL":
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        rr = reward / risk if risk > 0 else 0
        risk_pct = (risk / entry * 100) if entry else 0
        reward_pct = (reward / entry * 100) if entry else 0
    else:
        rr = 0; risk_pct = 0; reward_pct = 0

    # Action
    if direction == "NEUTRAL":
        action = "WAIT"
    elif confidence >= MIN_CONFIDENCE:
        action = "TRADE"
    else:
        action = "WATCH"

    # Position sizing
    pos_size = None
    if direction != "NEUTRAL" and risk_pct > 0:
        dollar_risk = account_size * (risk_per_trade_pct / 100)
        risk_amt = abs(entry - stop_loss)
        shares = int(dollar_risk / risk_amt) if risk_amt > 0 else 0
        pos_size = {
            "account": account_size, "risk_per_trade_pct": risk_per_trade_pct,
            "dollar_risk": round(dollar_risk, 2), "shares": shares,
            "position_value": round(shares * entry, 2),
        }

    return ScalpSignal(
        symbol=symbol, timestamp=timestamp, direction=direction, action=action,
        entry=round(entry, 4), stop_loss=round(stop_loss, 4), take_profit=round(take_profit, 4),
        risk_reward=round(rr, 2), risk_pct=round(risk_pct, 2), reward_pct=round(reward_pct, 2),
        confidence=round(confidence, 1), strength=_strength_label(confidence),
        reasons=reasons,
        indicators={
            "price": _safe_float(close, 0, 4),
            "ema_9": _safe_float(latest.get("EMA_9"), 0, 4),
            "ema_21": _safe_float(latest.get("EMA_21"), 0, 4),
            "sma_50": _safe_float(latest.get("SMA_50"), 0, 4),
            "vwap": _safe_float(latest.get("VWAP"), 0, 4),
            "rsi": _safe_float(latest.get("RSI_14"), 50, 2),
            "macd": _safe_float(latest.get("MACD"), 0, 4),
            "macd_signal": _safe_float(latest.get("MACD_Signal"), 0, 4),
            "macd_hist": _safe_float(latest.get("MACD_Hist"), 0, 4),
            "adx": _safe_float(latest.get("ADX_14"), 0, 2),
            "di_plus": _safe_float(latest.get("DI_PLUS"), 0, 2),
            "di_minus": _safe_float(latest.get("DI_MINUS"), 0, 2),
            "atr": _safe_float(atr_val, 0, 4),
            "atr_pct": _safe_float((atr_val / close * 100) if close else 0, 0, 2),
            "supertrend_dir": int(latest.get("ST_Direction") or 0) if not (isinstance(latest.get("ST_Direction"), float) and math.isnan(latest.get("ST_Direction"))) else 0,
            "supertrend": _safe_float(latest.get("Supertrend"), 0, 4),
            "stoch_k": _safe_float(latest.get("Stoch_K"), 50, 2),
            "stoch_d": _safe_float(latest.get("Stoch_D"), 50, 2),
            "williams_r": _safe_float(latest.get("Williams_R"), -50, 2),
            "cci": _safe_float(latest.get("CCI_20"), 0, 2),
            "mfi": _safe_float(latest.get("MFI_14"), 50, 2),
            "cmf": _safe_float(latest.get("CMF_20"), 0, 4),
            "obv": _safe_float(latest.get("OBV"), 0, 0),
            "volume_ratio": _safe_float(latest.get("Vol_Ratio"), 1.0, 2),
            "bb_upper": _safe_float(latest.get("BB_Upper"), 0, 4),
            "bb_middle": _safe_float(latest.get("BB_Middle"), 0, 4),
            "bb_lower": _safe_float(latest.get("BB_Lower"), 0, 4),
            "bb_width": _safe_float(latest.get("BB_Width"), 0, 4),
            "bb_percent_b": _safe_float(latest.get("BB_PercentB"), 0.5, 3),
            "long_score": _safe_float(long_score, 0, 1),
            "short_score": _safe_float(short_score, 0, 1),
        },
        position_size_hint=pos_size,
        patterns=patterns, regime=regime, levels=levels, htf_trend=htf_trend,
    )


def backtest_signals(df: pd.DataFrame, symbol: str, lookback_bars: int = 100) -> dict:
    """Replay detector over recent bars. Reports hit rate with forward bars."""
    signals = []
    hits = 0; misses = 0
    df = df.dropna().copy()
    start = max(30, len(df) - lookback_bars)
    forward_bars = 10
    for i in range(start, len(df) - forward_bars):
        window = df.iloc[: i + 1]
        try:
            sig = detect_scalp(window, symbol, snap_to_levels=False)
            if sig.direction == "NEUTRAL" or sig.confidence < MIN_CONFIDENCE:
                continue
            future = df.iloc[i + 1: i + 1 + forward_bars]
            fut_high = float(future["High"].max())
            fut_low = float(future["Low"].min())
            if sig.direction == "LONG":
                if fut_high >= sig.take_profit: hit = True
                elif fut_low <= sig.stop_loss: hit = False
                else: continue
            else:
                if fut_low <= sig.take_profit: hit = True
                elif fut_high >= sig.stop_loss: hit = False
                else: continue
            if hit: hits += 1
            else: misses += 1
            signals.append({
                "time": str(df.index[i]), "direction": sig.direction,
                "entry": sig.entry, "sl": sig.stop_loss, "tp": sig.take_profit,
                "confidence": sig.confidence, "hit": hit,
            })
        except Exception:
            continue
    total = hits + misses
    hit_rate = (hits / total * 100) if total else 0
    return {"signals": signals, "total": total, "wins": hits, "losses": misses,
            "hit_rate": round(hit_rate, 1), "lookback_bars": lookback_bars}
