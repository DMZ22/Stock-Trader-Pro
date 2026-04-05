"""Twelve Data provider (8 req/min free tier). Great for forex, crypto, stocks."""
import logging
import requests
import pandas as pd
from .base import MarketDataProvider, Quote, DataNotFoundError, ProviderError, RateLimitError

logger = logging.getLogger(__name__)


class TwelveDataProvider(MarketDataProvider):
    name = "twelve_data"
    requires_key = True
    BASE_URL = "https://api.twelvedata.com"

    INTERVAL_MAP = {
        "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
        "1h": "1h", "60m": "1h", "1d": "1day", "1wk": "1week", "1mo": "1month",
    }

    PERIOD_OUTPUTSIZE = {
        "1d": 100, "5d": 500, "1mo": 720, "3mo": 2000,
        "6mo": 4000, "1y": 5000, "2y": 5000, "5y": 5000, "max": 5000,
    }

    def __init__(self, api_key=None):
        super().__init__(api_key)
        self.session = requests.Session()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _request(self, endpoint: str, params: dict) -> dict:
        params["apikey"] = self.api_key
        try:
            r = self.session.get(f"{self.BASE_URL}/{endpoint}", params=params, timeout=15)
            if r.status_code == 429:
                raise RateLimitError("Twelve Data rate limit")
            if r.status_code != 200:
                raise ProviderError(f"Twelve Data HTTP {r.status_code}")
            data = r.json()
            if data.get("status") == "error":
                msg = data.get("message", "unknown")
                if "limit" in msg.lower():
                    raise RateLimitError(msg)
                raise DataNotFoundError(msg)
            return data
        except requests.RequestException as e:
            raise ProviderError(f"Twelve Data network error: {e}") from e

    def get_quote(self, symbol: str) -> Quote:
        data = self._request("quote", {"symbol": symbol})
        price = float(data.get("close") or 0)
        if not price:
            raise DataNotFoundError(f"No Twelve Data quote for {symbol}")
        return Quote(
            symbol=symbol, price=price,
            change=float(data.get("change") or 0),
            change_pct=float(data.get("percent_change") or 0),
            high=float(data.get("high") or 0),
            low=float(data.get("low") or 0),
            open=float(data.get("open") or 0),
            prev_close=float(data.get("previous_close") or 0),
            volume=float(data.get("volume") or 0),
            provider=self.name,
        )

    def get_candles(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        td_interval = self.INTERVAL_MAP.get(interval)
        if not td_interval:
            raise ProviderError(f"Twelve Data unsupported interval: {interval}")
        data = self._request("time_series", {
            "symbol": symbol, "interval": td_interval,
            "outputsize": self.PERIOD_OUTPUTSIZE.get(period, 1000),
        })
        values = data.get("values", [])
        if not values:
            raise DataNotFoundError(f"No Twelve Data candles for {symbol}")
        rows = []
        for v in values:
            rows.append({
                "dt": pd.to_datetime(v["datetime"]),
                "Open": float(v["open"]), "High": float(v["high"]),
                "Low": float(v["low"]), "Close": float(v["close"]),
                "Volume": float(v.get("volume", 0)),
            })
        return pd.DataFrame(rows).set_index("dt").sort_index()
