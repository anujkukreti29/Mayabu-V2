"""Account authentication API routes."""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from psycopg.errors import IntegrityError, UniqueViolation
from pydantic import BaseModel, Field

from mayabu.api.client_identity import client_identifier
from mayabu.api.rate_limit import SlidingWindowLimiter
from mayabu.auth import repository as repo
from mayabu.auth.csrf import csrf_ok
from mayabu.auth.deps import (
    clear_session_cookie,
    ensure_csrf_cookie,
    require_auth_user,
    resolve_auth_user,
    set_session_cookie,
)
from mayabu.auth.email import OutboundEmail, get_email_outbox, get_email_sender
from mayabu.auth.email_templates import (
    password_changed_email,
    password_reset_email,
    verification_email,
)
from mayabu.auth.passwords import (
    is_valid_email,
    normalize_email,
    validate_password,
    verify_password,
)
from mayabu.core.config import get_app_settings
from mayabu.core.security import hash_identifier
from mayabu.monitoring import instrumentation as metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

_LOGIN_LIMITER = SlidingWindowLimiter("auth_login")
_REGISTER_LIMITER = SlidingWindowLimiter("auth_register")
_FORGOT_LIMITER = SlidingWindowLimiter("auth_forgot")
_RESEND_LIMITER = SlidingWindowLimiter("auth_resend")

_SAFE_NEXT = re.compile(r"^/[a-zA-Z0-9/_?&=.\-~%]*$")


class RegisterBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ForgotBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ResetBody(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=128)


class VerifyBody(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class DisplayNameBody(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)


class RevokeSessionBody(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)


def _require_csrf(request: Request) -> None:
    settings = get_app_settings()
    if not csrf_ok(request, cookie_name=settings.auth_csrf_cookie_name):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def _rate_limited(
    limiter: SlidingWindowLimiter,
    key: str,
    limit: int,
    response: Response | None = None,
) -> None:
    result = limiter.allow(key, per_key_limit=limit, global_limit=limit * 20)
    if result != "allowed":
        if response is not None:
            response.headers["Retry-After"] = "60"
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again in a few minutes.",
            headers={"Retry-After": "60"},
        )


def _verification_link(token: str) -> str:
    base = get_app_settings().auth_public_base_url.rstrip("/")
    return f"{base}/verify-email?token={token}"


def _reset_link(token: str) -> str:
    base = get_app_settings().auth_public_base_url.rstrip("/")
    return f"{base}/reset-password?token={token}"


def _send_verification(email: str, token: str) -> bool:
    settings = get_app_settings()
    link = _verification_link(token)
    content = verification_email(
        to_email=email,
        verify_url=link,
        hours=settings.auth_verification_hours,
    )
    message = OutboundEmail(
        to=email,
        subject=content.subject,
        text_body=content.text_body,
        html_body=content.html_body,
        kind=content.kind,
        meta={"token": token},
    )
    return get_email_sender().send(message)


def _send_reset(email: str, token: str) -> bool:
    settings = get_app_settings()
    link = _reset_link(token)
    content = password_reset_email(reset_url=link, hours=settings.auth_reset_hours)
    message = OutboundEmail(
        to=email,
        subject=content.subject,
        text_body=content.text_body,
        html_body=content.html_body,
        kind=content.kind,
        meta={"token": token},
    )
    return get_email_sender().send(message)


def _send_password_changed(email: str) -> bool:
    content = password_changed_email()
    message = OutboundEmail(
        to=email,
        subject=content.subject,
        text_body=content.text_body,
        html_body=content.html_body,
        kind=content.kind,
    )
    return get_email_sender().send(message)


