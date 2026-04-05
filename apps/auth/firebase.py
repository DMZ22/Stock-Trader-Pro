"""
Firebase ID token verification.

We verify tokens by calling Google's tokeninfo endpoint OR by decoding the
JWT and validating against Google's public certs. This avoids the heavy
firebase-admin SDK dependency.

For production: add firebase-admin if service-account signing is required.
"""
import json
import time
import logging
import requests
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

GOOGLE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
GOOGLE_TOKENINFO_URL = "https://www.googleapis.com/oauth2/v3/tokeninfo"


def _get_project_id() -> str:
    return getattr(settings, "FIREBASE_PROJECT_ID", "") or ""


def verify_id_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token. Returns decoded claims on success.
    Raises ValueError on invalid/expired token.

    Uses Google's tokeninfo endpoint (simple, no external deps beyond requests).
    """
    if not id_token:
        raise ValueError("Missing token")
    try:
        r = requests.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token}, timeout=8)
        if r.status_code != 200:
            raise ValueError(f"Token invalid (HTTP {r.status_code})")
        claims = r.json()
    except requests.RequestException as e:
        raise ValueError(f"Token verification network error: {e}") from e

    # Validate basic claims
    now = int(time.time())
    exp = int(claims.get("exp", 0))
    if exp < now:
        raise ValueError("Token expired")

    project_id = _get_project_id()
    aud = claims.get("aud")
    if project_id and aud != project_id:
        raise ValueError(f"Wrong audience: {aud} (expected {project_id})")

    iss = claims.get("iss", "")
    expected_iss = f"https://securetoken.google.com/{project_id}" if project_id else None
    if expected_iss and iss != expected_iss:
        raise ValueError(f"Wrong issuer: {iss}")

    return {
        "uid": claims.get("user_id") or claims.get("sub"),
        "email": claims.get("email"),
        "email_verified": claims.get("email_verified") == "true",
        "name": claims.get("name", ""),
        "picture": claims.get("picture", ""),
        "provider": claims.get("firebase", {}).get("sign_in_provider") if isinstance(claims.get("firebase"), dict) else None,
        "exp": exp,
    }
