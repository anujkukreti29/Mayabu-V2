"""Efficient user-triggered live price verification orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

from mayabu.core.config import get_app_settings
from mayabu.jobs.queue import enqueue_verification, get_task
from mayabu.search.cache import get_cache
from mayabu.search.search_repository import get_product_offers, product_exists
from mayabu.verification.repository import get_product_verification_status

_CACHE = get_cache()


def _age_seconds(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - value).total_seconds()))


def _best_offer(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [row for row in offers if row.get("stock_status") != "out_of_stock" and row.get("current_price") is not None]
    source = eligible or [row for row in offers if row.get("current_price") is not None] or offers
    return sorted(source, key=lambda row: (row.get("current_price") is None, row.get("current_price") or 10**18))[:1]


def _request_price_verification_uncached(product_id: str, mode: str = "best_offer") -> dict[str, Any]:
    settings = get_app_settings()
    if mode not in {"best_offer", "all_offers"}:
        raise ValueError("mode must be best_offer or all_offers")

    # Hot path: load offers first. Only perform the extra existence query when
    # there are no offers, which keeps normal verification to fewer DB round trips.
    offers = [dict(row) for row in get_product_offers(product_id)]
    if not offers:
        if not product_exists(product_id):
            raise LookupError("Product not found")
        return {"status": "no_offers", "product_id": product_id, "task_ids": [], "offers": []}

    selected = _best_offer(offers) if mode == "best_offer" else offers[: settings.live_verify_max_offers_per_request]
    skipped: list[dict[str, Any]] = []
    due: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for offer in selected:
        listing_id = str(offer["id"])
        cached = _CACHE.get_json(f"verification:listing:{listing_id}")
        cached_age = _age_seconds(cached.get("verified_at")) if cached else None
        age = _age_seconds(offer.get("last_verified_at") or offer.get("last_successful_refresh_at"))
        if cached_age is not None and cached_age <= settings.live_verify_fresh_seconds:
            skipped.append({"listing_id": listing_id, "platform": offer.get("platform"), "reason": "fresh_cache", "result": cached})
            continue
        if age is not None and age <= settings.live_verify_fresh_seconds:
            skipped.append({"listing_id": listing_id, "platform": offer.get("platform"), "reason": "recently_verified", "age_seconds": age})
            continue
        next_allowed = offer.get("next_allowed_verification_at")
        if next_allowed and next_allowed > now:
            skipped.append({"listing_id": listing_id, "platform": offer.get("platform"), "reason": "cooldown", "next_allowed_at": next_allowed})
            continue
        due.append(offer)

    tasks: list[dict[str, Any]] = []
    for offer in due:
        listing_id = str(offer["id"])
        queued = enqueue_verification(
            platform=str(offer["platform"]),
            url=str(offer["listing_url"]),
            platform_listing_id=listing_id,
            product_id=product_id,
            priority=settings.live_verify_priority,
            max_attempts=settings.live_verify_max_attempts,
            active_cap=settings.live_verify_queue_max_active,
        )
        if queued.get("rejected") == "queue_busy":
            skipped.append({"listing_id": listing_id, "platform": offer.get("platform"), "reason": "queue_busy"})
            continue
        task = queued["task"]
        tasks.append({"task_id": str(task["id"]), "listing_id": listing_id, "platform": offer.get("platform"), "created": bool(queued["created"])})

    if tasks:
        status = "queued" if any(item["created"] for item in tasks) else "joined"
    elif skipped and all(item["reason"] in {"fresh_cache", "recently_verified"} for item in skipped):
        status = "fresh"
    elif skipped and any(item["reason"] == "queue_busy" for item in skipped):
        status = "busy"
    else:
        status = "cooldown"
    return {
        "status": status,
        "product_id": product_id,
        "mode": mode,
        "task_ids": [item["task_id"] for item in tasks],
        "tasks": tasks,
        "skipped": skipped,
        "estimated_seconds": settings.live_verify_estimated_seconds,
        "message": "Cached prices remain visible while Mayabu verifies selected store listings.",
    }


def request_price_verification(product_id: str, mode: str = "best_offer") -> dict[str, Any]:
    """Coalesce request bursts in Redis, with PostgreSQL idempotency as fallback."""
    response_key = f"verification:request:{product_id}:{mode}"
    cached = _CACHE.get_json(response_key)
    if cached is not None:
        result = dict(cached)
        if result.get("status") == "queued":
            result["status"] = "joined"
        result["coalesced"] = True
        return result

    lock_key = f"verification:request-lock:{product_id}:{mode}"
    leader = _CACHE.set_if_absent(lock_key, {"started": True}, 3)
    if leader is False:
        for _ in range(5):
            time.sleep(0.05)
            cached = _CACHE.get_json(response_key)
            if cached is not None:
                result = dict(cached)
                if result.get("status") == "queued":
                    result["status"] = "joined"
                result["coalesced"] = True
                return result

    try:
        result = _request_price_verification_uncached(product_id, mode)
        _CACHE.set_json(response_key, result, 2)
        return result
    finally:
        if leader is True:
            _CACHE.delete(lock_key)


def get_verification_job(task_id: str) -> dict[str, Any] | None:
    cache_key = f"verification:job:{task_id}"
    cached = _CACHE.get_json(cache_key)
    if cached is not None:
        return cached
    task = get_task(task_id)
    if not task or task.get("task_type") != "verify_listing":
        return None
    response = {
        "task_id": str(task["id"]),
        "status": task.get("status"),
        "platform": task.get("platform"),
        "attempts": int(task.get("attempts") or 0),
        "request_count": int(task.get("request_count") or 1),
        "result": task.get("result") or {},
        "last_error": task.get("last_error"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
    }
    terminal = response["status"] in {"completed", "failed", "dead", "cancelled"}
    _CACHE.set_json(cache_key, response, 300 if terminal else 3)
    return response


def get_verification_status(product_id: str) -> dict[str, Any]:
    if not product_exists(product_id):
        raise LookupError("Product not found")
    return get_product_verification_status(product_id)
