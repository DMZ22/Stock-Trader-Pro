"""Yahoo Finance provider (free, no API key required)."""
import logging
import pandas as pd
import yfinance as yf
from .base import MarketDataProvider, Quote, DataNotFoundError, ProviderError

logger = logging.getLogger(__name__)


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"
    requires_key = False

    # Interval/period compatibility constraints per yfinance
    INTRADAY_MAX_PERIOD = {
        "1m": "7d", "2m": "60d", "5m": "60d", "15m": "60d",
        "30m": "60d", "60m": "730d", "90m": "60d", "1h": "730d",
    }

    def is_available(self) -> bool:
        return True

    def _normalize_interval(self, interval: str) -> str:
        return {"1h": "60m"}.get(interval, interval)

    def _adjust_period(self, interval: str, period: str) -> str:
        """yfinance enforces max periods for intraday. Clamp accordingly."""
        if interval in self.INTRADAY_MAX_PERIOD:
            max_p = self.INTRADAY_MAX_PERIOD[interval]
            order = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]
            max_idx = {"7d": 2, "60d": 3, "730d": 7}.get(max_p, 7)
            if period in order and order.index(period) > max_idx:
                return max_p if max_p in order else "60d"
        return period

    def get_quote(self, symbol: str) -> Quote:
        """Get quote via the 1-day 1-minute candles endpoint (most reliable)."""
        try:
            # Use the daily candle endpoint for current price
            df = yf.download(symbol, period="5d", interval="1d",
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                raise DataNotFoundError(f"No price data for {symbol}")
            # Handle multi-ticker column MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            price = float(last["Close"])
            prev_close = float(prev["Close"])
            change = price - prev_close
            pct = (change / prev_close * 100) if prev_close else 0.0
            return Quote(
                symbol=symbol, price=price, change=change, change_pct=pct,
                high=float(last["High"]), low=float(last["Low"]),
                open=float(last["Open"]), prev_close=prev_close,
                volume=float(last.get("Volume", 0) or 0), provider=self.name,
            )
        except DataNotFoundError:
            raise
        except Exception as e:
            raise ProviderError(f"yfinance quote error: {e}") from e

    def get_candles(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        try:
            interval_norm = self._normalize_interval(interval)
            period_adj = self._adjust_period(interval_norm, period)
            df = yf.download(symbol, period=period_adj, interval=interval_norm,
                             progress=False, auto_adjust=True, threads=False)
            if df is None or df.empty:
                raise DataNotFoundError(f"No candles for {symbol} {interval} {period}")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            return df
        except DataNotFoundError:
            raise
        except Exception as e:
            raise ProviderError(f"yfinance candles error: {e}") from e

    def get_company_profile(self, symbol: str) -> dict:
        try:
            try:
                info = yf.Ticker(symbol).info or {}
            except Exception:
                info = {}
            return {
                "name": info.get("shortName") or info.get("longName") or symbol,
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "eps": info.get("trailingEps"),
                "beta": info.get("beta"),
                "dividend_yield": info.get("dividendYield"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "currency": info.get("currency", "USD"),
                "exchange": info.get("exchange", ""),
            }
        except Exception as e:
            logger.warning("yfinance profile failed for %s: %s", symbol, e)
            return {"name": symbol}
