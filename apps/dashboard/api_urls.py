from django.urls import path
from . import api

urlpatterns = [
    path("quote/<str:symbol>/", api.quote_api, name="api_quote"),
    path("candles/<str:symbol>/", api.candles_api, name="api_candles"),
    path("scalp/<str:symbol>/", api.scalp_api, name="api_scalp"),
    path("analyze/<str:symbol>/", api.analyze_api, name="api_analyze"),
    path("backtest/<str:symbol>/", api.backtest_api, name="api_backtest"),
    path("search/", api.search_api, name="api_search"),
    path("assets/", api.assets_api, name="api_assets"),
    path("health/", api.health_api, name="api_health"),
]
