"""News sentiment analysis using multiple news providers."""
import logging
from datetime import datetime, timedelta
import requests
import yfinance as yf
from textblob import TextBlob
from django.conf import settings
from django.core.cache import cache
import numpy as np

logger = logging.getLogger(__name__)


def _fetch_newsapi(query: str, days: int = 7) -> list:
    key = settings.API_KEYS.get("NEWSAPI")
    if not key:
        return []
    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "from": (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d"),
                "language": "en", "sortBy": "publishedAt", "pageSize": 30,
                "apiKey": key,
            },
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning("NewsAPI status %d: %s", r.status_code, r.text[:200])
            return []
        return r.json().get("articles", []) or []
    except Exception as e:
        logger.warning("NewsAPI failure: %s", e)
        return []


def _fetch_marketaux(symbol: str) -> list:
    key = settings.API_KEYS.get("MARKETAUX")
    if not key:
        return []
    try:
        r = requests.get(
            "https://api.marketaux.com/v1/news/all",
            params={"symbols": symbol, "filter_entities": "true",
                    "language": "en", "api_token": key, "limit": 20},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        data = r.json().get("data", [])
        articles = []
        for d in data:
            articles.append({
                "title": d.get("title", ""),
                "description": d.get("description", ""),
                "url": d.get("url", ""),
                "source": {"name": d.get("source", "Marketaux")},
                "publishedAt": d.get("published_at", ""),
            })
        return articles
    except Exception as e:
        logger.warning("Marketaux failure: %s", e)
        return []


def _fetch_finnhub_news(symbol: str) -> list:
    key = settings.API_KEYS.get("FINNHUB")
    if not key:
        return []
    try:
        to_date = datetime.utcnow().strftime("%Y-%m-%d")
        from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": symbol, "from": from_date, "to": to_date, "token": key},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        data = r.json() or []
        articles = []
        for d in data[:30]:
            articles.append({
                "title": d.get("headline", ""),
                "description": d.get("summary", ""),
                "url": d.get("url", ""),
                "source": {"name": d.get("source", "Finnhub")},
                "publishedAt": str(d.get("datetime", "")),
            })
        return articles
    except Exception as e:
        logger.warning("Finnhub news failure: %s", e)
        return []


def _fetch_yahoo_news(symbol: str) -> list:
    try:
        news = yf.Ticker(symbol).news or []
        articles = []
        for item in news[:30]:
            content = item.get("content", item)
            title = content.get("title") or item.get("title", "")
            if not title:
                continue
            articles.append({
                "title": title,
                "description": content.get("summary") or content.get("description") or "",
                "url": (content.get("canonicalUrl", {}) or {}).get("url") or item.get("link", ""),
                "source": {"name": (content.get("provider", {}) or {}).get("displayName")
                           or item.get("publisher", "Yahoo Finance")},
                "publishedAt": str(content.get("pubDate") or item.get("providerPublishTime", "")),
            })
        return articles
    except Exception as e:
        logger.warning("Yahoo news failure: %s", e)
        return []


def fetch_news(symbol: str, company_name: str = "") -> list:
    """Try all news providers; merge de-duplicated results."""
    ckey = f"news:{symbol}"
    cached = cache.get(ckey)
    if cached is not None:
        return cached

    query = company_name or symbol
    articles = []
    # Try providers in order, stop once we have enough
    for fetcher in [
        lambda: _fetch_finnhub_news(symbol),
        lambda: _fetch_marketaux(symbol),
        lambda: _fetch_newsapi(f"{query} OR {symbol}"),
        lambda: _fetch_yahoo_news(symbol),
    ]:
        try:
            batch = fetcher()
            articles.extend(batch)
            if len(articles) >= 20:
                break
        except Exception:
            continue

    # Dedupe by title
    seen = set()
    unique = []
    for a in articles:
        t = a.get("title", "").strip()
        if t and t not in seen:
            seen.add(t); unique.append(a)
    cache.set(ckey, unique, 600)
    return unique


def analyze_sentiment(articles: list) -> dict:
    """Score headlines with TextBlob polarity."""
    if not articles:
        return {
            "avg_polarity": 0.0, "label": "Neutral", "count": 0,
            "bullish_pct": 0.0, "bearish_pct": 0.0, "neutral_pct": 100.0,
            "scored": [],
        }
    scored = []
    pols = []
    for a in articles:
        text = f"{a.get('title','')}. {a.get('description','') or ''}"
        pol = float(TextBlob(text).sentiment.polarity)
        scored.append({
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": (a.get("source") or {}).get("name", "Unknown"),
            "published": a.get("publishedAt", ""),
            "polarity": round(pol, 3),
        })
        pols.append(pol)
    avg = float(np.mean(pols))
    bull = sum(1 for p in pols if p > 0.05) / len(pols) * 100
    bear = sum(1 for p in pols if p < -0.05) / len(pols) * 100
    neu = 100 - bull - bear
    if avg > 0.1:
        label = "Bullish"
    elif avg < -0.1:
        label = "Bearish"
    else:
        label = "Neutral"
    scored.sort(key=lambda x: x["polarity"], reverse=True)
    return {
        "avg_polarity": round(avg, 3), "label": label, "count": len(pols),
        "bullish_pct": round(bull, 1), "bearish_pct": round(bear, 1),
        "neutral_pct": round(neu, 1), "scored": scored,
    }
