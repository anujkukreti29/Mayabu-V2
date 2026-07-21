"""PostgreSQL-backed durable queue with idempotency."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from psycopg.types.json import Jsonb

from mayabu.db.connection import db_connection
from mayabu_common import canonical_platform, normalize_url


def idempotency_key(task_type: str, platform: str, *, query: str | None = None, url: str | None = None, metadata: dict[str, Any] | None = None) -> str:
    payload = {
        "task_type": task_type,
        "platform": canonical_platform(platform),
        "query": (query or "").strip().lower(),
        "url": normalize_url(url or ""),
        "metadata": metadata or {},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def enqueue_task(
    task_type: str,
    platform: str,
    *,
    query: str | None = None,
    url: str | None = None,
    priority: int = 100,
    max_pages: int | None = None,
    max_products: int | None = None,
    max_attempts: int = 3,
    metadata: dict[str, Any] | None = None,
    created_by: str = "system",
    force: bool = False,
) -> dict[str, Any]:
    platform = canonical_platform(platform)
    allowed_platforms = {"amazon", "flipkart", "croma", "reliancedigital", "system"}
    if platform not in allowed_platforms:
        raise ValueError(f"Unsupported platform: {platform}")
    if platform == "system" and task_type not in {"maintenance", "index_product"}:
        raise ValueError("The system platform is reserved for maintenance and index tasks")
    if not 1 <= int(max_attempts) <= 20:
        raise ValueError("max_attempts must be between 1 and 20")
    if max_pages is not None and int(max_pages) <= 0:
        raise ValueError("max_pages must be positive")
    if max_products is not None and int(max_products) <= 0:
        raise ValueError("max_products must be positive")

    normalized_url = normalize_url(url or "") or None
    key = None if force else idempotency_key(task_type, platform, query=query, url=normalized_url, metadata=metadata)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into scrape_tasks(platform, task_type, query, url, max_pages, max_products,
                                         priority, max_attempts, metadata, idempotency_key, created_by)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (idempotency_key)
                  where idempotency_key is not null and status in ('pending','running','paused')
                do nothing
                returning *
                """,
                (platform, task_type, query, normalized_url, max_pages,
                 max_products, priority, max_attempts, Jsonb(metadata or {}), key, created_by),
            )
            created = cur.fetchone()
            if created:
                return {"created": True, "task": dict(created)}
            if not key:
                raise RuntimeError("Task insert did not return a row")
            cur.execute(
                """
                select * from scrape_tasks
                where idempotency_key = %s and status in ('pending','running','paused')
                order by created_at desc limit 1
                """,
                (key,),
            )
            existing = cur.fetchone()
            if not existing:
                raise RuntimeError("Idempotent task insert conflicted but the active task could not be loaded")
            if task_type == "verify_listing":
                cur.execute(
                    """
                    update scrape_tasks
                    set request_count = request_count + 1, priority = least(priority, %s), updated_at = now()
                    where id = %s
                    returning *
                    """,
                    (priority, existing["id"]),
                )
                existing = cur.fetchone() or existing
            return {"created": False, "task": dict(existing)}


def enqueue_direct_ingest(url: str, platform: str, *, priority: int = 20, created_by: str = "admin", force: bool = False) -> dict[str, Any]:
    return enqueue_task(
        "direct_ingest", platform, url=url, priority=priority,
        metadata={"source": "direct_url"}, created_by=created_by, force=force,
    )


def enqueue_maintenance(job: str = "all", *, priority: int = 200, force: bool = False, created_by: str = "admin") -> dict[str, Any]:
    if job not in {"all", "queue", "search", "storage"}:
        raise ValueError("Unknown maintenance job")
    return enqueue_task(
        "maintenance",
        "system",
        priority=priority,
        metadata={"job": job},
        created_by=created_by,
        force=force,
    )


def get_task(task_id: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from scrape_tasks where id = %s", (task_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def enqueue_verification(
    *,
    platform: str,
    url: str,
    platform_listing_id: str,
    product_id: str,
    priority: int,
    max_attempts: int,
    active_cap: int,
    created_by: str = "public_live_verify",
) -> dict[str, Any]:
    """Atomically join or admit one live-verification task.

    The advisory transaction lock makes the global active queue cap hard even
    when many API processes receive different-product requests simultaneously.
    Existing same-listing work is joined before the cap is checked.
    """
    platform = canonical_platform(platform)
    if platform not in {"amazon", "flipkart", "croma", "reliancedigital"}:
        raise ValueError(f"Unsupported verification platform: {platform}")
    normalized_url = normalize_url(url or "")
    if not normalized_url:
        raise ValueError("Verification URL is required")
    metadata = {
        "platform_listing_id": str(platform_listing_id),
        "product_id": str(product_id),
        "verification_mode": "live",
    }
    # The listing UUID is the stable identity. Product clusters can be merged or
    # reassigned while a verification task is active, which must not create a
    # second task for the same store listing.
    key = idempotency_key(
        "verify_listing",
        platform,
        url=normalized_url,
        metadata={"platform_listing_id": str(platform_listing_id)},
    )
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select * from scrape_tasks
                where idempotency_key = %s and status in ('pending','running','paused')
                order by created_at desc limit 1
                """,
                (key,),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """
                    update scrape_tasks
                    set request_count = request_count + 1,
                        priority = least(priority, %s), updated_at = now()
                    where id = %s
                    returning *
                    """,
                    (priority, existing["id"]),
                )
                return {"created": False, "task": dict(cur.fetchone()), "rejected": None}

            # One tiny global admission critical section. The lock is held only
            # for COUNT + INSERT, never while scraping.
            cur.execute("select pg_advisory_xact_lock(918273645)")
            cur.execute(
                """
                select count(*) as n from scrape_tasks
                where task_type = 'verify_listing' and status in ('pending','running','paused')
                """
            )
            if int(cur.fetchone()["n"]) >= max(1, int(active_cap)):
                return {"created": False, "task": None, "rejected": "queue_busy"}
            cur.execute(
                """
                insert into scrape_tasks(
                  platform, task_type, url, priority, max_attempts, metadata,
                  idempotency_key, created_by
                ) values (%s,'verify_listing',%s,%s,%s,%s,%s,%s)
                returning *
                """,
                (
                    platform,
                    normalized_url,
                    int(priority),
                    int(max_attempts),
                    Jsonb(metadata),
                    key,
                    created_by,
                ),
            )
            return {"created": True, "task": dict(cur.fetchone()), "rejected": None}
