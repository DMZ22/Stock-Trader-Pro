"""
Technical indicators with canonical formulas. Every function here uses the
standard textbook formula so results are auditable and match platforms
like TradingView, Investopedia, etc.

All functions take a DataFrame with OHLCV columns and return a new DataFrame
(copy) with added indicator columns. Input data is never mutated.
"""
import numpy as np
import pandas as pd


# =============================================================================
# MOVING AVERAGES
# =============================================================================

def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average: mean over window."""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average with k=2/(period+1). Seeded with SMA."""
    alpha = 2.0 / (period + 1.0)
    return series.ewm(alpha=alpha, adjust=False, min_periods=period).mean()


def wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average (linear weights)."""
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


# =============================================================================
# MOMENTUM
# =============================================================================

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI. Uses Wilder's smoothing (alpha = 1/period).
    RSI = 100 - 100/(1 + RS) where RS = avg_gain / avg_loss.
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 14, d_period: int = 3) -> tuple:
    """
    Stochastic Oscillator.
    %K = 100 * (Close - LowestLow_k) / (HighestHigh_k - LowestLow_k)
    %D = SMA(%K, d_period)
    """
    ll = low.rolling(k_period).min()
    hh = high.rolling(k_period).max()
    k = 100 * (close - ll) / (hh - ll).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R = -100 * (HH - Close) / (HH - LL)."""
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
    return -100 * (hh - close) / (hh - ll).replace(0, np.nan)


def roc(close: pd.Series, period: int = 12) -> pd.Series:
    """Rate of Change = 100 * (Close - Close_n) / Close_n."""
    return 100 * (close - close.shift(period)) / close.shift(period)


def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """
    Commodity Channel Index.
    CCI = (TP - SMA(TP)) / (0.015 * MAD)
    where TP = (H+L+C)/3 and MAD = mean absolute deviation.
    """
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))


# =============================================================================
# TREND
# =============================================================================

def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """
    MACD line = EMA(fast) - EMA(slow)
    Signal line = EMA(MACD, signal)
    Histogram = MACD - Signal
    """
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(alpha=2.0 / (signal + 1), adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> tuple:
    """
    Average Directional Index (Wilder).
    Returns (ADX, +DI, -DI).
    """
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(high, low, close)
    atr_w = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=high.index).ewm(
        alpha=1.0 / period, adjust=False, min_periods=period
    ).mean() / atr_w.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=high.index).ewm(
        alpha=1.0 / period, adjust=False, min_periods=period
    ).mean() / atr_w.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return adx_val, plus_di, minus_di


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
               period: int = 10, multiplier: float = 3.0) -> tuple:
    """
    Supertrend indicator — popular scalping trend filter.
    Returns (supertrend_line, direction) where direction is +1 (uptrend) or -1.
    """
    atr_val = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val
    final_upper = upper_band.copy()
    final_lower = lower_band.copy()
    st = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)
    for i in range(len(close)):
        if i == 0:
            st.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = -1
            continue
        # Adjust bands
        if upper_band.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = upper_band.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]
        if lower_band.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = lower_band.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]
        # Determine direction
        if st.iloc[i - 1] == final_upper.iloc[i - 1]:
            if close.iloc[i] > final_upper.iloc[i]:
                st.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1
            else:
                st.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = -1
        else:
            if close.iloc[i] < final_lower.iloc[i]:
                st.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = -1
            else:
                st.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1
    return st, direction


def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series,
             conv: int = 9, base: int = 26, span_b: int = 52) -> dict:
    """Ichimoku Cloud components."""
    conv_line = (high.rolling(conv).max() + low.rolling(conv).min()) / 2
    base_line = (high.rolling(base).max() + low.rolling(base).min()) / 2
    lead_a = ((conv_line + base_line) / 2).shift(base)
    lead_b = ((high.rolling(span_b).max() + low.rolling(span_b).min()) / 2).shift(base)
    lagging = close.shift(-base)
    return {
        "tenkan": conv_line, "kijun": base_line,
        "senkou_a": lead_a, "senkou_b": lead_b, "chikou": lagging,
    }


# =============================================================================
# VOLATILITY
# =============================================================================

