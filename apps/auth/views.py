"""Firebase auth views + master bypass + user data endpoints."""
import json
import logging
import secrets
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .firebase import verify_id_token
from .models import UserProfile, WatchlistItem, SignalLog, PaperTrade, PriceAlert

logger = logging.getLogger(__name__)


def _firebase_config(request):
    return {
        "apiKey": settings.FIREBASE_CONFIG.get("API_KEY", ""),
        "authDomain": settings.FIREBASE_CONFIG.get("AUTH_DOMAIN", ""),
        "projectId": settings.FIREBASE_CONFIG.get("PROJECT_ID", ""),
        "appId": settings.FIREBASE_CONFIG.get("APP_ID", ""),
        "configured": bool(settings.FIREBASE_CONFIG.get("API_KEY")),
    }


def _is_master(email: str) -> bool:
    return email and email.lower().strip() == settings.MASTER_EMAIL


def _create_session(request, uid, email, name="", picture="", provider=""):
    """Create session + persist/update UserProfile."""
    is_master = _is_master(email)
    existing = UserProfile.objects.filter(uid=uid).first()
    new_count = (existing.login_count + 1) if existing else 1
    profile, _ = UserProfile.objects.update_or_create(
        uid=uid,
        defaults={
            "email": email, "name": name, "picture": picture,
            "provider": provider, "is_master": is_master,
            "login_count": new_count,
        },
    )
    request.session["uid"] = uid
    request.session["email"] = email
    request.session["name"] = name
    request.session["picture"] = picture
    request.session["provider"] = provider
    request.session["is_master"] = is_master
    # 48 hours (configurable via SESSION_HOURS env var)
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    return profile


# ---------------------------------------------------------------------------
# PAGES
# ---------------------------------------------------------------------------

def login_page(request):
    if request.session.get("uid"):
        return HttpResponseRedirect(reverse("dashboard:index"))
    return render(request, "dashboard/login.html", {
        "firebase_config": _firebase_config(request),
        "next": request.GET.get("next", "/"),
    })


def signup_page(request):
    if request.session.get("uid"):
        return HttpResponseRedirect(reverse("dashboard:index"))
    return render(request, "dashboard/signup.html", {
        "firebase_config": _firebase_config(request),
    })


# ---------------------------------------------------------------------------
# SESSION ENDPOINTS
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def session_login(request):
    """Exchange Firebase ID token for Django session."""
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    id_token = data.get("idToken", "")
    if not id_token:
        return JsonResponse({"ok": False, "error": "Missing idToken"}, status=400)
    try:
        claims = verify_id_token(id_token)
    except ValueError as e:
        logger.warning("Token verification failed: %s", e)
        return JsonResponse({"ok": False, "error": str(e)}, status=401)
    _create_session(
        request, uid=claims["uid"], email=claims.get("email", ""),
        name=claims.get("name", ""), picture=claims.get("picture", ""),
        provider=claims.get("provider", ""),
    )
    return JsonResponse({
        "ok": True, "uid": claims["uid"], "email": claims.get("email"),
        "is_master": _is_master(claims.get("email", "")),
    })



@csrf_exempt
@require_POST
def direct_login(request):
    """Simple email login when Firebase is not configured."""
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    email = (data.get("email") or "").lower().strip()
    password = data.get("password", "")
    if not email:
        return JsonResponse({"ok": False, "error": "Email required"}, status=400)
    # Check if user exists
    profile = UserProfile.objects.filter(email=email).first()
    if profile:
        # Existing user — just log them in
        _create_session(request, uid=profile.uid, email=email,
                        name=profile.name, picture=profile.picture,
                        provider="direct")
        return JsonResponse({"ok": True, "uid": profile.uid, "email": email})
    # New user — create account
    if not password:
        return JsonResponse({"ok": False, "error": "Password required for new accounts"}, status=400)
    uid = f"direct:{email}"
    _create_session(request, uid=uid, email=email, name=email.split("@")[0],
                    provider="direct")
    return JsonResponse({"ok": True, "uid": uid, "email": email, "created": True})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    request.session.flush()
    if request.method == "POST":
        return JsonResponse({"ok": True})
    return HttpResponseRedirect(reverse("firebase_auth:login"))


