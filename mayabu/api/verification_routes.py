"""Public endpoints for bounded live price verification."""

from __future__ import annotations

import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from mayabu.api.client_identity import client_identifier
from mayabu.api.rate_limit import SlidingWindowLimiter
from mayabu.core.config import get_app_settings
from mayabu.monitoring import instrumentation as metrics
from mayabu.verification.service import get_verification_job, get_verification_status, request_price_verification

router = APIRouter(prefix="/api", tags=["live-verification"])
_RATE_LIMITER = SlidingWindowLimiter("verify")


class VerifyPriceRequest(BaseModel):
    mode: Literal["best_offer", "all_offers"] = "best_offer"


def _json_safe(value: Any) -> Any:
    """Ensure verification payloads are JSON-serializable (datetimes, UUIDs, Decimals)."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _enforce_rate_limit(request: Request) -> None:
    settings = get_app_settings()
    decision = _RATE_LIMITER.allow(
        client_identifier(request),
        per_key_limit=settings.live_verify_per_user_per_minute,
        global_limit=settings.live_verify_global_per_minute,
        fail_closed_global=settings.environment.lower() in {"production", "prod"},
    )
    if decision == "client_limited":
        metrics.USER_PRICE_VERIFICATION.inc(result="rate_limited")
        raise HTTPException(
            status_code=429,
            detail="Too many verification requests. Please use the recently verified result.",
            headers={"Retry-After": "60"},
        )
    if decision == "global_limited":
        metrics.USER_PRICE_VERIFICATION.inc(result="rate_limited")
        raise HTTPException(
            status_code=429,
            detail="Live verification traffic is high. The last known price remains available; try again shortly.",
            headers={"Retry-After": str(settings.live_verify_busy_retry_seconds)},
        )


@router.post("/products/{product_id}/verify-price", status_code=status.HTTP_202_ACCEPTED)
def verify_price(product_id: str, body: VerifyPriceRequest, request: Request) -> dict:
    _enforce_rate_limit(request)
    started = time.perf_counter()
    try:
        result = request_price_verification(product_id, body.mode)
    except LookupError as exc:
        metrics.USER_PRICE_VERIFICATION.inc(result="not_found")
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        metrics.USER_PRICE_VERIFICATION.inc(result="invalid")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    status_label = str(result.get("status") or "unknown")[:40]
    elapsed_ms = (time.perf_counter() - started) * 1000
    metrics.USER_PRICE_VERIFICATION.inc(result=status_label)
    metrics.USER_PRICE_VERIFICATION_DURATION.observe(elapsed_ms, result=status_label)
    if result["status"] == "busy":
        result["retry_after_seconds"] = get_app_settings().live_verify_busy_retry_seconds
    return _json_safe(result)


@router.get("/verification-jobs/{task_id}")
def verification_job(task_id: str) -> dict:
    job = get_verification_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Verification job not found")
    return _json_safe(job)


@router.get("/products/{product_id}/verification-status")
def product_verification_status(product_id: str) -> dict:
    try:
        return _json_safe(get_verification_status(product_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
