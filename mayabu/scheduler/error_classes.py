"""Operational retailer/adapter error classes.

Consumer APIs never receive these strings. Scheduler/worker logs and
platform_health may store the class. Parser bugs must not be recorded as
retailer blocking.
"""

from __future__ import annotations

from typing import Any

TIMEOUT_MARKERS = ("timeout", "timed out", "timeouterror")
NETWORK_MARKERS = ("connect", "connection", "network", "dns", "proxy", "ssl")
PARSE_MARKERS = ("parse", "json", "selector", "beautifulsoup", "lxml")
CHALLENGE_STATUSES = frozenset({"blocked", "captcha"})
LOGIN_MARKERS = ("login", "sign-in", "signin", "authentication")
EMPTY_MARKERS = ("empty", "no products", "no listings")


def classify_refresh_failure(
    result: Any | None = None,
    exc: BaseException | None = None,
) -> str:
    """Map an adapter outcome to a bounded operational class."""
    page_status = str(getattr(result, "page_status", None) or "").strip().lower()
    if page_status in CHALLENGE_STATUSES:
        return "challenge"
    if page_status == "not_found":
        return "unavailable"
    warnings = [str(item).lower() for item in list(getattr(result, "warnings", None) or [])]
    blob = " ".join(warnings)
    if any(marker in blob for marker in LOGIN_MARKERS):
        return "login_required"
    if page_status == "failed" and any(marker in blob for marker in TIMEOUT_MARKERS):
        return "timeout"
    if page_status in {"failed", "unknown"} and any(marker in blob for marker in NETWORK_MARKERS):
        return "network"
    price = getattr(result, "current_price", None)
    if result is not None and price is None and page_status in {"success", "partial", "unknown", ""}:
        if any(marker in blob for marker in PARSE_MARKERS):
            return "parsing"
        if any(marker in blob for marker in EMPTY_MARKERS) or page_status in {"", "unknown"}:
            return "empty"
        return "invalid_price"
    if exc is not None:
        return classify_exception(exc)
    if page_status == "failed":
        return "unknown"
    if page_status == "partial":
        return "empty"
    return "unknown"


def classify_exception(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    text = f"{name} {exc}".lower()
    if any(marker in text for marker in TIMEOUT_MARKERS):
        return "timeout"
    if any(marker in text for marker in NETWORK_MARKERS):
        return "network"
    if any(marker in text for marker in PARSE_MARKERS):
        return "parsing"
    if any(marker in text for marker in LOGIN_MARKERS):
        return "login_required"
    if "circuit" in text:
        return "blocked"
    return "unknown"
