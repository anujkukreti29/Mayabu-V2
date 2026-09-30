"""Security headers and private-cache helpers for Mayabu API responses."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from mayabu.core.config import get_app_settings

_PRIVATE_PREFIXES = (
    "/api/auth/",
    "/api/wishlist",
    "/api/admin",
)


def _is_https_request(request: Request) -> bool:
    settings = get_app_settings()
    if request.url.scheme == "https":
        return True
    if not settings.trust_proxy_headers:
        return False
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return proto == "https"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        settings = get_app_settings()
        env = settings.environment.lower()
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        # Conservative API CSP — JSON/API only; browsers navigate retailer links outside this app.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        path = request.url.path
        if path.startswith(_PRIVATE_PREFIXES):
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Vary"] = "Cookie"
        if env in {"production", "prod", "staging"} and _is_https_request(request):
            # One year HSTS; preload is a deliberate future edge decision — not set here.
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
