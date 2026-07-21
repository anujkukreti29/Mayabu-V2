"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from mayabu.monitoring.health import collect_health, readiness

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    return collect_health()


@router.get("/live")
def live() -> dict:
    return {"status": "ok", "service": "mayabu-backend"}


@router.get("/ready")
def ready() -> dict:
    data = readiness()
    if not data.get("ready"):
        raise HTTPException(status_code=503, detail=data)
    return data
