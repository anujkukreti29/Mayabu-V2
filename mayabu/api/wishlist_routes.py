"""Authenticated wishlist API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from mayabu.api.serializers import serialize_product
from mayabu.auth import repository as repo
from mayabu.auth.csrf import csrf_ok
from mayabu.auth.deps import ensure_csrf_cookie, require_auth_user
from mayabu.core.config import get_app_settings
from mayabu.domain.price_watch import update_watch
from mayabu.monitoring import instrumentation as metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


class WatchBody(BaseModel):
    target_price: float | None = Field(default=None, gt=0, le=10_000_000)
    notify_on_drop: bool = False


def _require_csrf(request: Request) -> None:
    settings = get_app_settings()
    if not csrf_ok(request, cookie_name=settings.auth_csrf_cookie_name):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


@router.get("")
def list_wishlist(request: Request, response: Response, limit: int = Query(default=60, ge=1, le=200)) -> dict[str, Any]:
    user = require_auth_user(request)
    ensure_csrf_cookie(response, request)
    rows = repo.wishlist_list(user.id, limit=limit)
    product_ids = [str(row["id"]) for row in rows if row.get("id")]
    from mayabu.domain.watch_events import (
        derive_watch_state,
        latest_events_by_product,
        list_watch_events,
    )

    latest = latest_events_by_product(user.id, product_ids)
    products = []
    for row in rows:
        payload = serialize_product(row)
        pid = str(row["id"])
        payload["wishlisted_at"] = row["wishlisted_at"].isoformat() if row.get("wishlisted_at") else None
        available = (row.get("status") or "").lower() == "active"
        payload["available"] = available
        target = float(row["target_price"]) if row.get("target_price") is not None else None
        notify = bool(row.get("notify_on_drop"))
        payload["target_price"] = target
        payload["notify_on_drop"] = notify
        payload["watch_delivery"] = "deferred"
        price = payload.get("best_price")
        purchasable = available and price is not None and float(price) > 0
        event = latest.get(pid)
        payload["latest_watch_event"] = (
            {
                "id": str(event["id"]),
                "event_type": event["event_type"],
                "current_price": float(event["current_price"]) if event.get("current_price") is not None else None,
                "previous_price": float(event["previous_price"]) if event.get("previous_price") is not None else None,
                "created_at": event["created_at"].isoformat() if event.get("created_at") else None,
                "seen_at": event["seen_at"].isoformat() if event.get("seen_at") else None,
            }
            if event
            else None
        )
        payload["watch_state"] = derive_watch_state(
            target_price=target,
            notify_on_drop=notify,
            current_price=float(price) if price is not None else None,
            purchasable=purchasable,
            latest_event_type=event.get("event_type") if event else None,
        )
        products.append(payload)

    recent_activity = []
    for event in list_watch_events(user.id, limit=12):
        recent_activity.append(
            {
                "id": str(event["id"]),
                "product_id": str(event["product_id"]),
                "event_type": event["event_type"],
                "current_price": float(event["current_price"]) if event.get("current_price") is not None else None,
                "previous_price": float(event["previous_price"]) if event.get("previous_price") is not None else None,
                "target_price": float(event["target_price"]) if event.get("target_price") is not None else None,
                "title": event.get("title"),
                "created_at": event["created_at"].isoformat() if event.get("created_at") else None,
                "seen_at": event["seen_at"].isoformat() if event.get("seen_at") else None,
            }
        )
    return {
        "products": products,
        "count": len(products),
        "recent_watch_activity": recent_activity,
        "watch_delivery": "deferred",
    }

@router.get("/status")
def wishlist_status(
    request: Request,
    response: Response,
    ids: str = Query(default="", description="Comma-separated product IDs"),
) -> dict[str, Any]:
    user = require_auth_user(request)
    ensure_csrf_cookie(response, request)
    product_ids = [part.strip() for part in ids.split(",") if part.strip()]
    status_map = repo.wishlist_status(user.id, product_ids)
    return {"status": status_map, "count": repo.wishlist_count(user.id)}


@router.post("/{product_id}")
def add_wishlist(product_id: str, request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    user = require_auth_user(request)
    result = repo.wishlist_add(user.id, product_id)
    ensure_csrf_cookie(response, request)
    if result == "rejected":
        metrics.WISHLIST_ACTION.inc(action="add", result="rejected")
        raise HTTPException(status_code=404, detail="Product is not available to save.")
    metrics.WISHLIST_ACTION.inc(action="add", result=result)
    return {"status": result, "count": repo.wishlist_count(user.id)}


@router.delete("/{product_id}")
def remove_wishlist(product_id: str, request: Request, response: Response) -> dict[str, Any]:
    _require_csrf(request)
    user = require_auth_user(request)
    result = repo.wishlist_remove(user.id, product_id)
    ensure_csrf_cookie(response, request)
    metrics.WISHLIST_ACTION.inc(action="remove", result=result)
    return {"status": result, "count": repo.wishlist_count(user.id)}


@router.patch("/{product_id}")
def update_wishlist_watch(
    product_id: str,
    body: WatchBody,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Price-watch foundation. Notifications are not delivered until email is proven."""
    _require_csrf(request)
    user = require_auth_user(request)
    try:
        row = update_watch(
            user.id,
            product_id,
            target_price=body.target_price,
            notify_on_drop=body.notify_on_drop,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ensure_csrf_cookie(response, request)
    if not row:
        raise HTTPException(status_code=404, detail="Product is not available to watch.")
    return {
        "status": "updated",
        "product_id": product_id,
        "target_price": float(row["target_price"]) if row.get("target_price") is not None else None,
        "notify_on_drop": bool(row.get("notify_on_drop")),
        "watch_delivery": "deferred",
        "message": "Watch saved. Mayabu tracks this price inside your account.",
        "count": repo.wishlist_count(user.id),
    }


__all__ = ["router"]
