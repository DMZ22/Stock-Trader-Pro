"""
Market data service: orchestrates multiple providers with fallback, retry,
caching, and rate limiting. This is the ONLY interface the rest of the app
should use for market data.
"""
import logging
import hashlib
from typing import List, Optional
import pandas as pd
from django.conf import settings
from django.core.cache import cache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .providers import (
    MarketDataProvider, ProviderError, RateLimitError, DataNotFoundError,
    YFinanceProvider, FinnhubProvider, AlphaVantageProvider, TwelveDataProvider,
)
from .providers.base import Quote
from .rate_limiter import REGISTRY

logger = logging.getLogger(__name__)


# Provider priority: best data quality → fallback
DEFAULT_PROVIDER_ORDER = ["finnhub", "twelve_data", "alpha_vantage", "yfinance"]

# Cache TTLs (seconds)
QUOTE_TTL = 30
CANDLES_TTL = 300
PROFILE_TTL = 3600


class MarketDataService:
    """Unified market data facade."""

    def __init__(self, provider_order: Optional[List[str]] = None):
        self.provider_order = provider_order or DEFAULT_PROVIDER_ORDER
        self.providers: List[MarketDataProvider] = self._build_providers()
        logger.info("MarketDataService ready with: %s", [p.name for p in self.providers])

    def _build_providers(self) -> List[MarketDataProvider]:
        api_keys = settings.API_KEYS
        candidates = {
            "finnhub": lambda: FinnhubProvider(api_keys.get("FINNHUB")),
            "twelve_data": lambda: TwelveDataProvider(api_keys.get("TWELVE_DATA")),
            "alpha_vantage": lambda: AlphaVantageProvider(api_keys.get("ALPHA_VANTAGE")),
            "yfinance": lambda: YFinanceProvider(),
        }
        providers = []
        for name in self.provider_order:
            if name not in candidates:
                continue
            try:
                p = candidates[name]()
                if p.is_available():
                    providers.append(p)
            except Exception as e:
                logger.debug("Provider %s unavailable: %s", name, e)
        if not providers:
            # yfinance is always available
            providers.append(YFinanceProvider())
        return providers

    def _cache_key(self, kind: str, *parts) -> str:
        key = f"mkt:{kind}:" + ":".join(str(p) for p in parts)
        # Hash long keys
        if len(key) > 200:
            key = f"mkt:{kind}:" + hashlib.md5(key.encode()).hexdigest()
        return key

    def _apply_rate_limit(self, provider_name: str):
        rpm = settings.RATE_LIMITS.get(provider_name.upper())
        if rpm:
            REGISTRY.get(provider_name, rpm).acquire()

    # -------------------------------------------------------------------------
    # QUOTE
    # -------------------------------------------------------------------------
    def get_quote(self, symbol: str, use_cache: bool = True) -> Quote:
        symbol = symbol.strip().upper()
        ckey = self._cache_key("quote", symbol)
        if use_cache:
            cached = cache.get(ckey)
            if cached:
                return cached

        last_err = None
        for provider in self.providers:
            try:
                self._apply_rate_limit(provider.name)
                quote = self._retry_quote(provider, symbol)
                cache.set(ckey, quote, QUOTE_TTL)
                return quote
            except (DataNotFoundError, ProviderError) as e:
                last_err = e
                logger.warning("[%s] quote failed for %s: %s", provider.name, symbol, e)
                continue
        raise ProviderError(f"All providers failed for {symbol}: {last_err}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((RateLimitError, ProviderError)),
        reraise=True,
    )
    def _retry_quote(self, provider, symbol):
        return provider.get_quote(symbol)

    # -------------------------------------------------------------------------
    # CANDLES
    # -------------------------------------------------------------------------
    def get_candles(self, symbol: str, interval: str = "1d", period: str = "1y",
                    use_cache: bool = True) -> pd.DataFrame:
        symbol = symbol.strip().upper()
        ckey = self._cache_key("candles", symbol, interval, period)
        if use_cache:
            cached = cache.get(ckey)
            if cached is not None:
                return cached

        last_err = None
        for provider in self.providers:
            try:
                self._apply_rate_limit(provider.name)
                df = self._retry_candles(provider, symbol, interval, period)
                if df is None or df.empty:
                    continue
                cache.set(ckey, df, CANDLES_TTL)
                logger.info("[%s] candles %s %s/%s: %d bars", provider.name, symbol, interval, period, len(df))
                return df
            except (DataNotFoundError, ProviderError) as e:
                last_err = e
                logger.warning("[%s] candles failed for %s: %s", provider.name, symbol, e)
                continue
        raise ProviderError(f"All providers failed for candles {symbol}: {last_err}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    def _retry_candles(self, provider, symbol, interval, period):
        return provider.get_candles(symbol, interval, period)

    # -------------------------------------------------------------------------
    # PROFILE
    # -------------------------------------------------------------------------
    def get_profile(self, symbol: str, use_cache: bool = True) -> dict:
        symbol = symbol.strip().upper()
        ckey = self._cache_key("profile", symbol)
        if use_cache:
            cached = cache.get(ckey)
            if cached:
                return cached
        # Try providers in order
        for provider in self.providers:
            try:
                self._apply_rate_limit(provider.name)
                profile = provider.get_company_profile(symbol)
                if profile and profile.get("name"):
                    cache.set(ckey, profile, PROFILE_TTL)
                    return profile
            except Exception:
                continue
        return {"name": symbol}


# Singleton instance
_service = None


def get_market_service() -> MarketDataService:
    global _service
    if _service is None:
        _service = MarketDataService()
    return _service
