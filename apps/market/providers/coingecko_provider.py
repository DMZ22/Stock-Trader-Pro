"""CoinGecko provider - free, no API key, reliable for crypto."""
import logging
import requests
import pandas as pd
from .base import MarketDataProvider, Quote, DataNotFoundError, ProviderError

logger = logging.getLogger(__name__)


class CoinGeckoProvider(MarketDataProvider):
    """Crypto-only provider. Auto-maps Yahoo-style tickers (BTC-USD -> bitcoin)."""

    name = "coingecko"
    requires_key = False
    BASE_URL = "https://api.coingecko.com/api/v3"

    # Yahoo ticker → CoinGecko id
    SYMBOL_MAP = {
        "BTC-USD": "bitcoin", "ETH-USD": "ethereum", "BNB-USD": "binancecoin",
        "SOL-USD": "solana", "XRP-USD": "ripple", "ADA-USD": "cardano",
        "DOGE-USD": "dogecoin", "AVAX-USD": "avalanche-2", "TRX-USD": "tron",
        "DOT-USD": "polkadot", "MATIC-USD": "matic-network", "LINK-USD": "chainlink",
        "LTC-USD": "litecoin", "SHIB-USD": "shiba-inu", "UNI-USD": "uniswap",
        "ATOM-USD": "cosmos", "NEAR-USD": "near", "APT-USD": "aptos",
        "ARB-USD": "arbitrum", "OP-USD": "optimism", "SUI-USD": "sui",
        "INJ-USD": "injective-protocol", "SEI-USD": "sei-network",
        "RNDR-USD": "render-token", "TIA-USD": "celestia", "KAS-USD": "kaspa",
        "MKR-USD": "maker", "AAVE-USD": "aave", "LDO-USD": "lido-dao",
        "COMP-USD": "compound-governance-token", "CRV-USD": "curve-dao-token",
        "SNX-USD": "havven", "STX-USD": "blockstack", "ALGO-USD": "algorand",
        "XTZ-USD": "tezos", "HBAR-USD": "hedera-hashgraph",
        "PEPE-USD": "pepe", "BONK-USD": "bonk", "FLOKI-USD": "floki",
        "WIF-USD": "dogwifcoin", "BOME-USD": "book-of-meme", "MOG-USD": "mog-coin",
        "BCH-USD": "bitcoin-cash", "ETC-USD": "ethereum-classic",
        "XMR-USD": "monero", "ZEC-USD": "zcash", "DASH-USD": "dash",
        "VET-USD": "vechain", "FIL-USD": "filecoin",
        "ICP-USD": "internet-computer", "GRT-USD": "the-graph",
        "FTM-USD": "fantom", "FLOW-USD": "flow",
        "AXS-USD": "axie-infinity", "SAND-USD": "the-sandbox",
        "MANA-USD": "decentraland", "APE-USD": "apecoin", "CHZ-USD": "chiliz",
    }

    DAYS_MAP = {
        "1d": 1, "5d": 7, "1mo": 30, "3mo": 90,
        "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": "max",
    }

    # CoinGecko OHLC auto-resolution:
    # days=1 → 30min candles; days=7-14 → 4h candles; days>=30 → 4d candles
    # For intraday intervals we cap days to get finer resolution
    INTERVAL_MAX_DAYS = {
        "1m": 1, "5m": 1, "15m": 1, "30m": 1,
        "1h": 14, "60m": 14, "4h": 14,
        "1d": 90, "1wk": 365, "1mo": 365,
    }

    def __init__(self, api_key=None):
        super().__init__(api_key)
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"
        self.session.headers["User-Agent"] = "Stock-Trader-Pro/1.0"

    def is_available(self) -> bool:
        return True

    def _cg_id(self, symbol: str) -> str:
        s = symbol.upper().strip()
        # Normalize USDT/USDC suffixes to USD lookup
        for suffix in ("-USDT", "-USDC", "-BUSD", "/USDT", "/USD"):
            if s.endswith(suffix):
                s = s.replace(suffix, "-USD")
                break
        if s in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[s]
        if s.endswith("-USD"):
            base = s.replace("-USD", "").lower()
            return base
        return s.lower()

    def _is_crypto_symbol(self, symbol: str) -> bool:
        s = symbol.upper().strip()
        if any(s.endswith(suf) for suf in ("-USD", "-USDT", "-USDC", "-BUSD", "/USDT", "/USD")):
            return True
        return s in self.SYMBOL_MAP

    def _request(self, endpoint: str, params: dict = None) -> dict:
        try:
            r = self.session.get(f"{self.BASE_URL}/{endpoint}", params=params or {}, timeout=12)
            if r.status_code == 429:
                raise ProviderError("CoinGecko rate limit")
            if r.status_code != 200:
                raise ProviderError(f"CoinGecko HTTP {r.status_code}")
            return r.json()
        except requests.RequestException as e:
            raise ProviderError(f"CoinGecko network error: {e}") from e

    def get_quote(self, symbol: str) -> Quote:
        if not self._is_crypto_symbol(symbol):
            raise DataNotFoundError(f"CoinGecko: {symbol} is not a crypto pair")
        cg_id = self._cg_id(symbol)
        data = self._request("simple/price", {
            "ids": cg_id, "vs_currencies": "usd",
            "include_24hr_change": "true", "include_24hr_vol": "true",
            "include_last_updated_at": "true",
        })
        if cg_id not in data:
            raise DataNotFoundError(f"CoinGecko no quote for {symbol}")
        q = data[cg_id]
        price = float(q.get("usd") or 0)
        change_pct = float(q.get("usd_24h_change") or 0)
        prev = price / (1 + change_pct / 100) if change_pct else price
        change = price - prev
        return Quote(
            symbol=symbol.upper(), price=price, change=change, change_pct=change_pct,
            high=0, low=0, open=prev, prev_close=prev,
            volume=float(q.get("usd_24h_vol") or 0),
            timestamp=int(q.get("last_updated_at") or 0),
            provider=self.name,
        )

    def get_candles(self, symbol: str, interval: str, period: str) -> pd.DataFrame:
        if not self._is_crypto_symbol(symbol):
            raise DataNotFoundError(f"CoinGecko: {symbol} is not a crypto pair")
        cg_id = self._cg_id(symbol)
        requested_days = self.DAYS_MAP.get(period, 30)
        # Cap days by interval to get appropriate granularity
        if interval in self.INTERVAL_MAX_DAYS:
            if requested_days == "max":
                requested_days = self.INTERVAL_MAX_DAYS[interval]
            else:
                requested_days = min(requested_days, self.INTERVAL_MAX_DAYS[interval])
        data = self._request(f"coins/{cg_id}/ohlc", {"vs_currency": "usd", "days": requested_days})
        if not data or not isinstance(data, list) or len(data) == 0:
            raise DataNotFoundError(f"CoinGecko no OHLC for {symbol}")
        df = pd.DataFrame(data, columns=["timestamp", "Open", "High", "Low", "Close"])
        df["Volume"] = 0.0
        df.index = pd.to_datetime(df["timestamp"], unit="ms")
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        # Try to join volume from market_chart endpoint
        try:
            mc = self._request(f"coins/{cg_id}/market_chart",
                               {"vs_currency": "usd", "days": requested_days})
            vols = mc.get("total_volumes", [])
            if vols:
                vol_df = pd.DataFrame(vols, columns=["timestamp", "Volume"])
                vol_df.index = pd.to_datetime(vol_df["timestamp"], unit="ms")
                # Reindex to OHLC timestamps
                df["Volume"] = vol_df["Volume"].reindex(df.index, method="nearest").fillna(0)
        except Exception:
            pass
        return df.sort_index()

    def get_company_profile(self, symbol: str) -> dict:
        try:
            cg_id = self._cg_id(symbol)
            data = self._request(f"coins/{cg_id}",
                                 {"localization": "false", "tickers": "false",
                                  "community_data": "false", "developer_data": "false"})
            md = data.get("market_data", {}) or {}
            return {
                "name": data.get("name", symbol),
                "symbol": data.get("symbol", "").upper(),
                "sector": "Cryptocurrency",
                "industry": (data.get("categories") or ["Crypto"])[0] if data.get("categories") else "Crypto",
                "market_cap": (md.get("market_cap") or {}).get("usd"),
                "52w_high": (md.get("ath") or {}).get("usd"),
                "52w_low": (md.get("atl") or {}).get("usd"),
                "currency": "USD",
                "exchange": "CoinGecko",
            }
        except Exception as e:
            logger.warning("CoinGecko profile failed: %s", e)
            return {"name": symbol}
