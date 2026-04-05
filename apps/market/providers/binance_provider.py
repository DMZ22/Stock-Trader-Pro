"""Binance public API — free, no API key, excellent for crypto OHLCV."""
import logging
import requests
import pandas as pd
from .base import MarketDataProvider, Quote, DataNotFoundError, ProviderError, RateLimitError

logger = logging.getLogger(__name__)


class BinanceProvider(MarketDataProvider):
    name = "binance"
    requires_key = False
    BASE_URL = "https://api.binance.com/api/v3"

    INTERVAL_MAP = {
        "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "60m": "1h", "2h": "2h", "4h": "4h", "6h": "6h",
        "8h": "8h", "12h": "12h", "1d": "1d", "3d": "3d",
        "1wk": "1w", "1w": "1w", "1mo": "1M",
    }

    def __init__(self, api_key=None):
        super().__init__(api_key)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Stock-Trader-Pro/1.1"

    def is_available(self) -> bool:
        return True

    def _to_binance_symbol(self, symbol: str) -> str:
        """Convert BTC-USD / BTC-USDT → BTCUSDT."""
        s = symbol.upper().strip()
        # Already clean binance pair
        if not any(c in s for c in ("-", "/", "=")):
            return s
        # Common conversions
        for suffix in ("-USDT", "-USDC", "-BUSD", "/USDT", "/USD"):
            if s.endswith(suffix):
                return s.replace(suffix, "USDT").replace("/", "")
        if s.endswith("-USD"):
            # Binance uses USDT primarily; convert BTC-USD → BTCUSDT
            return s.replace("-USD", "USDT")
        return s.replace("-", "").replace("/", "")

    def _is_supported(self, symbol: str) -> bool:
        """Binance only supports crypto pairs."""
        s = symbol.upper().strip()
        return any(s.endswith(suf) for suf in
                    ("-USD", "-USDT", "-USDC", "-BUSD", "/USDT", "/USD", "USDT", "USDC", "BUSD"))

    def _request(self, endpoint: str, params: dict = None) -> dict:
        try:
            r = self.session.get(f"{self.BASE_URL}/{endpoint}", params=params or {}, timeout=10)
            if r.status_code == 429 or r.status_code == 418:
                raise RateLimitError("Binance rate limit")
            if r.status_code == 400:
                raise DataNotFoundError(f"Binance symbol not found")
            if r.status_code != 200:
                raise ProviderError(f"Binance HTTP {r.status_code}")
            return r.json()
        except requests.RequestException as e:
            raise ProviderError(f"Binance network error: {e}") from e

    def get_quote(self, symbol: str) -> Quote:
        if not self._is_supported(symbol):
            raise DataNotFoundError(f"Binance: {symbol} not a crypto pair")
        bsym = self._to_binance_symbol(symbol)
        data = self._request("ticker/24hr", {"symbol": bsym})
        price = float(data.get("lastPrice") or 0)
        if not price:
            raise DataNotFoundError(f"Binance no price for {bsym}")
        prev = float(data.get("prevClosePrice") or data.get("openPrice") or 0)
        return Quote(
            symbol=symbol.upper(), price=price,
            change=float(data.get("priceChange") or 0),
            change_pct=float(data.get("priceChangePercent") or 0),
            high=float(data.get("highPrice") or 0),
            low=float(data.get("lowPrice") or 0),
            open=float(data.get("openPrice") or 0),
            prev_close=prev,
            volume=float(data.get("volume") or 0),
            provider=self.name,
        )

    def get_candles(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        if not self._is_supported(symbol):
            raise DataNotFoundError(f"Binance: {symbol} not a crypto pair")
        bsym = self._to_binance_symbol(symbol)
        bi = self.INTERVAL_MAP.get(interval)
        if not bi:
            raise ProviderError(f"Binance: interval {interval} not supported")
        # Binance max 1000 bars per request
        data = self._request("klines", {"symbol": bsym, "interval": bi, "limit": 1000})
        if not data or not isinstance(data, list):
            raise DataNotFoundError(f"Binance no klines for {bsym}")
        # Kline format: [openTime, open, high, low, close, volume, closeTime, ...]
        rows = []
        for k in data:
            rows.append({
                "dt": pd.to_datetime(int(k[0]), unit="ms"),
                "Open": float(k[1]), "High": float(k[2]),
                "Low": float(k[3]), "Close": float(k[4]),
                "Volume": float(k[5]),
            })
        df = pd.DataFrame(rows).set_index("dt").sort_index()
        return df

    def get_company_profile(self, symbol: str) -> dict:
        return {"name": symbol, "exchange": "Binance", "currency": "USDT"}