@require_GET
def whoami(request):
    uid = request.session.get("uid")
    if not uid:
        return JsonResponse({"authenticated": False})
    return JsonResponse({
        "authenticated": True,
        "uid": uid,
        "email": request.session.get("email"),
        "name": request.session.get("name"),
        "picture": request.session.get("picture"),
        "provider": request.session.get("provider"),
        "is_master": request.session.get("is_master", False),
        "session_expires_in_sec": request.session.get_expiry_age(),
    })


# ---------------------------------------------------------------------------
# USER DATA: WATCHLIST
# ---------------------------------------------------------------------------

def _require_user(request):
    uid = request.session.get("uid")
    if not uid:
        return None
    try:
        return UserProfile.objects.get(uid=uid)
    except UserProfile.DoesNotExist:
        return None


@require_GET
def watchlist_list(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    items = [{"symbol": w.symbol, "label": w.label, "added_at": w.added_at.isoformat()}
             for w in user.watchlist.all()[:100]]
    return JsonResponse({"ok": True, "items": items})


@csrf_exempt
@require_POST
def watchlist_add(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    symbol = (data.get("symbol") or "").strip().upper()
    label = (data.get("label") or "").strip()
    if not symbol:
        return JsonResponse({"ok": False, "error": "Missing symbol"}, status=400)
    item, created = WatchlistItem.objects.get_or_create(
        user=user, symbol=symbol, defaults={"label": label}
    )
    if not created and label and item.label != label:
        item.label = label; item.save()
    return JsonResponse({"ok": True, "created": created, "symbol": symbol})


@csrf_exempt
@require_POST
def watchlist_remove(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    symbol = (data.get("symbol") or "").strip().upper()
    deleted, _ = WatchlistItem.objects.filter(user=user, symbol=symbol).delete()
    return JsonResponse({"ok": True, "deleted": deleted})


# ---------------------------------------------------------------------------
# USER DATA: SIGNAL HISTORY
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# PAPER TRADING / PORTFOLIO
# ---------------------------------------------------------------------------

@require_GET
def trades_list(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    status = request.GET.get("status", "").upper()
    qs = user.trades.all()
    if status in ("OPEN", "CLOSED"):
        qs = qs.filter(status=status)
    # Live mark-to-market for open trades
    from apps.market.services import get_market_service
    svc = get_market_service()
    items = []
    total_pnl = 0.0
    for t in qs[:200]:
        current = t.exit_price
        if t.status == "OPEN":
            try:
                current = svc.get_quote(t.symbol).price
            except Exception:
                current = t.entry
        pnl_abs = t.pnl_abs(current or t.entry)
        pnl_pct = t.pnl_pct(current or t.entry)
        total_pnl += pnl_abs
        items.append({
            "id": t.id, "symbol": t.symbol, "direction": t.direction,
            "entry": t.entry, "stop_loss": t.stop_loss, "take_profit": t.take_profit,
            "quantity": t.quantity, "exit_price": t.exit_price,
            "status": t.status, "opened_at": t.opened_at.isoformat(),
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "current_price": round(current or t.entry, 4),
            "pnl_abs": round(pnl_abs, 2), "pnl_pct": round(pnl_pct, 2),
            "notes": t.notes,
        })
    open_count = sum(1 for i in items if i["status"] == "OPEN")
    closed_count = sum(1 for i in items if i["status"] == "CLOSED")
    return JsonResponse({
        "ok": True, "items": items,
        "summary": {"total_pnl": round(total_pnl, 2), "open": open_count, "closed": closed_count},
    })


@csrf_exempt
@require_POST
def trade_open(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    try:
        t = PaperTrade.objects.create(
            user=user,
            symbol=(data.get("symbol") or "").strip().upper(),
            direction=(data.get("direction") or "LONG").upper(),
            entry=float(data["entry"]),
            stop_loss=float(data["stop_loss"]) if data.get("stop_loss") else None,
            take_profit=float(data["take_profit"]) if data.get("take_profit") else None,
            quantity=float(data.get("quantity") or 1.0),
            notes=(data.get("notes") or "")[:255],
        )
        return JsonResponse({"ok": True, "id": t.id, "symbol": t.symbol})
    except (KeyError, ValueError, TypeError) as e:
        return JsonResponse({"ok": False, "error": f"Invalid input: {e}"}, status=400)


@csrf_exempt
@require_POST
def trade_close(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    trade_id = data.get("id")
    exit_price = data.get("exit_price")
    try:
        t = PaperTrade.objects.get(id=trade_id, user=user)
    except PaperTrade.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Trade not found"}, status=404)
    if exit_price is None:
        # Fetch current price
        try:
            from apps.market.services import get_market_service
            exit_price = get_market_service().get_quote(t.symbol).price
        except Exception:
            return JsonResponse({"ok": False, "error": "Could not fetch exit price"}, status=502)
    t.exit_price = float(exit_price)
    t.status = "CLOSED"
    t.closed_at = timezone.now()
    t.save()
    return JsonResponse({"ok": True, "id": t.id, "exit_price": t.exit_price,
                          "pnl_abs": round(t.pnl_abs(t.exit_price), 2),
                          "pnl_pct": round(t.pnl_pct(t.exit_price), 2)})


# ---------------------------------------------------------------------------
# PRICE ALERTS
# ---------------------------------------------------------------------------

@require_GET
def alerts_list(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    items = [{
        "id": a.id, "symbol": a.symbol, "trigger_price": a.trigger_price,
        "direction": a.direction, "message": a.message,
        "created_at": a.created_at.isoformat(),
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "active": a.active,
    } for a in user.alerts.all()[:100]]
    return JsonResponse({"ok": True, "items": items})


@csrf_exempt
@require_POST
def alert_create(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    try:
        a = PriceAlert.objects.create(
            user=user,
            symbol=(data.get("symbol") or "").strip().upper(),
            trigger_price=float(data["trigger_price"]),
            direction=(data.get("direction") or "ABOVE").upper(),
            message=(data.get("message") or "")[:255],
        )
        return JsonResponse({"ok": True, "id": a.id})
    except (KeyError, ValueError) as e:
        return JsonResponse({"ok": False, "error": f"Invalid: {e}"}, status=400)


@csrf_exempt
@require_POST
def alert_delete(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    PriceAlert.objects.filter(id=data.get("id"), user=user).delete()
    return JsonResponse({"ok": True})


@require_GET
def alerts_check(request):
    """Check all active alerts against current prices. Returns triggered alerts."""
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    from apps.market.services import get_market_service
    svc = get_market_service()
    # Unique symbols
    active = user.alerts.filter(active=True, triggered_at__isnull=True)
    symbol_prices = {}
    triggered = []
    for a in active:
        if a.symbol not in symbol_prices:
            try:
                symbol_prices[a.symbol] = svc.get_quote(a.symbol).price
            except Exception:
                symbol_prices[a.symbol] = None
        price = symbol_prices[a.symbol]
        if price is None:
            continue
        fired = ((a.direction == "ABOVE" and price >= a.trigger_price) or
                  (a.direction == "BELOW" and price <= a.trigger_price))
        if fired:
            a.triggered_at = timezone.now()
            a.active = False
            a.save()
            triggered.append({
                "id": a.id, "symbol": a.symbol, "direction": a.direction,
                "trigger_price": a.trigger_price, "current_price": price,
                "message": a.message,
            })
    return JsonResponse({"ok": True, "triggered": triggered, "checked": len(active)})


@require_GET
def signal_history(request):
    user = _require_user(request)
    if not user:
        return JsonResponse({"ok": False, "error": "Not authenticated"}, status=401)
    limit = int(request.GET.get("limit", 50))
    symbol_filter = request.GET.get("symbol", "").strip().upper()
    qs = user.signals.all()
    if symbol_filter:
        qs = qs.filter(symbol=symbol_filter)
    items = [{
        "symbol": s.symbol, "interval": s.interval,
        "direction": s.direction, "action": s.action,
        "entry": s.entry, "stop_loss": s.stop_loss, "take_profit": s.take_profit,
        "confidence": s.confidence, "risk_reward": s.risk_reward,
        "regime": s.regime, "htf_trend": s.htf_trend,
        "created_at": s.created_at.isoformat(),
    } for s in qs[:limit]]
    return JsonResponse({"ok": True, "items": items, "count": qs.count()})
