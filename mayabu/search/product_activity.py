"""Privacy-conscious aggregate product activity for homepage discovery."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from psycopg.errors import UndefinedTable

from mayabu.db.connection import db_connection
from mayabu.search.search_repository import product_exists

# Nested db_connection/cursor with-blocks match the rest of the Mayabu data layer.
# ruff: noqa: SIM117

logger = logging.getLogger(__name__)

EventType = Literal["product_view", "search_click", "retailer_click"]
ALLOWED_EVENTS: frozenset[str] = frozenset({"product_view", "search_click", "retailer_click"})

# Minimum absolute events before ranking appears on the homepage.
TRENDING_MIN_RECENT = 3
POPULAR_MIN_WINDOW = 5
TRENDING_RECENT_HOURS = 48
TRENDING_BASELINE_HOURS = 48
POPULAR_WINDOW_HOURS = 24 * 7


def _hour_bucket(now: datetime | None = None) -> datetime:
    moment = now or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _client_hash(client_id: str | None) -> str | None:
    text = (client_id or "").strip()
    if not text or len(text) > 128:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def record_product_activity(
    *,
    product_id: str,
    event_type: str,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Increment a bounded hourly aggregate. No PII stored."""
    if event_type not in ALLOWED_EVENTS:
        return {"accepted": False, "reason": "invalid_event"}
    try:
        uuid.UUID(str(product_id))
    except (TypeError, ValueError):
        return {"accepted": False, "reason": "invalid_product"}
    if not product_exists(product_id):
        return {"accepted": False, "reason": "unknown_product"}

    bucket = _hour_bucket()
    client_key = _client_hash(client_id)

    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                if client_key:
                    cur.execute(
                        """
                        insert into product_activity_dedupe(client_hash, product_id, event_type, hour_bucket)
                        values (%s, %s::uuid, %s, %s)
                        on conflict do nothing
                        returning 1
                        """,
                        (client_key, product_id, event_type, bucket),
                    )
                    if cur.fetchone() is None:
                        return {"accepted": True, "deduped": True, "hour_bucket": bucket.isoformat()}

                cur.execute(
                    """
                    insert into product_activity_hourly(product_id, event_type, hour_bucket, event_count)
                    values (%s::uuid, %s, %s, 1)
                    on conflict (product_id, event_type, hour_bucket)
                    do update set event_count = product_activity_hourly.event_count + 1,
                                  updated_at = now()
                    """,
                    (product_id, event_type, bucket),
                )
    except UndefinedTable:
        logger.warning("product_activity tables missing; skipping activity write")
        return {"accepted": False, "reason": "activity_schema_missing"}
    return {"accepted": True, "deduped": False, "hour_bucket": bucket.isoformat()}


def _fetch_activity_scores(
    *,
    recent_hours: int,
    baseline_hours: int = 0,
    min_recent: int = 1,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Return product_id scores from hourly aggregates."""
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                if baseline_hours > 0:
                    cur.execute(
                        """
                        with recent as (
                          select product_id, sum(event_count)::int as recent_count
                          from product_activity_hourly
                          where hour_bucket >= date_trunc('hour', now() at time zone 'utc')
                                            - (%s::int * interval '1 hour')
                          group by product_id
                        ),
                        baseline as (
                          select product_id, sum(event_count)::int as baseline_count
                          from product_activity_hourly
                          where hour_bucket >= date_trunc('hour', now() at time zone 'utc')
                                            - ((%s::int + %s::int) * interval '1 hour')
                            and hour_bucket < date_trunc('hour', now() at time zone 'utc')
                                            - (%s::int * interval '1 hour')
                          group by product_id
                        )
                        select r.product_id::text as product_id,
                               r.recent_count,
                               coalesce(b.baseline_count, 0) as baseline_count,
                               (r.recent_count::float / greatest(coalesce(b.baseline_count, 0), 1)) as momentum
                        from recent r
                        left join baseline b on b.product_id = r.product_id
                        where r.recent_count >= %s
                        order by momentum desc, r.recent_count desc, r.product_id asc
                        limit %s
                        """,
                        (
                            recent_hours,
                            recent_hours,
                            baseline_hours,
                            recent_hours,
                            min_recent,
                            limit,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        select product_id::text as product_id,
                               sum(event_count)::int as recent_count,
                               0 as baseline_count,
                               sum(event_count)::float as momentum
                        from product_activity_hourly
                        where hour_bucket >= date_trunc('hour', now() at time zone 'utc')
                                          - (%s::int * interval '1 hour')
                        group by product_id
                        having sum(event_count) >= %s
                        order by sum(event_count) desc, product_id asc
                        limit %s
                        """,
                        (recent_hours, min_recent, limit),
                    )
                return [dict(row) for row in cur.fetchall()]
    except UndefinedTable:
        logger.warning("product_activity_hourly missing; trending/popular sections empty")
        return []


def trending_product_ids(*, limit: int = 12) -> list[str]:
    rows = _fetch_activity_scores(
        recent_hours=TRENDING_RECENT_HOURS,
        baseline_hours=TRENDING_BASELINE_HOURS,
        min_recent=TRENDING_MIN_RECENT,
        limit=limit,
    )
    # Prefer acceleration: recent > baseline, or strong absolute recent when baseline is empty.
    out: list[str] = []
    for row in rows:
        recent = int(row.get("recent_count") or 0)
        baseline = int(row.get("baseline_count") or 0)
        if recent < TRENDING_MIN_RECENT:
            continue
        if baseline > 0 and recent <= baseline:
            continue
        out.append(str(row["product_id"]))
    return out


def popular_product_ids(*, limit: int = 12) -> list[str]:
    rows = _fetch_activity_scores(
        recent_hours=POPULAR_WINDOW_HOURS,
        baseline_hours=0,
        min_recent=POPULAR_MIN_WINDOW,
        limit=limit,
    )
    return [str(row["product_id"]) for row in rows]
