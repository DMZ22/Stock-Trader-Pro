# Stock Trader Pro v1.1

Production Django trading dashboard with scalp trade signals, multi-timeframe confluence, price action patterns, market regime detection, 20+ technical indicators, LSTM forecasting, news sentiment, backtesting, and Firebase authentication.

## View Project

| | Link |
|---|---|
| **Live Demo** | [https://graves-clarify-freeness.ngrok-free.dev](https://graves-clarify-freeness.ngrok-free.dev) |
| **GitHub** | [https://github.com/DMZ22/Stock-Trader-Pro](https://github.com/DMZ22/Stock-Trader-Pro) |

## What's New in v1.1

- **50+ assets added** — Now supports 230+ symbols across 12 categories: US stocks, Indian NSE (35 tickers), 60+ cryptocurrencies, Gold/Silver/Platinum futures + ETFs + miners, energy & agricultural commodities, forex, global ETFs & indices.
- **CoinGecko provider** (no API key) — Reliable crypto data for all major and alt coins.
- **Multi-timeframe confluence** — Scalp signals check higher-timeframe trend (5m → 1h, 1h → 1d) for alignment; +12 score boost when aligned, -15 when counter-trend.
- **Price action patterns** — Detects Hammer, Shooting Star, Doji, Bullish/Bearish Engulfing, Inside Bar, Morning/Evening Star, Three White Soldiers / Black Crows.
- **Market regime classification** — STRONG_TREND / WEAK_TREND / RANGING / TIGHT_RANGE / VOLATILE_CHOP with strategy adaptation.
- **Support/resistance auto-detection** — Fractal swing highs/lows. SL/TP snap to nearby levels when within 0.5 × ATR.
- **Backtest endpoint** — Replay signals on historical bars, report hit rate vs 2:1 R/R breakeven.
- **31 indicator values** exposed per signal with tooltips explaining each.
- **Firebase Authentication** — Email/password + Google OAuth sign-in with Django session integration.
- **Production hardening** — HSTS, secure cookies, CSRF trusted origins, detailed health endpoint.

## Quick Start

```bash
git clone <repo-url>
cd Stock-Trader-Pro
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
# visit http://localhost:8000
```

## Environment Variables (all optional)

```ini
# Market Data API keys (yfinance + CoinGecko work without keys)
FINNHUB_API_KEY=          # https://finnhub.io  (60/min)
TWELVE_DATA_API_KEY=      # https://twelvedata.com  (8/min)
ALPHA_VANTAGE_API_KEY=    # https://www.alphavantage.co  (5/min)

# News APIs
NEWSAPI_KEY=              # https://newsapi.org  (100/day)
MARKETAUX_API_KEY=        # https://marketaux.com

# Firebase Auth (optional)
FIREBASE_API_KEY=
FIREBASE_AUTH_DOMAIN=yourproject.firebaseapp.com
FIREBASE_PROJECT_ID=yourproject
FIREBASE_APP_ID=1:123:web:abc
REQUIRE_LOGIN=False       # set True to force login for all pages
```

## Asset Categories

| Category | Count | Examples |
|---|---|---|
| US Tech | 27 | AAPL, MSFT, NVDA, GOOGL, AMZN, TSM, ASML |
| US Finance | 14 | JPM, V, GS, BLK |
| US Consumer/Industrial | 21 | DIS, WMT, KO, LLY, JNJ |
| Indian NSE | 35 | RELIANCE.NS, TCS.NS, HDFCBANK.NS, SBIN.NS |
| Major Crypto | 16 | BTC, ETH, SOL, BNB, XRP, DOGE |
| Crypto DeFi & L1 | 20 | NEAR, APT, ARB, OP, MKR, AAVE, LDO |
| Crypto Meme & Alt | 22 | PEPE, BONK, WIF, BCH, XMR |
| Precious Metals & Miners | 16 | Gold/Silver/Platinum/Palladium futures, GLD, GDX, NEM |
| Energy & Agri Commodities | 18 | WTI, Brent, Nat Gas, Copper, Wheat, Coffee |
| ETFs & Indices | 24 | SPY, QQQ, VIX, Nifty, Sensex, Nikkei, DAX |
| Forex | 18 | EUR/USD, GBP/USD, USD/INR, USD/JPY |

## REST API

| Endpoint | Description |
|---|---|
| `GET /api/health/` | Provider status + cache + Firebase config |
| `GET /api/quote/{symbol}/` | Real-time quote |
| `GET /api/candles/{symbol}/?interval=5m&period=5d` | OHLCV candles |
| `GET /api/scalp/{symbol}/?interval=5m&period=5d&account=10000&risk=1&htf=1` | Full scalp signal with HTF confluence |
| `GET /api/analyze/{symbol}/` | Combined analysis (scalp + sentiment + composite) |
| `GET /api/backtest/{symbol}/?bars=300` | Historical hit rate |
| `GET /api/search/?q=BTC` | Asset search |
| `GET /api/assets/` | Full asset universe |
| `POST /auth/session/` | Exchange Firebase ID token for Django session |
| `GET /auth/whoami/` | Current session user |

## Signal Accuracy Stack

1. **Core scoring** (0-100 per direction): EMA-9/21 cross, VWAP position, Supertrend, MACD histogram + acceleration, RSI zones, volume ratio, ADX strength + DI directionality, Stochastic reversal, Bollinger %B.
2. **Pattern adjustment**: +8 per aligned candlestick pattern, -10 per counter-trend pattern.
3. **Regime adjustment**: +5 in STRONG_TREND, -10 in VOLATILE_CHOP.
4. **HTF confluence**: +12 when higher timeframe aligns, -15 when counter to HTF trend.
5. **Level snapping**: SL/TP adjusted to support/resistance when within 0.5 × ATR.
6. **Position sizing**: Dollar risk = account × risk_pct; shares = dollar_risk ÷ (entry - stop).

Breakeven hit rate at 2:1 R/R = 33.3%. Any hit rate above that is profitable.

## Deployment

### Docker
```bash
docker-compose up --build
```

### Production checklist
- Set `DJANGO_DEBUG=False` and a strong `DJANGO_SECRET_KEY`
- Add your domain to `DJANGO_ALLOWED_HOSTS`
- Configure API keys in `.env`
- Set up Firebase project + enable Email/Password and Google providers
- Use Redis via `REDIS_URL` for shared cache across workers
- Behind nginx/Cloudflare, HTTPS auto-detected via `X-Forwarded-Proto`

## Architecture

```
config/                 Django settings + routing
apps/
  market/               Multi-provider data + 20+ indicators
    providers/          yfinance, finnhub, alpha_vantage, twelve_data, coingecko
    services.py         Unified facade: retry/failover/caching/rate-limit
    indicators.py       Canonical formulas (RSI, MACD, BB, ADX, Stoch, etc.)
    assets.py           230+ curated symbols
  predictor/            Bidirectional LSTM (24 features, multi-step)
  signals/              Scalp engine + patterns + regime + sentiment + composite
    scalper.py          Confluence scoring + ATR SL/TP + position sizing
    patterns.py         Candlestick patterns + regime + S/R levels
    sentiment.py        4 news providers with TextBlob
    composite.py        Combined scalp + LSTM + sentiment
  auth/                 Firebase ID token verification + session auth
  dashboard/            Views, REST API, templates
```

## Disclaimer

**For educational purposes only.** Trading involves substantial risk of loss. Past performance does not guarantee future results. This software provides technical analysis based on historical data and indicator confluence; it does not account for fundamentals, breaking news, or black-swan events. Always do your own research and consult a licensed financial advisor before trading.

## License

MIT
