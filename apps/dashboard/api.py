"""REST API endpoints for the dashboard."""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page

from apps.market.services import get_market_service
from apps.market.providers.base import ProviderError, DataNotFoundError
from apps.market.indicators import add_indicators
from apps.market.assets import ASSET_CATEGORIES, find_symbol
from apps.signals.scalper import detect_scalp, backtest_signals


# Map low TF to higher TF for multi-timeframe confluence
HTF_MAP = {
    "1m": ("15m", "5d"),
    "5m": ("1h", "1mo"),
    "15m": ("1h", "1mo"),
    "30m": ("4h", "3mo") if False else ("1h", "1mo"),
    "1h": ("1d", "6mo"),
    "1d": ("1wk", "2y"),
}
from apps.signals.sentiment import fetch_news, analyze_sentiment
from apps.signals.composite import combine

logger = logging.getLogger(__name__)


def _error(message, status=400):
    return JsonResponse({"error": message, "ok": False}, status=status)


@require_GET
def health_api(request):
    """Detailed health check: provider status + cache + version."""
    import time
    svc = get_market_service()
    checks = {}
    # Test each provider with a lightweight call
    for p in svc.providers:
        try:
            t0 = time.time()
            if p.name == "coingecko":
                # CoinGecko doesn't support non-crypto; skip live test
                checks[p.name] = {"status": "available", "requires_key": p.requires_key}
            else:
                # Just check availability, don't make network call
                checks[p.name] = {"status": "configured" if p.is_available() else "unavailable",
                                  "requires_key": p.requires_key}
        except Exception as e:
            checks[p.name] = {"status": "error", "error": str(e)}
    # Cache check
    from django.core.cache import cache
    try:
        cache.set("health_ping", "ok", 10)
        cache_ok = cache.get("health_ping") == "ok"
    except Exception:
        cache_ok = False
    return JsonResponse({
        "ok": True,
        "version": "1.1.0",
        "providers": checks,
        "provider_order": [p.name for p in svc.providers],
        "cache": "ok" if cache_ok else "error",
        "firebase_configured": bool(__import__("django.conf").conf.settings.FIREBASE_CONFIG.get("API_KEY")),
    })


@require_GET
def assets_api(request):
    return JsonResponse({
        "ok": True,
        "categories": {cat: [{"name": n, "symbol": s} for n, s in items]
                       for cat, items in ASSET_CATEGORIES.items()},
    })


@require_GET
def search_api(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"ok": True, "results": []})
    return JsonResponse({"ok": True, "results": find_symbol(q)})


@require_GET
def quote_api(request, symbol):
    try:
        quote = get_market_service().get_quote(symbol)
        return JsonResponse({"ok": True, "quote": quote.__dict__})
    except DataNotFoundError as e:
        return _error(str(e), 404)
    except ProviderError as e:
        return _error(str(e), 502)
    except Exception as e:
        logger.exception("quote_api")
        return _error("Internal error", 500)


@require_GET
def candles_api(request, symbol):
    interval = request.GET.get("interval", "1d")
    period = request.GET.get("period", "6mo")
    try:
        df = get_market_service().get_candles(symbol, interval, period)
        data = {
            "ok": True,
            "symbol": symbol.upper(),
            "interval": interval, "period": period,
            "bars": len(df),
            "data": {
                "time": [str(x) for x in df.index.tolist()],
                "open": df["Open"].astype(float).tolist(),
                "high": df["High"].astype(float).tolist(),
                "low": df["Low"].astype(float).tolist(),
                "close": df["Close"].astype(float).tolist(),
                "volume": df["Volume"].astype(float).tolist(),
            },
        }
        return JsonResponse(data)
    except DataNotFoundError as e:
        return _error(str(e), 404)
    except ProviderError as e:
        return _error(str(e), 502)
    except Exception as e:
        logger.exception("candles_api")
        return _error("Internal error", 500)


