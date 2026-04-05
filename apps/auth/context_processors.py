from django.conf import settings


def firebase(request):
    cfg = settings.FIREBASE_CONFIG
    return {
        "firebase_configured": bool(cfg.get("API_KEY")),
        "firebase_config_json": {
            "apiKey": cfg.get("API_KEY", ""),
            "authDomain": cfg.get("AUTH_DOMAIN", ""),
            "projectId": cfg.get("PROJECT_ID", ""),
            "appId": cfg.get("APP_ID", ""),
        },
        "firebase_user": getattr(request, "firebase_user", {"authenticated": False}),
    }
