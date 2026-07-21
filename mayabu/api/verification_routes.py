"""Public endpoints for bounded live price verification."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from mayabu.api.client_identity import client_identifier
from mayabu.api.rate_limit import SlidingWindowLimiter
from mayabu.core.config import get_app_settings
from mayabu.verification.service import get_verification_job, get_verification_status, request_price_verification

router = APIRouter(prefix="/api", tags=["live-verification"])
_RATE_LIMITER = SlidingWindowLimiter("verify")


class VerifyPriceRequest(BaseModel):
    mode: Literal["best_offer", "all_offers"] = "best_offer"


def _enforce_rate_limit(request: Request) -> None:
    settings = get_app_settings()
    decision = _RATE_LIMITER.allow(
        client_identifier(request),
        per_key_limit=settings.live_verify_per_user_per_minute,
        global_limit=settings.live_verify_global_per_minute,
        fail_closed_global=settings.environment.lower() in {"production", "prod"},
    )
    if decision == "client_limited":
        raise HTTPException(
            status_code=429,
            detail="Too many verification requests. Please use the recently verified result.",
            headers={"Retry-After": "60"},
        )
    if decision == "global_limited":
        raise HTTPException(
            status_code=429,
            detail="Live verification traffic is high. The last known price remains available; try again shortly.",
            headers={"Retry-After": str(settings.live_verify_busy_retry_seconds)},
        )


@router.post("/products/{product_id}/verify-price", status_code=status.HTTP_202_ACCEPTED)
def verify_price(product_id: str, body: VerifyPriceRequest, request: Request) -> dict:
    _enforce_rate_limit(request)
    try:
        result = request_price_verification(product_id, body.mode)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result["status"] == "busy":
        result["retry_after_seconds"] = get_app_settings().live_verify_busy_retry_seconds
    return result


@router.get("/verification-jobs/{task_id}")
def verification_job(task_id: str) -> dict:
    job = get_verification_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Verification job not found")
    return job


@router.get("/products/{product_id}/verification-status")
def product_verification_status(product_id: str) -> dict:
    try:
        return get_verification_status(product_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
