"""Django settings for Stock-Trader-Pro."""
from pathlib import Path
import os
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    FINNHUB_RATE_LIMIT=(int, 60),
    ALPHA_VANTAGE_RATE_LIMIT=(int, 5),
    REQUIRE_LOGIN=(bool, True),
    MASTER_EMAIL=(str, "dev22ashish@gmail.com"),
    SESSION_HOURS=(int, 48),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-key-replace-in-production")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# Trust proxy-forwarded HTTPS (for deployment behind nginx/cloudflare/etc)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CSRF - add production hosts via env
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")]
CSRF_TRUSTED_ORIGINS += ["http://localhost:8000", "http://127.0.0.1:8000",
                          "http://localhost:8787", "http://127.0.0.1:8787"]

# Production security headers (auto-enabled when DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.market",
    "apps.predictor",
    "apps.signals",
    "apps.dashboard",
    "apps.auth.apps.AuthConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.auth.middleware.FirebaseUserMiddleware",
    "apps.auth.middleware.RequireLoginMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "apps.auth.context_processors.firebase",
        ],
    },
}]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Cache
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "stock-trader-pro",
            "TIMEOUT": 300,
        }
    }

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------------------------------
# API Keys
# -------------------------------------------------------------------------
API_KEYS = {
    "FINNHUB": env("FINNHUB_API_KEY", default=""),
    "ALPHA_VANTAGE": env("ALPHA_VANTAGE_API_KEY", default=""),
    "TWELVE_DATA": env("TWELVE_DATA_API_KEY", default=""),
    "POLYGON": env("POLYGON_API_KEY", default=""),
    "NEWSAPI": env("NEWSAPI_KEY", default=""),
    "MARKETAUX": env("MARKETAUX_API_KEY", default=""),
}

RATE_LIMITS = {
    "FINNHUB": env("FINNHUB_RATE_LIMIT"),
    "ALPHA_VANTAGE": env("ALPHA_VANTAGE_RATE_LIMIT"),
}

# -------------------------------------------------------------------------
# Firebase Auth
# -------------------------------------------------------------------------
FIREBASE_CONFIG = {
    "API_KEY": env("FIREBASE_API_KEY", default=""),
    "AUTH_DOMAIN": env("FIREBASE_AUTH_DOMAIN", default=""),
    "PROJECT_ID": env("FIREBASE_PROJECT_ID", default=""),
    "APP_ID": env("FIREBASE_APP_ID", default=""),
}
FIREBASE_PROJECT_ID = FIREBASE_CONFIG["PROJECT_ID"]
REQUIRE_LOGIN = env("REQUIRE_LOGIN")
MASTER_EMAIL = env("MASTER_EMAIL").lower().strip()

# Session: 48 hours by default
SESSION_COOKIE_AGE = env("SESSION_HOURS") * 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True  # Refresh expiry on every request

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "app.log",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "apps": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
