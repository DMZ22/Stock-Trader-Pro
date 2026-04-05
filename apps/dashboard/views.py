"""Dashboard views — HTML pages."""
from django.shortcuts import render
from apps.market.assets import ASSET_CATEGORIES


def index(request):
    return render(request, "dashboard/index.html", {
        "categories": ASSET_CATEGORIES,
    })


def analyze(request):
    symbol = request.GET.get("symbol", "AAPL").upper()
    interval = request.GET.get("interval", "5m")
    period = request.GET.get("period", "5d")
    return render(request, "dashboard/analyze.html", {
        "symbol": symbol, "interval": interval, "period": period,
        "categories": ASSET_CATEGORIES,
    })


def scalp_view(request):
    """Dedicated scalping dashboard."""
    return render(request, "dashboard/scalp.html", {
        "categories": ASSET_CATEGORIES,
    })


def scanner_view(request):
    """AI-ranked market scanner across multiple asset universes."""
    return render(request, "dashboard/scanner.html", {
        "categories": ASSET_CATEGORIES,
    })


def portfolio_view(request):
    """Paper trading portfolio + price alerts management."""
    return render(request, "dashboard/portfolio.html", {
        "categories": ASSET_CATEGORIES,
    })