def _device_label(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    browser = "Browser"
    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "chrome/" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "safari/" in ua and "chrome/" not in ua:
        browser = "Safari"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"

    system = "device"
    if "iphone" in ua or "ipad" in ua:
        system = "iPhone" if "iphone" in ua else "iPad"
    elif "android" in ua:
        system = "Android"
    elif "windows" in ua:
        system = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        system = "macOS"
    elif "linux" in ua:
        system = "Linux"
    return f"{browser} on {system}"


def safe_next_path(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None
    if not _SAFE_NEXT.match(candidate):
        return None
    if "://" in candidate:
        return None
    return candidate


@router.get("/csrf")
def get_csrf(request: Request, response: Response) -> dict[str, str]:
    token = ensure_csrf_cookie(response, request)
    return {"csrf_token": token}


@router.get("/me")
def auth_me(request: Request, response: Response) -> dict[str, Any]:
    ensure_csrf_cookie(response, request)
    user = resolve_auth_user(request)
    metrics.AUTH_SESSION.inc(result="ok" if user else "anonymous")
    if not user:
        return {"user": None, "wishlist_count": 0}
    return {"user": user.public_dict(), "wishlist_count": repo.wishlist_count(user.id)}


@router.post("/register")
def register(body: RegisterBody, request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    settings = get_app_settings()
    client = client_identifier(request)
    _rate_limited(_REGISTER_LIMITER, hash_identifier(client), settings.auth_register_per_minute, response)

    if not is_valid_email(body.email):
        metrics.AUTH_REGISTER.inc(result="invalid")
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    password_error = validate_password(body.password)
    if password_error:
        metrics.AUTH_REGISTER.inc(result="invalid")
        raise HTTPException(status_code=400, detail=password_error)

    try:
        user = repo.create_user(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
        )
    except (UniqueViolation, IntegrityError):
        metrics.AUTH_REGISTER.inc(result="duplicate")
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Sign in or reset your password.",
        ) from None
    except Exception:
        logger.exception("auth_register_failed")
        metrics.AUTH_REGISTER.inc(result="error")
        raise HTTPException(status_code=500, detail="Could not create account.") from None

    token = repo.create_email_verification_token(
        str(user["id"]), hours=settings.auth_verification_hours
    )
    delivered = _send_verification(str(user["email"]), token)
    raw_session, _ = repo.create_session(
        str(user["id"]),
        lifetime_days=settings.auth_session_days,
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, raw_session)
    ensure_csrf_cookie(response, request)
    metrics.AUTH_REGISTER.inc(result="ok")
    metrics.AUTH_SESSION_EVENT.inc(event="created")
    logger.info(
        "auth_register_success",
        extra={"event": "auth_register", "email_delivered": delivered},
    )
    return {
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "display_name": user.get("display_name"),
            "email_verified": False,
            "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
        },
        "verification_email_queued": delivered,
        "message": "Account created. Check your email to verify your address.",
    }


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    settings = get_app_settings()
    client = client_identifier(request)
    normalized = normalize_email(body.email)
    _rate_limited(
        _LOGIN_LIMITER,
        hash_identifier(f"{client}:{normalized}"),
        settings.auth_login_per_minute,
        response,
    )

    user = repo.get_user_by_normalized_email(body.email)
    invalid = (
        user is None
        or (user.get("status") or "").lower() != "active"
        or not verify_password(str(user.get("password_hash") or ""), body.password)
    )
    if invalid:
        metrics.AUTH_LOGIN.inc(result="failure")
        logger.info("auth_login_failure", extra={"event": "auth_login"})
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    raw_session, _ = repo.create_session(
        str(user["id"]),
        lifetime_days=settings.auth_session_days,
        user_agent=request.headers.get("user-agent"),
    )
    repo.touch_last_login(str(user["id"]))
    set_session_cookie(response, raw_session)
    ensure_csrf_cookie(response, request)
    metrics.AUTH_LOGIN.inc(result="success")
    metrics.AUTH_SESSION_EVENT.inc(event="created")
    logger.info("auth_login_success", extra={"event": "auth_login"})
    return {
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "display_name": user.get("display_name"),
            "email_verified": user.get("email_verified_at") is not None,
            "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
        }
    }


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    # Logout is idempotent; CSRF still required for browser callers.
    settings = get_app_settings()
    if request.cookies.get(settings.auth_session_cookie_name):
        _require_csrf(request)
    raw = request.cookies.get(settings.auth_session_cookie_name)
    if raw and repo.revoke_session_by_token(raw):
        metrics.AUTH_SESSION_EVENT.inc(event="revoked")
    clear_session_cookie(response)
    ensure_csrf_cookie(response, request)
    metrics.AUTH_LOGIN.inc(result="logout")
    logger.info("auth_logout", extra={"event": "auth_logout"})
    return {"status": "ok"}