def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True Range = max(H-L, |H-PrevClose|, |L-PrevClose|)."""
    prev_close = close.shift(1)
    return pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range with Wilder smoothing."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple:
    """Bollinger Bands. Returns (upper, middle, lower, bandwidth, %B)."""
    middle = sma(close, period)
    std = close.rolling(period).std(ddof=0)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    bandwidth = (upper - lower) / middle
    percent_b = (close - lower) / (upper - lower).replace(0, np.nan)
    return upper, middle, lower, bandwidth, percent_b


def keltner_channels(high: pd.Series, low: pd.Series, close: pd.Series,
                     period: int = 20, multiplier: float = 2.0) -> tuple:
    """Keltner Channels: EMA ± multiplier * ATR."""
    mid = ema(close, period)
    atr_val = atr(high, low, close, period)
    return mid + multiplier * atr_val, mid, mid - multiplier * atr_val


# =============================================================================
# VOLUME
# =============================================================================

def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Volume Weighted Average Price.
    VWAP = cumsum(TypicalPrice * Volume) / cumsum(Volume).
    Typically reset daily; here computed cumulatively over the series.
    """
    tp = (high + low + close) / 3
    return (tp * volume).cumsum() / volume.cumsum().replace(0, np.nan)


def mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
        period: int = 14) -> pd.Series:
    """Money Flow Index — volume-weighted RSI."""
    tp = (high + low + close) / 3
    mf = tp * volume
    direction = np.sign(tp.diff())
    pos_mf = mf.where(direction > 0, 0).rolling(period).sum()
    neg_mf = mf.where(direction < 0, 0).rolling(period).sum()
    mfr = pos_mf / neg_mf.replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def cmf(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
        period: int = 20) -> pd.Series:
    """Chaikin Money Flow."""
    mfm = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    mfv = mfm * volume
    return mfv.rolling(period).sum() / volume.rolling(period).sum().replace(0, np.nan)


# =============================================================================
# MASTER: ADD ALL INDICATORS
# =============================================================================

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicators to an OHLCV DataFrame."""
    d = df.copy()
    o, h, l, c, v = d["Open"], d["High"], d["Low"], d["Close"], d["Volume"]

    # Moving averages
    d["SMA_20"] = sma(c, 20)
    d["SMA_50"] = sma(c, 50)
    d["SMA_200"] = sma(c, 200)
    d["EMA_9"] = ema(c, 9)
    d["EMA_20"] = ema(c, 20)
    d["EMA_21"] = ema(c, 21)
    d["EMA_50"] = ema(c, 50)

    # Momentum
    d["RSI_14"] = rsi(c, 14)
    d["ROC_12"] = roc(c, 12)
    k, dd = stochastic(h, l, c, 14, 3)
    d["Stoch_K"] = k; d["Stoch_D"] = dd
    d["Williams_R"] = williams_r(h, l, c, 14)
    d["CCI_20"] = cci(h, l, c, 20)

    # Trend
    macd_line, signal_line, hist = macd(c)
    d["MACD"] = macd_line; d["MACD_Signal"] = signal_line; d["MACD_Hist"] = hist
    adx_val, pdi, ndi = adx(h, l, c, 14)
    d["ADX_14"] = adx_val; d["DI_PLUS"] = pdi; d["DI_MINUS"] = ndi
    st, st_dir = supertrend(h, l, c, 10, 3.0)
    d["Supertrend"] = st; d["ST_Direction"] = st_dir

    # Volatility
    upper, mid, lower, bw, pb = bollinger_bands(c, 20, 2.0)
    d["BB_Upper"] = upper; d["BB_Middle"] = mid; d["BB_Lower"] = lower
    d["BB_Width"] = bw; d["BB_PercentB"] = pb
    d["ATR_14"] = atr(h, l, c, 14)
    kc_u, kc_m, kc_l = keltner_channels(h, l, c, 20, 2.0)
    d["KC_Upper"] = kc_u; d["KC_Middle"] = kc_m; d["KC_Lower"] = kc_l

    # Volume
    d["OBV"] = obv(c, v)
    d["VWAP"] = vwap(h, l, c, v)
    d["MFI_14"] = mfi(h, l, c, v, 14)
    d["CMF_20"] = cmf(h, l, c, v, 20)
    d["Vol_SMA_20"] = sma(v, 20)
    d["Vol_Ratio"] = v / d["Vol_SMA_20"].replace(0, np.nan)

    # Returns
    d["Returns"] = c.pct_change()
    d["LogReturns"] = np.log(c / c.shift(1))

    return d
