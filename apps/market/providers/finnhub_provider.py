"""Finnhub provider (60 req/min free tier). Best for US stocks and crypto."""
import logging
import time
import requests
import pandas as pd
from .base import MarketDataProvider, Quote, DataNotFoundError, ProviderError, RateLimitError

logger = logging.getLogger(__name__)


class FinnhubProvider(MarketDataProvider):
    name = "finnhub"
    requires_key = True
    BASE_URL = "https://finnhub.io/api/v1"

    # Finnhub resolution mapping
    RESOLUTION_MAP = {
        "1m": "1", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "60m": "60", "1d": "D", "1wk": "W", "1mo": "M",
    }

    PERIOD_DAYS = {
        "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825, "max": 3650,
    }

    def __init__(self, api_key=None):
        super().__init__(api_key)
        self.session = requests.Session()
        self.session.headers["X-Finnhub-Token"] = self.api_key or ""

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _request(self, endpoint: str, params: dict) -> dict:
        try:
            r = self.session.get(f"{self.BASE_URL}/{endpoint}", params=params, timeout=10)
            if r.status_code == 429:
                raise RateLimitError("Finnhub rate limit hit")
            if r.status_code == 401:
                raise ProviderError("Finnhub invalid API key")
            if r.status_code != 200:
                raise ProviderError(f"Finnhub HTTP {r.status_code}: {r.text[:200]}")
            return r.json()
        except requests.RequestException as e:
            raise ProviderError(f"Finnhub network error: {e}") from e

    def get_quote(self, symbol: str) -> Quote:
        data = self._request("quote", {"symbol": symbol})
        price = float(data.get("c") or 0)
        if not price:
            raise DataNotFoundError(f"No Finnhub quote for {symbol}")
        prev = float(data.get("pc") or 0)
        return Quote(
            symbol=symbol, price=price,
            change=float(data.get("d") or 0),
            change_pct=float(data.get("dp") or 0),
            high=float(data.get("h") or 0),
            low=float(data.get("l") or 0),
            open=float(data.get("o") or 0),
            prev_close=prev,
            timestamp=int(data.get("t") or 0),
            provider=self.name,
        )

    def get_candles(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        resolution = self.RESOLUTION_MAP.get(interval)
        if not resolution:
            raise ProviderError(f"Finnhub unsupported interval: {interval}")
        now = int(time.time())
        days = self.PERIOD_DAYS.get(period, 365)
        from_ts = now - days * 86400
        data = self._request("stock/candle", {
            "symbol": symbol, "resolution": resolution, "from": from_ts, "to": now
        })
        if data.get("s") != "ok":
            raise DataNotFoundError(f"Finnhub no candles for {symbol}: {data.get('s')}")
        df = pd.DataFrame({
            "Open": data["o"], "High": data["h"], "Low": data["l"],
            "Close": data["c"], "Volume": data.get("v", [0]*len(data["c"])),
        }, index=pd.to_datetime(data["t"], unit="s"))
        return df.sort_index()

    def get_company_profile(self, symbol: str) -> dict:
        try:
            data = self._request("stock/profile2", {"symbol": symbol})
            if not data:
                return {"name": symbol}
            return {
                "name": data.get("name", symbol),
                "sector": data.get("finnhubIndustry", ""),
                "industry": data.get("finnhubIndustry", ""),
                "market_cap": (data.get("marketCapitalization") or 0) * 1_000_000,
                "currency": data.get("currency", "USD"),
                "exchange": data.get("exchange", ""),
                "logo": data.get("logo", ""),
                "website": data.get("weburl", ""),
            }
        except Exception as e:
            logger.warning("finnhub profile failed: %s", e)
            return {"name": symbol}
