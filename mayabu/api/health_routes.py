"""Liveness, readiness, health, and metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Response

from mayabu import __version__
from mayabu.core.config import get_app_settings
from mayabu.monitoring.health import collect_health, collect_liveness, readiness
from mayabu.monitoring.registry import get_registry

router = APIRouter(prefix="/api", tags=["health"])


def _require_admin_token(x_mayabu_admin_token: str | None) -> None:
    settings = get_app_settings()
    if not settings.admin_token:
        # Development without admin token: allow local diagnostics.
        if settings.is_deployed_environment():
            raise HTTPException(status_code=401, detail="admin_token_required")
        return
    if x_mayabu_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/health")
def health(
    x_mayabu_admin_token: str | None = Header(default=None, alias="X-Mayabu-Admin-Token"),
) -> dict:
    settings = get_app_settings()
    if settings.detailed_health_requires_admin():
        _require_admin_token(x_mayabu_admin_token)
    data = collect_health()
    if settings.release_version:
        data["release_version"] = settings.release_version
    if settings.git_sha:
        data["git_sha"] = settings.git_sha[:12]
    data["api_version"] = __version__
    return data


@router.get("/live")
def live() -> dict:
    data = collect_liveness()
    settings = get_app_settings()
    if settings.release_version:
        data["release_version"] = settings.release_version
    return data


@router.get("/ready")
def ready() -> dict:
    data = readiness()
    if not data.get("ready"):
        raise HTTPException(status_code=503, detail=data)
    return data


@router.get("/metrics")
def metrics(
    x_mayabu_admin_token: str | None = Header(default=None, alias="X-Mayabu-Admin-Token"),
) -> Response:
    """Prometheus text exposition. Protected whenever admin token is configured or env is deployed."""
    settings = get_app_settings()
    if settings.admin_token or settings.is_deployed_environment():
        _require_admin_token(x_mayabu_admin_token)
    body = get_registry().render_prometheus()
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control": "private, no-store"},
    )
