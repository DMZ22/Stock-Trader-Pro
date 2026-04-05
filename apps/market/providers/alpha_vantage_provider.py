"""Alpha Vantage provider (5 req/min free tier). Good for global coverage & FX."""
import logging
import requests
import pandas as pd
from .base import MarketDataProvider, Quote, DataNotFoundError, ProviderError, RateLimitError

logger = logging.getLogger(__name__)


class AlphaVantageProvider(MarketDataProvider):
    name = "alpha_vantage"
    requires_key = True
    BASE_URL = "https://www.alphavantage.co/query"

    INTERVAL_MAP = {
        "1m": ("TIME_SERIES_INTRADAY", "1min"),
        "5m": ("TIME_SERIES_INTRADAY", "5min"),
        "15m": ("TIME_SERIES_INTRADAY", "15min"),
        "30m": ("TIME_SERIES_INTRADAY", "30min"),
        "1h": ("TIME_SERIES_INTRADAY", "60min"),
        "60m": ("TIME_SERIES_INTRADAY", "60min"),
        "1d": ("TIME_SERIES_DAILY_ADJUSTED", None),
        "1wk": ("TIME_SERIES_WEEKLY_ADJUSTED", None),
        "1mo": ("TIME_SERIES_MONTHLY_ADJUSTED", None),
    }

    def __init__(self, api_key=None):
        super().__init__(api_key)
        self.session = requests.Session()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _request(self, params: dict) -> dict:
        params["apikey"] = self.api_key
        try:
            r = self.session.get(self.BASE_URL, params=params, timeout=15)
            if r.status_code != 200:
                raise ProviderError(f"Alpha Vantage HTTP {r.status_code}")
            data = r.json()
            if "Note" in data or "Information" in data:
                raise RateLimitError(data.get("Note") or data.get("Information"))
            if "Error Message" in data:
                raise DataNotFoundError(data["Error Message"])
            return data
        except requests.RequestException as e:
            raise ProviderError(f"Alpha Vantage network error: {e}") from e

    def get_quote(self, symbol: str) -> Quote:
        data = self._request({"function": "GLOBAL_QUOTE", "symbol": symbol})
        q = data.get("Global Quote", {})
        if not q or not q.get("05. price"):
            raise DataNotFoundError(f"No AV quote for {symbol}")
        price = float(q["05. price"])
        prev = float(q.get("08. previous close") or 0)
        change = float(q.get("09. change") or 0)
        pct_str = (q.get("10. change percent") or "0%").rstrip("%")
        return Quote(
            symbol=symbol, price=price, change=change,
            change_pct=float(pct_str or 0),
            high=float(q.get("03. high") or 0),
            low=float(q.get("04. low") or 0),
            open=float(q.get("02. open") or 0),
            prev_close=prev,
            volume=float(q.get("06. volume") or 0),
            provider=self.name,
        )

    def get_candles(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        fn_tuple = self.INTERVAL_MAP.get(interval)
        if not fn_tuple:
            raise ProviderError(f"AV unsupported interval: {interval}")
        function, av_interval = fn_tuple
        params = {"function": function, "symbol": symbol, "outputsize": "full"}
        if av_interval:
            params["interval"] = av_interval
        data = self._request(params)
        # Find time series key
        ts_key = next((k for k in data if "Time Series" in k), None)
        if not ts_key:
            raise DataNotFoundError(f"AV no time series for {symbol}")
        ts = data[ts_key]
        rows = []
        for dt_str, bar in ts.items():
            rows.append({
                "dt": pd.to_datetime(dt_str),
                "Open": float(bar.get("1. open", 0)),
                "High": float(bar.get("2. high", 0)),
                "Low": float(bar.get("3. low", 0)),
                "Close": float(bar.get("4. close", 0)),
                "Volume": float(bar.get("5. volume", bar.get("6. volume", 0))),
            })
        df = pd.DataFrame(rows).set_index("dt").sort_index()
        return df
