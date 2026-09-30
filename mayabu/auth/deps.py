"""Auth request dependencies and cookie helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import Request, Response

from mayabu.auth import repository as repo
from mayabu.auth.csrf import new_csrf_token
from mayabu.core.config import get_app_settings


@dataclass(slots=True)
class AuthUser:
    id: str
    email: str
    display_name: str | None
    email_verified: bool
    created_at: datetime | None
    session_id: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "email_verified": self.email_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def _cookie_secure() -> bool:
    settings = get_app_settings()
    if settings.auth_cookie_secure is not None:
        return settings.auth_cookie_secure
    return settings.environment.lower() in {"production", "prod", "staging"}


def set_session_cookie(response: Response, raw_token: str) -> None:
    settings = get_app_settings()
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=raw_token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_app_settings()
    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite=settings.auth_cookie_samesite,
    )


def ensure_csrf_cookie(response: Response, request: Request) -> str:
    settings = get_app_settings()
    existing = request.cookies.get(settings.auth_csrf_cookie_name)
    token = existing or new_csrf_token()
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=False,
        secure=_cookie_secure(),
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    return token


def clear_csrf_cookie(response: Response) -> None:
    settings = get_app_settings()
    response.delete_cookie(
        key=settings.auth_csrf_cookie_name,
        path="/",
        secure=_cookie_secure(),
        samesite=settings.auth_cookie_samesite,
    )


def resolve_auth_user(request: Request) -> AuthUser | None:
    settings = get_app_settings()
    raw = request.cookies.get(settings.auth_session_cookie_name)
    if not raw:
        return None
    row = repo.get_session_by_token(raw)
    if not row:
        return None
    if row.get("revoked_at") is not None:
        return None
    expires = row.get("expires_at")
    if expires is not None and expires <= datetime.now(expires.tzinfo or None):
        return None
    if (row.get("status") or "").lower() != "active":
        return None
    session_id = str(row["session_id"])
    settings = get_app_settings()
    repo.touch_session(session_id, min_interval_seconds=settings.auth_session_touch_seconds)
    return AuthUser(
        id=str(row["user_id"]),
        email=str(row["email"]),
        display_name=row.get("display_name"),
        email_verified=row.get("email_verified_at") is not None,
        created_at=row.get("created_at"),
        session_id=session_id,
    )


def require_auth_user(request: Request) -> AuthUser:
    user = resolve_auth_user(request)
    if not user:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Authentication required")
    return user
