"""Security helpers used by API and admin modules."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

from fastapi import Header, HTTPException, status

from mayabu.core.config import get_app_settings

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_query(query: str | None, max_length: int | None = None) -> str:
    """Return a safe normalized query string without control characters."""
    settings = get_app_settings()
    limit = max_length or settings.max_query_length
    text = _CONTROL_CHARS.sub(" ", query or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].strip()
    return text


def hash_identifier(value: str | None, salt: str = "mayabu") -> str | None:
    if not value:
        return None
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8", errors="ignore")).hexdigest()


def require_admin_token(x_mayabu_admin_token: str | None = Header(default=None)) -> None:
    settings = get_app_settings()
    expected = settings.admin_token or ""
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin token is not configured")
    provided = x_mayabu_admin_token or ""
    if not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def ok_response(**values: Any) -> dict[str, Any]:
    return {"ok": True, **values}
