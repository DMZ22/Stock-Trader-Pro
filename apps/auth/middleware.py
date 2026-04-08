"""Middleware to inject current user into request and optionally protect routes."""
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse


class FirebaseUserMiddleware:
    """Attaches request.firebase_user from session. Non-blocking."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        uid = request.session.get("uid")
        request.firebase_user = {
            "authenticated": bool(uid),
            "uid": uid,
            "email": request.session.get("email"),
            "name": request.session.get("name"),
            "picture": request.session.get("picture"),
            "is_master": request.session.get("is_master", False),
        } if uid else {"authenticated": False, "is_master": False}
        return self.get_response(request)


class RequireLoginMiddleware:
    """Redirects unauthenticated users to /auth/login/ for protected paths."""

    PUBLIC_PATHS = ("/auth/", "/static/", "/api/", "/admin/")

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "REQUIRE_LOGIN", False)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)
        path = request.path
        if any(path.startswith(p) for p in self.PUBLIC_PATHS):
            return self.get_response(request)
        if not request.session.get("uid"):
            return HttpResponseRedirect(f"{reverse('firebase_auth:login')}?next={path}")
        return self.get_response(request)