@router.post("/logout-all")
def logout_all(request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    user = require_auth_user(request)
    revoked = repo.revoke_all_user_sessions(user.id)
    clear_session_cookie(response)
    ensure_csrf_cookie(response, request)
    metrics.AUTH_SESSION_EVENT.inc(event="revoked_all")
    logger.info("auth_logout_all", extra={"event": "auth_logout_all", "revoked": revoked})
    return {"status": "ok", "revoked": revoked}


@router.post("/logout-others")
def logout_others(request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    user = require_auth_user(request)
    revoked = repo.revoke_other_sessions(user.id, user.session_id)
    ensure_csrf_cookie(response, request)
    metrics.AUTH_SESSION_EVENT.inc(event="revoked_others")
    return {"status": "ok", "revoked": revoked}


@router.get("/sessions")
def list_sessions(request: Request, response: Response) -> dict[str, Any]:
    user = require_auth_user(request)
    ensure_csrf_cookie(response, request)
    rows = repo.list_active_sessions(user.id)
    sessions = []
    for row in rows:
        session_id = str(row["id"])
        sessions.append(
            {
                "id": session_id,
                "current": session_id == user.session_id,
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "last_seen_at": row["last_seen_at"].isoformat() if row.get("last_seen_at") else None,
                "device_label": _device_label(row.get("user_agent")),
            }
        )
    return {"sessions": sessions}


@router.post("/sessions/revoke")
def revoke_one_session(
    body: RevokeSessionBody, request: Request, response: Response
) -> dict[str, Any]:
    _require_csrf(request)
    user = require_auth_user(request)
    ensure_csrf_cookie(response, request)
    target = body.session_id.strip()
    if target == user.session_id:
        # Revoking current session is logout.
        repo.revoke_session_for_user(user.id, target)
        clear_session_cookie(response)
        metrics.AUTH_SESSION_EVENT.inc(event="revoked")
        return {"status": "ok", "current_revoked": True}
    revoked = repo.revoke_session_for_user(user.id, target)
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found or already signed out.")
    metrics.AUTH_SESSION_EVENT.inc(event="revoked")
    return {"status": "ok", "current_revoked": False}


@router.post("/verify-email")
def verify_email(body: VerifyBody, request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    user_id, status = repo.consume_email_verification_token(body.token.strip())
    ensure_csrf_cookie(response, request)
    if status == "already_verified":
        metrics.AUTH_REGISTER.inc(result="verify_already")
        return {"status": "already_verified"}
    if status != "ok" or not user_id:
        metrics.AUTH_REGISTER.inc(result="verify_invalid")
        detail = {
            "expired": "This verification link has expired.",
            "used": "This verification link was already used.",
            "invalid": "This verification link is invalid or expired.",
        }.get(status, "This verification link is invalid or expired.")
        raise HTTPException(status_code=400, detail=detail)
    logger.info("auth_email_verified", extra={"event": "auth_verify"})
    metrics.AUTH_REGISTER.inc(result="verified")
    return {"status": "verified"}


@router.post("/resend-verification")
def resend_verification(request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    settings = get_app_settings()
    user = require_auth_user(request)
    client = client_identifier(request)
    _rate_limited(
        _RESEND_LIMITER,
        hash_identifier(f"{client}:{user.id}"),
        settings.auth_resend_per_minute,
        response,
    )
    ensure_csrf_cookie(response, request)
    if user.email_verified:
        return {"status": "already_verified"}
    token = repo.create_email_verification_token(user.id, hours=settings.auth_verification_hours)
    delivered = _send_verification(user.email, token)
    return {
        "status": "queued" if delivered else "delivery_failed",
        "retry_after_seconds": 60 if not delivered else None,
    }


@router.post("/forgot-password")
def forgot_password(body: ForgotBody, request: Request, response: Response) -> dict[str, str]:
    _require_csrf(request)
    settings = get_app_settings()
    client = client_identifier(request)
    _rate_limited(_FORGOT_LIMITER, hash_identifier(client), settings.auth_forgot_per_minute, response)
    ensure_csrf_cookie(response, request)

    # Always generic — do not reveal account existence.
    user = repo.get_user_by_normalized_email(body.email) if is_valid_email(body.email) else None
    if user and (user.get("status") or "").lower() == "active":
        token = repo.create_password_reset_token(str(user["id"]), hours=settings.auth_reset_hours)
        _send_reset(str(user["email"]), token)
    logger.info("auth_forgot_password", extra={"event": "auth_forgot"})
    return {
        "message": "If an account exists for that email, we'll send password reset instructions.",
    }


@router.post("/reset-password")
def reset_password(body: ResetBody, request: Request, response: Response) -> dict[str, str]:
    _require_csrf(request)
    password_error = validate_password(body.password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)
    user_id, status = repo.consume_password_reset_token(body.token.strip(), body.password)
    clear_session_cookie(response)
    ensure_csrf_cookie(response, request)
    if status != "ok" or not user_id:
        detail = {
            "expired": "This reset link has expired.",
            "used": "This reset link was already used.",
            "invalid": "This reset link is invalid or expired.",
        }.get(status, "This reset link is invalid or expired.")
        raise HTTPException(status_code=400, detail=detail)
    user = repo.get_user_by_id(user_id)
    if user:
        _send_password_changed(str(user["email"]))
    metrics.AUTH_SESSION_EVENT.inc(event="reset_success")
    logger.info("auth_password_reset", extra={"event": "auth_reset"})
    return {
        "status": "ok",
        "message": "Password updated. Existing sessions were signed out. Please sign in.",
    }


@router.patch("/me")
def update_me(body: DisplayNameBody, request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    user = require_auth_user(request)
    updated = repo.update_display_name(user.id, body.display_name)
    ensure_csrf_cookie(response, request)
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found")
    return {
        "user": {
            "id": str(updated["id"]),
            "email": updated["email"],
            "display_name": updated.get("display_name"),
            "email_verified": updated.get("email_verified_at") is not None,
            "created_at": updated["created_at"].isoformat() if updated.get("created_at") else None,
        }
    }


@router.get("/dev/last-outbound")
def dev_last_outbound(request: Request, kind: str | None = None) -> dict[str, Any]:
    """Test/dev inbox peek. Disabled unless MAYABU_AUTH_DEV_INBOX=1 and non-production."""
    settings = get_app_settings()
    if settings.environment.lower() in {"production", "prod"} or not settings.auth_dev_inbox_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    message = get_email_outbox().latest(kind=kind)
    if not message:
        return {"message": None}
    return {
        "message": {
            "to": message.to,
            "subject": message.subject,
            "kind": message.kind,
            "text_body": message.text_body,
            "meta": message.meta,
            "created_at": message.created_at.isoformat(),
        }
    }


@router.get("/dev/email-preview")
def dev_email_preview(kind: str = "verification") -> dict[str, Any]:
    """Developer-only template preview. Never public in production."""
    settings = get_app_settings()
    if settings.environment.lower() in {"production", "prod"} or not settings.auth_dev_inbox_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    sample_url = f"{settings.auth_public_base_url.rstrip('/')}/verify-email?token=preview-token"
    if kind == "password_reset":
        content = password_reset_email(reset_url=sample_url.replace("verify-email", "reset-password"), hours=2)
    elif kind == "password_changed":
        content = password_changed_email()
    else:
        content = verification_email(to_email="preview@example.com", verify_url=sample_url, hours=48)
    return {
        "kind": content.kind,
        "subject": content.subject,
        "text_body": content.text_body,
        "html_body": content.html_body,
    }


__all__ = ["router", "safe_next_path"]
