"""Firebase auth views: login page, session creation, logout."""
import json
import logging
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from .firebase import verify_id_token

logger = logging.getLogger(__name__)


def _firebase_config(request):
    return {
        "apiKey": settings.FIREBASE_CONFIG.get("API_KEY", ""),
        "authDomain": settings.FIREBASE_CONFIG.get("AUTH_DOMAIN", ""),
        "projectId": settings.FIREBASE_CONFIG.get("PROJECT_ID", ""),
        "appId": settings.FIREBASE_CONFIG.get("APP_ID", ""),
        "configured": bool(settings.FIREBASE_CONFIG.get("API_KEY")),
    }


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
    # Store in session
    request.session["uid"] = claims["uid"]
    request.session["email"] = claims.get("email", "")
    request.session["name"] = claims.get("name", "")
    request.session["picture"] = claims.get("picture", "")
    request.session["provider"] = claims.get("provider", "")
    request.session.set_expiry(60 * 60 * 24 * 7)  # 7 days
    return JsonResponse({"ok": True, "uid": claims["uid"], "email": claims.get("email", "")})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    request.session.flush()
    if request.method == "POST":
        return JsonResponse({"ok": True})
    return HttpResponseRedirect(reverse("firebase_auth:login"))


def whoami(request):
    if not request.session.get("uid"):
        return JsonResponse({"authenticated": False})
    return JsonResponse({
        "authenticated": True,
        "uid": request.session["uid"],
        "email": request.session.get("email"),
        "name": request.session.get("name"),
        "picture": request.session.get("picture"),
        "provider": request.session.get("provider"),
    })