@require_GET
def scalp_api(request, symbol):
    interval = request.GET.get("interval", "5m")
    period = request.GET.get("period", "5d")
    account = float(request.GET.get("account", 10000))
    risk_pct = float(request.GET.get("risk", 1.0))
    use_htf = request.GET.get("htf", "1") == "1"
    try:
        svc = get_market_service()
        df = svc.get_candles(symbol, interval, period)
        df_ind = add_indicators(df)
        # Fetch higher-timeframe for confluence
        htf_ind = None
        if use_htf and interval in HTF_MAP:
            htf_interval, htf_period = HTF_MAP[interval]
            try:
                htf_df = svc.get_candles(symbol, htf_interval, htf_period)
                htf_ind = add_indicators(htf_df)
            except Exception as e:
                logger.info("HTF fetch failed (non-critical): %s", e)
        sig = detect_scalp(df_ind, symbol.upper(),
                           account_size=account, risk_per_trade_pct=risk_pct,
                           htf_df=htf_ind)
        return JsonResponse({"ok": True, "signal": sig.to_dict()})
    except DataNotFoundError as e:
        return _error(str(e), 404)
    except ProviderError as e:
        return _error(str(e), 502)
    except Exception as e:
        logger.exception("scalp_api")
        return _error(str(e), 500)


@require_GET
def analyze_api(request, symbol):
    """Full analysis: candles + indicators + scalp + sentiment + composite."""
    interval = request.GET.get("interval", "5m")
    period = request.GET.get("period", "5d")
    try:
        svc = get_market_service()
        df = svc.get_candles(symbol, interval, period)
        profile = svc.get_profile(symbol)
        df_ind = add_indicators(df)
        # Multi-timeframe trend filter
        htf_ind = None
        if interval in HTF_MAP:
            htf_interval, htf_period = HTF_MAP[interval]
            try:
                htf_df_raw = svc.get_candles(symbol, htf_interval, htf_period)
                htf_ind = add_indicators(htf_df_raw)
            except Exception:
                pass
        scalp = detect_scalp(df_ind, symbol.upper(), htf_df=htf_ind)
        articles = fetch_news(symbol.upper(), profile.get("name", ""))
        sentiment = analyze_sentiment(articles)
        current_price = float(df["Close"].iloc[-1])
        composite = combine(scalp, lstm_forecast=None, current_price=current_price, sentiment=sentiment)
        latest = df_ind.iloc[-1]
        return JsonResponse({
            "ok": True,
            "symbol": symbol.upper(),
            "profile": profile,
            "current_price": current_price,
            "scalp": scalp.to_dict(),
            "composite": composite,
            "sentiment": {
                "label": sentiment["label"],
                "avg_polarity": sentiment["avg_polarity"],
                "count": sentiment["count"],
                "bullish_pct": sentiment["bullish_pct"],
                "bearish_pct": sentiment["bearish_pct"],
                "neutral_pct": sentiment["neutral_pct"],
                "headlines": sentiment["scored"][:10],
            },
            "indicators_snapshot": {
                "rsi": round(float(latest.get("RSI_14", 0)), 2),
                "macd": round(float(latest.get("MACD", 0)), 4),
                "macd_signal": round(float(latest.get("MACD_Signal", 0)), 4),
                "adx": round(float(latest.get("ADX_14", 0)), 2),
                "atr": round(float(latest.get("ATR_14", 0)), 4),
                "vwap": round(float(latest.get("VWAP", 0)), 4),
                "bb_upper": round(float(latest.get("BB_Upper", 0)), 4),
                "bb_lower": round(float(latest.get("BB_Lower", 0)), 4),
            },
        })
    except DataNotFoundError as e:
        return _error(str(e), 404)
    except ProviderError as e:
        return _error(str(e), 502)
    except Exception as e:
        logger.exception("analyze_api")
        return _error(str(e), 500)


@require_GET
def backtest_api(request, symbol):
    """Backtest scalp signals over recent bars to show historical accuracy."""
    interval = request.GET.get("interval", "5m")
    period = request.GET.get("period", "1mo")
    bars = int(request.GET.get("bars", 200))
    try:
        df = get_market_service().get_candles(symbol, interval, period)
        df_ind = add_indicators(df)
        result = backtest_signals(df_ind, symbol.upper(), lookback_bars=bars)
        return JsonResponse({"ok": True, "symbol": symbol.upper(),
                             "interval": interval, "period": period, **result})
    except DataNotFoundError as e:
        return _error(str(e), 404)
    except ProviderError as e:
        return _error(str(e), 502)
    except Exception as e:
        logger.exception("backtest_api")
        return _error(str(e), 500)
