"""Kraken public API — free, no key, broad crypto coverage."""
import logging
import requests
import pandas as pd
from .base import MarketDataProvider, Quote, DataNotFoundError, ProviderError, RateLimitError

logger = logging.getLogger(__name__)


class KrakenProvider(MarketDataProvider):
    name = "kraken"
    requires_key = False
    BASE_URL = "https://api.kraken.com/0/public"

    # Kraken uses XBT for bitcoin, XXBT/ZUSD pair names internally
    SYMBOL_MAP = {
        "BTC-USD": "XBTUSD", "BTC-USDT": "XBTUSDT",
        "ETH-USD": "ETHUSD", "ETH-USDT": "ETHUSDT",
        "SOL-USD": "SOLUSD", "SOL-USDT": "SOLUSDT",
        "ADA-USD": "ADAUSD", "ADA-USDT": "ADAUSDT",
        "DOT-USD": "DOTUSD", "DOT-USDT": "DOTUSDT",
        "LINK-USD": "LINKUSD", "LINK-USDT": "LINKUSDT",
        "LTC-USD": "LTCUSD", "LTC-USDT": "LTCUSDT",
        "XRP-USD": "XRPUSD", "XRP-USDT": "XRPUSDT",
        "DOGE-USD": "XDGUSD", "DOGE-USDT": "XDGUSDT",
        "AVAX-USD": "AVAXUSD", "AVAX-USDT": "AVAXUSDT",
        "ATOM-USD": "ATOMUSD", "MATIC-USD": "MATICUSD",
        "UNI-USD": "UNIUSD", "ALGO-USD": "ALGOUSD",
        "XTZ-USD": "XTZUSD", "FIL-USD": "FILUSD",
    }

    # Kraken interval in minutes
    INTERVAL_MIN = {
        "1m": 1, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "60m": 60, "4h": 240, "1d": 1440, "1wk": 10080,
    }

    def __init__(self, api_key=None):
        super().__init__(api_key)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Stock-Trader-Pro/1.2"

    def is_available(self) -> bool:
        return True

    def _kraken_pair(self, symbol: str) -> str:
        s = symbol.upper().strip()
        if s in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[s]
        # Try auto-mapping
        for suffix in ("-USDT", "-USDC"):
            if s.endswith(suffix):
                base = s.replace(suffix, "")
                return f"{base}USDT"
        if s.endswith("-USD"):
            return s.replace("-USD", "USD")
        return s.replace("-", "").replace("/", "")

    def _is_supported(self, symbol: str) -> bool:
        s = symbol.upper().strip()
        if s in self.SYMBOL_MAP:
            return True
        return any(s.endswith(suf) for suf in ("-USD", "-USDT", "-USDC"))

    def _request(self, endpoint: str, params: dict = None) -> dict:
        try:
            r = self.session.get(f"{self.BASE_URL}/{endpoint}", params=params or {}, timeout=10)
            if r.status_code == 429:
                raise RateLimitError("Kraken rate limit")
            if r.status_code != 200:
                raise ProviderError(f"Kraken HTTP {r.status_code}")
            data = r.json()
            if data.get("error"):
                err = data["error"]
                if isinstance(err, list) and err:
                    msg = str(err[0])
                    if "Rate limit" in msg:
                        raise RateLimitError(msg)
                    if "Unknown asset" in msg or "Unknown pair" in msg:
                        raise DataNotFoundError(msg)
                    raise ProviderError(msg)
            return data.get("result", {})
        except requests.RequestException as e:
            raise ProviderError(f"Kraken network error: {e}") from e

    def get_quote(self, symbol: str) -> Quote:
        if not self._is_supported(symbol):
            raise DataNotFoundError(f"Kraken: {symbol} not supported")
        pair = self._kraken_pair(symbol)
        data = self._request("Ticker", {"pair": pair})
        if not data:
            raise DataNotFoundError(f"Kraken no ticker for {pair}")
        # Kraken returns keyed by pair name (may differ from request)
        key = next(iter(data.keys()), None)
        if not key:
            raise DataNotFoundError(f"Kraken empty result for {pair}")
        t = data[key]
        price = float(t.get("c", [0])[0])
        if not price:
            raise DataNotFoundError(f"Kraken no price for {pair}")
        open_p = float(t.get("o", 0) or 0)
        high_p = float(t.get("h", [0])[1] if len(t.get("h", [])) > 1 else 0)
        low_p = float(t.get("l", [0])[1] if len(t.get("l", [])) > 1 else 0)
        vol = float(t.get("v", [0])[1] if len(t.get("v", [])) > 1 else 0)
        change = price - open_p
        pct = (change / open_p * 100) if open_p else 0.0
        return Quote(
            symbol=symbol.upper(), price=price, change=change, change_pct=pct,
            high=high_p, low=low_p, open=open_p, prev_close=open_p,
            volume=vol, provider=self.name,
        )

    def get_candles(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        if not self._is_supported(symbol):
            raise DataNotFoundError(f"Kraken: {symbol} not supported")
        pair = self._kraken_pair(symbol)
        kmin = self.INTERVAL_MIN.get(interval)
        if not kmin:
            raise ProviderError(f"Kraken: interval {interval} not supported")
        data = self._request("OHLC", {"pair": pair, "interval": kmin})
        # Kraken returns {pair: [[time, open, high, low, close, vwap, volume, count], ...], last: ...}
        key = next((k for k in data.keys() if k != "last"), None)
        if not key or not data.get(key):
            raise DataNotFoundError(f"Kraken no OHLC for {pair}")
        rows = []
        for k in data[key]:
            rows.append({
                "dt": pd.to_datetime(int(k[0]), unit="s"),
                "Open": float(k[1]), "High": float(k[2]),
                "Low": float(k[3]), "Close": float(k[4]),
                "Volume": float(k[6]),
            })
        return pd.DataFrame(rows).set_index("dt").sort_index()

    def get_company_profile(self, symbol: str) -> dict:
        return {"name": symbol, "exchange": "Kraken", "currency": "USD"}
