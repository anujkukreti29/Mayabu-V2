"""CSRF helpers for cookie-authenticated browser requests."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request

from mayabu.auth.tokens import generate_token, tokens_equal
from mayabu.core.config import get_app_settings


def new_csrf_token() -> str:
    return generate_token(24)


def origin_allowed(request: Request) -> bool:
    settings = get_app_settings()
    origin = request.headers.get("origin")
    if origin:
        allowed = {o.rstrip("/") for o in settings.cors_origins}
        return origin.rstrip("/") in allowed
    # Same-origin navigations may omit Origin; fall back to Referer host check.
    referer = request.headers.get("referer")
    if not referer:
        # Non-browser clients (tests/tools) without Origin/Referer: allow when
        # CSRF header matches cookie (double-submit still required by caller).
        return True
    try:
        host = urlparse(referer).netloc.lower()
    except (TypeError, ValueError, AttributeError):
        return False
    for allowed in settings.cors_origins:
        try:
            if urlparse(allowed).netloc.lower() == host:
                return True
        except (TypeError, ValueError, AttributeError):
            continue
    return False


def csrf_ok(request: Request, *, cookie_name: str) -> bool:
    if not origin_allowed(request):
        return False
    header = request.headers.get("x-csrf-token") or ""
    cookie = request.cookies.get(cookie_name) or ""
    if not header or not cookie:
        return False
    return tokens_equal(header, cookie)
