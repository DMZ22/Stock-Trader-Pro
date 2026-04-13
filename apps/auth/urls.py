from django.urls import path
from . import views

app_name = "firebase_auth"

urlpatterns = [
    path("login/", views.login_page, name="login"),
    path("signup/", views.signup_page, name="signup"),
    path("session/", views.session_login, name="session"),
    path("logout/", views.logout_view, name="logout"),
    path("whoami/", views.whoami, name="whoami"),
    # User data endpoints
    path("watchlist/", views.watchlist_list, name="watchlist_list"),
    path("watchlist/add/", views.watchlist_add, name="watchlist_add"),
    path("watchlist/remove/", views.watchlist_remove, name="watchlist_remove"),
    path("signals/", views.signal_history, name="signal_history"),
    # Paper trading
    path("trades/", views.trades_list, name="trades_list"),
    path("trades/open/", views.trade_open, name="trade_open"),
    path("trades/close/", views.trade_close, name="trade_close"),
    # Price alerts
    path("alerts/", views.alerts_list, name="alerts_list"),
    path("alerts/create/", views.alert_create, name="alert_create"),
    path("alerts/delete/", views.alert_delete, name="alert_delete"),
    path("alerts/check/", views.alerts_check, name="alerts_check"),
]
