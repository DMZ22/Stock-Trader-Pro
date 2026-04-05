"""Base provider interface and exceptions."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pandas as pd


class ProviderError(Exception):
    """Base exception for provider errors."""


class RateLimitError(ProviderError):
    """Rate limit exceeded."""


class DataNotFoundError(ProviderError):
    """Data not available for requested symbol."""


class AuthenticationError(ProviderError):
    """Invalid or missing API key."""


@dataclass
class Quote:
    """Normalized real-time quote."""
    symbol: str
    price: float
    change: float
    change_pct: float
    high: float
    low: float
    open: float
    prev_close: float
    volume: Optional[float] = None
    timestamp: Optional[int] = None
    provider: str = ""


class MarketDataProvider(ABC):
    """Abstract interface for market data providers."""

    name: str = "base"
    requires_key: bool = False

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if self.requires_key and not api_key:
            raise AuthenticationError(f"{self.name} requires an API key")

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider can be used (has key etc.)."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Return a real-time quote."""

    @abstractmethod
    def get_candles(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        """
        Return OHLCV historical data.
        interval: '1m','5m','15m','30m','1h','1d','1wk'
        period: '1d','5d','1mo','3mo','6mo','1y','2y','5y','max'
        Returns DataFrame indexed by datetime with columns: Open, High, Low, Close, Volume
        """

    def get_company_profile(self, symbol: str) -> dict:
        """Optional: return company/instrument metadata."""
        return {}
