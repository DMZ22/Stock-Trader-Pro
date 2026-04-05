"""
Trajectory forecast module. Projects future price paths using:

1. **Linear trend** — OLS fit on last N log-returns, extrapolated forward.
2. **EMA momentum** — short/long EMA slope for directional continuation.
3. **ATR-based uncertainty cone** — widening confidence bands (±1σ, ±2σ)
   that grow as √t (stochastic diffusion model).
4. **Regime-adjusted drift** — in strong trends, drift = recent momentum;
   in ranging markets, drift decays toward mean (Ornstein-Uhlenbeck).

This gives "ghost lines" that appear as dashed forecast trajectories on the
chart — a central path plus upper/lower confidence cones.
"""
import math
import numpy as np
import pandas as pd
from datetime import timedelta


INTERVAL_DELTAS = {
    "1m": timedelta(minutes=1), "2m": timedelta(minutes=2), "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15), "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1), "60m": timedelta(hours=1),
    "1d": timedelta(days=1), "1wk": timedelta(weeks=1), "1mo": timedelta(days=30),
}


def _estimate_drift_and_vol(close: pd.Series, lookback: int = 30) -> tuple:
    """Estimate drift (mean log-return) and volatility (stdev) over lookback window."""
    log_ret = np.log(close / close.shift(1)).dropna().tail(lookback)
    if len(log_ret) < 5:
        return 0.0, 0.01
    mu = float(log_ret.mean())
    sigma = float(log_ret.std(ddof=1))
    if math.isnan(sigma) or sigma == 0:
        sigma = 0.01
    return mu, sigma


def _linear_trend_projection(close: pd.Series, lookback: int, steps: int) -> np.ndarray:
    """OLS linear regression on recent closes, projected forward."""
    y = close.tail(lookback).values
    x = np.arange(len(y), dtype=float)
    if len(y) < 3:
        return np.array([float(y[-1])] * steps)
    slope, intercept = np.polyfit(x, y, 1)
    future_x = np.arange(len(y), len(y) + steps, dtype=float)
    return slope * future_x + intercept


def project_trajectory(df: pd.DataFrame, steps: int = 20, lookback: int = 30,
                        interval: str = "1d", regime: str = "RANGING") -> dict:
    """
    Generate forward trajectory with confidence bands.

    Args:
        df: OHLCV DataFrame with indicators (needs ATR_14 column ideally).
        steps: Number of bars to forecast.
        lookback: Historical bars to fit trend/volatility.
        interval: Bar interval for timestamp generation.
        regime: Current market regime - controls drift behavior.

    Returns dict with:
        times: future timestamps
        central: expected price path (main ghost line)
        upper_1sd, lower_1sd: ±1σ cone (68% confidence)
        upper_2sd, lower_2sd: ±2σ cone (95% confidence)
        linear: pure linear extrapolation (secondary ghost line)
        expected_move_pct: % change at final forecast bar
        mean_drift: per-bar drift estimate
    """
    if len(df) < 10:
        return {}

    close = df["Close"]
    last_price = float(close.iloc[-1])
    last_time = df.index[-1]
    delta = INTERVAL_DELTAS.get(interval, timedelta(days=1))

    # Future timestamps
    future_times = [last_time + delta * (i + 1) for i in range(steps)]

    # Drift & vol estimation (log-return based)
    mu, sigma = _estimate_drift_and_vol(close, lookback)

    # Regime-adjusted drift
    if regime == "STRONG_TREND":
        drift = mu * 1.2  # amplify trend
    elif regime == "WEAK_TREND":
        drift = mu * 1.0
    elif regime in ("RANGING", "TIGHT_RANGE"):
        drift = mu * 0.3  # mean-reversion damping
    elif regime == "VOLATILE_CHOP":
        drift = mu * 0.1
    else:
        drift = mu

    # Geometric Brownian-motion-style central path
    central = np.zeros(steps)
    upper_1sd = np.zeros(steps)
    lower_1sd = np.zeros(steps)
    upper_2sd = np.zeros(steps)
    lower_2sd = np.zeros(steps)
    for i in range(steps):
        t = i + 1
        # central: last_price * exp(drift * t)
        central[i] = last_price * math.exp(drift * t)
        # Volatility cone grows as √t
        sigma_t = sigma * math.sqrt(t)
        upper_1sd[i] = last_price * math.exp(drift * t + sigma_t)
        lower_1sd[i] = last_price * math.exp(drift * t - sigma_t)
        upper_2sd[i] = last_price * math.exp(drift * t + 2 * sigma_t)
        lower_2sd[i] = last_price * math.exp(drift * t - 2 * sigma_t)

    # Linear regression projection as secondary ghost line
    linear = _linear_trend_projection(close, lookback, steps)

    final_pct = (central[-1] - last_price) / last_price * 100 if last_price else 0.0

    return {
        "times": [t.isoformat() for t in future_times],
        "central": [float(x) for x in central],
        "linear": [float(x) for x in linear],
        "upper_1sd": [float(x) for x in upper_1sd],
        "lower_1sd": [float(x) for x in lower_1sd],
        "upper_2sd": [float(x) for x in upper_2sd],
        "lower_2sd": [float(x) for x in lower_2sd],
        "expected_move_pct": round(final_pct, 2),
        "mean_drift": round(drift, 6),
        "volatility": round(sigma, 6),
        "steps": steps,
        "interval": interval,
        "regime_used": regime,
    }


def expected_move_over_horizon(df: pd.DataFrame, horizon_bars: int = 10,
                                interval: str = "5m") -> dict:
    """
    Compute expected % move over horizon using recent realized volatility.
    Used to filter signals targeting 2-5% moves.

    Returns dict with expected_move_pct (1σ) and range_low/range_high.
    """
    if len(df) < 10 or "ATR_14" not in df.columns:
        return {"expected_move_pct": 0, "ok": False}
    last_price = float(df["Close"].iloc[-1])
    atr = float(df["ATR_14"].iloc[-1])
    if last_price <= 0 or atr <= 0:
        return {"expected_move_pct": 0, "ok": False}
    # Per-bar volatility as fraction
    atr_pct = atr / last_price
    # Scale by sqrt(horizon) for multi-bar expected range
    expected_pct = atr_pct * math.sqrt(horizon_bars) * 100
    return {
        "ok": True,
        "horizon_bars": horizon_bars,
        "expected_move_pct": round(expected_pct, 2),
        "atr_pct_per_bar": round(atr_pct * 100, 3),
        "fits_2_5_pct_target": 2.0 <= expected_pct <= 5.0,
        "range_low": round(last_price * (1 - expected_pct / 100), 4),
        "range_high": round(last_price * (1 + expected_pct / 100), 4),
    }
