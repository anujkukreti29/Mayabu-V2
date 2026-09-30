"""Bounded scheduler→worker proof helpers.

Live traffic requires explicit CLI opt-in. Tests use fake adapters only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from mayabu.db.connection import db_connection
from mayabu.domain.price_intelligence import get_price_intelligence, serialize_intelligence
from mayabu.platforms.coverage import public_offer_allowed
from mayabu.search.public_price import compute_public_best_price
from mayabu.search.search_repository import get_price_history, get_product, get_product_offers

LIVE_CONFIRM = "MAYABU_LIVE_SMOKE=1"
MAX_LIVE_LISTINGS = 4
MAX_LIVE_DISCOVERY = 1


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


def snapshot_listing(listing_id: str) -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, product_id, platform, category, listing_id, listing_url,
                       listing_url_hash, native_id, match_status, current_price,
                       stock_status, last_successful_refresh_at, observation_count,
                       last_price_change_at, refresh_interval_minutes
                from platform_listings
                where id = %s::uuid
                """,
                (listing_id,),
            )
            row = cur.fetchone()
    if not row:
        raise ValueError(f"listing not found: {listing_id}")
    payload = dict(row)
    product_id = str(payload["product_id"]) if payload.get("product_id") else None
    payload["product_id"] = product_id
    payload["id"] = str(payload["id"])
    if product_id:
        product = get_product(product_id) or {}
        offers = get_product_offers(product_id)
        best = compute_public_best_price(offers, payload.get("category"))
        intel = get_price_intelligence(product_id)
        history = get_price_history(product_id, days=30)
        payload["current_best_price"] = str(best.best_price) if best.best_price is not None else None
        payload["current_best_platform"] = best.best_platform
        payload["public_offer_count"] = len(offers)
        payload["history_days"] = len(history)
        payload["intelligence"] = serialize_intelligence(intel) if intel else None
        payload["product_status"] = product.get("status")
    else:
        payload["current_best_price"] = None
        payload["intelligence"] = None
    return json_safe(payload)


def snapshot_task(task_id: str) -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, platform, task_type, status, priority, created_by, url,
                       metadata, scheduled_at, locked_at, locked_by, lease_expires_at,
                       last_error, attempts, created_at, updated_at, result
                from scrape_tasks
                where id = %s::uuid
                """,
                (task_id,),
            )
            row = cur.fetchone()
    if not row:
        raise ValueError(f"task not found: {task_id}")
    payload = dict(row)
    payload["id"] = str(payload["id"])
    metadata = payload.get("metadata") or {}
    payload["task_source"] = metadata.get("task_source") or payload.get("created_by")
    return json_safe(payload)


def select_live_refresh_listings(limit: int = 2) -> list[dict[str, Any]]:
    """Pick a tiny production-enabled sample. No broad crawl.

    Prefer listings already due. If none are due, fall back to a few matched
    production listings so the bounded smoke can still prove the scheduler
    chain without enabling the catalog scheduler.
    """
    from mayabu.scheduler.refresh_policy import due_refresh_candidates

    cap = max(1, min(int(limit), MAX_LIVE_LISTINGS))
    chosen = _pick_diverse_production(due_refresh_candidates(limit=80), cap, reason="due")
    if len(chosen) < cap:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select id, product_id, platform, category, listing_id, listing_url,
                           native_id, match_status, current_price, stock_status,
                           last_successful_refresh_at
                    from platform_listings
                    where match_status = 'matched'
                      and listing_url is not null
                      and listing_url <> ''
                    order by last_successful_refresh_at asc nulls first
                    limit 40
                    """
                )
                rows = [dict(row) for row in cur.fetchall()]
        extra = _pick_diverse_production(rows, cap, reason="smoke_fallback_not_due")
        seen_ids = {item["id"] for item in chosen}
        for row in extra:
            if row["id"] in seen_ids:
                continue
            chosen.append(row)
            if len(chosen) >= cap:
                break
        if len(chosen) < cap:
            # Same platform/category is acceptable when the local catalog has no other pair.
            for row in rows:
                payload_id = str(row["id"])
                if payload_id in seen_ids:
                    continue
                url = str(row.get("listing_url") or "")
                if _is_synthetic_smoke_url(url, str(row.get("listing_id") or "")):
                    continue
                if not public_offer_allowed(str(row.get("platform") or ""), str(row.get("category") or "")):
                    continue
                if str(row.get("match_status") or "") != "matched":
                    continue
                payload = dict(row)
                payload["id"] = payload_id
                if payload.get("product_id"):
                    payload["product_id"] = str(payload["product_id"])
                payload["smoke_eligibility"] = "smoke_same_pair_fill"
                chosen.append(payload)
                seen_ids.add(payload_id)
                if len(chosen) >= cap:
                    break
    return chosen[:cap]


def _is_synthetic_smoke_url(url: str, listing_id: str | None = None) -> bool:
    blob = f"{url or ''} {listing_id or ''}".lower()
    return "runtime-" in blob or "b0runtime" in blob


def _pick_diverse_production(rows: list[dict[str, Any]], cap: int, *, reason: str) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    chosen: list[dict[str, Any]] = []
    for row in rows:
        platform = str(row.get("platform") or "")
        category = str(row.get("category") or "")
        url = str(row.get("listing_url") or "")
        public_id = str(row.get("listing_id") or "")
        if _is_synthetic_smoke_url(url, public_id):
            continue
        if not public_offer_allowed(platform, category):
            continue
        if not url:
            continue
        if str(row.get("match_status") or "") != "matched":
            continue
        key = (platform, category)
        if key in seen:
            continue
        seen.add(key)
        payload = dict(row)
        payload["id"] = str(payload["id"])
        if payload.get("product_id"):
            payload["product_id"] = str(payload["product_id"])
        payload["smoke_eligibility"] = reason
        chosen.append(payload)
        if len(chosen) >= cap:
            break
    return chosen


def select_live_discovery_plan() -> dict[str, Any] | None:
    from mayabu.platforms.coverage import discovery_allowed

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from scheduler_plans
                where enabled = true
                order by last_materialized_at asc nulls first, priority asc
                limit 20
                """
            )
            plans = [dict(row) for row in cur.fetchall()]
    for plan in plans:
        metadata = plan.get("metadata") or {}
        category = metadata.get("category") if isinstance(metadata, dict) else None
        platform = str(plan.get("platform") or "")
        if category and discovery_allowed(platform, str(category)):
            plan["id"] = str(plan["id"])
            return plan
        if not category:
            continue
    return None


def find_scheduler_refresh_task(listing_uuid: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select *
                from scrape_tasks
                where task_type = 'refresh_listing'
                  and created_by = 'scheduler'
                  and metadata->>'platform_listing_id' = %s
                order by created_at desc
                limit 1
                """,
                (listing_uuid,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
