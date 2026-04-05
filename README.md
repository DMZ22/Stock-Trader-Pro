# Stock Trader Pro

Production-grade Django trading dashboard with scalp trade signals, multi-feature LSTM price prediction, technical analysis, and news sentiment.

## Features

- **Multi-Provider Market Data** — Finnhub, Twelve Data, Alpha Vantage, Yahoo Finance with automatic failover, retry logic, and per-provider rate limiting.
- **Scalp Trade Engine** — Auto-detects LONG/SHORT setups with entry, ATR-based stop-loss, take-profit, risk/reward, and position sizing.
- **20+ Technical Indicators** — RSI, MACD, Bollinger Bands, ADX, Stochastic, Williams %R, CCI, MFI, CMF, Supertrend, VWAP, ATR, EMA/SMA (all canonical formulas).
- **Bidirectional LSTM Predictor** — 24 input features, multi-step forecasting, MAE/MAPE/R²/Directional Accuracy.
- **News Sentiment** — NewsAPI, Marketaux, Finnhub news, Yahoo Finance news with TextBlob polarity scoring.
- **Composite Signal** — Combines scalp + LSTM + sentiment into a unified trade recommendation.
- **REST API** — Full JSON API at `/api/` for all data and signals.
- **150+ Assets** — US stocks, Indian NSE, crypto, forex, commodities, ETFs, global indices.

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/YOUR_USERNAME/Stock-Trader-Pro.git
cd Stock-Trader-Pro
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — add API keys (all optional; yfinance works without keys)

# 3. Run
python manage.py migrate
python manage.py runserver
```

Visit `http://localhost:8000`.

## API Keys (all optional — recommended for production)

| Provider | Free Tier | Get Key |
|---|---|---|
| Finnhub | 60 req/min | https://finnhub.io |
| Twelve Data | 8 req/min | https://twelvedata.com |
| Alpha Vantage | 5 req/min | https://www.alphavantage.co |
| NewsAPI | 100 req/day | https://newsapi.org |
| Marketaux | 100 req/day | https://marketaux.com |

## Docker Deployment

```bash
docker-compose up --build
```

## REST API Reference

| Endpoint | Description |
|---|---|
| `GET /api/health/` | Provider health & availability |
| `GET /api/quote/{symbol}/` | Real-time quote |
| `GET /api/candles/{symbol}/?interval=5m&period=5d` | OHLCV candles |
| `GET /api/scalp/{symbol}/?interval=5m&period=5d&account=10000&risk=1` | Scalp trade signal |
| `GET /api/analyze/{symbol}/` | Full analysis (scalp + sentiment + composite) |
| `GET /api/search/?q=AAPL` | Asset search |
| `GET /api/assets/` | Full asset universe |

## Architecture

```
config/          Django project settings & routing
apps/
  market/        Data providers + indicators + rate limiting
    providers/   yfinance, finnhub, alpha_vantage, twelve_data
    indicators.py  Canonical formulas for 20+ indicators
    services.py  Unified facade with caching/retry/failover
  predictor/     Bidirectional LSTM
  signals/       Scalp engine, composite, sentiment
  dashboard/     Views, REST API, templates
```

## How Signals Are Generated

The scalp engine scores bullish vs bearish signals using 8 confirmations:
1. EMA-9/EMA-21 crossover (short trend)
2. VWAP position (institutional bias)
3. Supertrend direction (trend filter)
4. RSI zones (momentum)
5. MACD histogram direction & acceleration
6. Volume ratio vs 20-period average
7. ADX strength + DI+/DI- directionality
8. Stochastic oversold/overbought reversal

Stop-loss = entry ± 1.5 × ATR(14). Take-profit = entry ± 3.0 × ATR(14). R/R = 2:1.

## Disclaimer

**For educational purposes only.** This software provides market analysis based on historical patterns and technical indicators. It does not guarantee profits and should not be considered financial advice. Always do your own research and consult a licensed financial advisor before making investment decisions.

## License

MIT
