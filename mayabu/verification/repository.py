"""Persistence helpers for live verification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg import Connection

from mayabu.db.connection import db_connection


def mark_verification_started(conn: Connection, listing_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update platform_listings
            set last_verification_attempt_at = now(), verification_status = 'pending', updated_at = now()
            where id = %s
            """,
            (listing_id,),
        )


def mark_verification_success(
    conn: Connection,
    listing_id: str,
    *,
    source: str,
    cooldown_seconds: int,
    status: str = "verified",
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update platform_listings
            set last_verified_at = now(), verification_status = %s, verification_source = %s,
                consecutive_verification_failures = 0,
                next_allowed_verification_at = now() + make_interval(secs => %s),
                updated_at = now()
            where id = %s
            """,
            (status, source, max(1, cooldown_seconds), listing_id),
        )


def mark_verification_failure(conn: Connection, listing_id: str, *, error: str, base_cooldown_seconds: int, max_cooldown_seconds: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update platform_listings
            set verification_status = case when %s ilike '%%blocked%%' or %s ilike '%%captcha%%' then 'blocked' else 'failed' end,
                consecutive_verification_failures = consecutive_verification_failures + 1,
                next_allowed_verification_at = now() + make_interval(secs => least(%s, %s * power(2, least(consecutive_verification_failures, 8))::int)),
                last_refresh_error = left(%s, 2000), updated_at = now()
            where id = %s
            """,
            (error, error, max(1, max_cooldown_seconds), max(1, base_cooldown_seconds), error, listing_id),
        )


def get_product_verification_status(product_id: str) -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, platform, current_price, current_mrp, stock_status,
                       last_verified_at, last_verification_attempt_at, verification_status,
                       verification_source, next_allowed_verification_at,
                       consecutive_verification_failures
                from platform_listings
                where product_id = %s and match_status = 'matched'
                order by current_price asc nulls last, platform
                """,
                (product_id,),
            )
            rows = [dict(row) for row in cur.fetchall()]
    now = datetime.now(timezone.utc)
    for row in rows:
        verified = row.get("last_verified_at")
        row["age_seconds"] = max(0, int((now - verified).total_seconds())) if verified else None
    return {"product_id": product_id, "offers": rows, "count": len(rows)}


def record_verification_event(
    conn: Connection,
    *,
    task_id: str | None,
    product_id: str | None,
    listing_id: str,
    platform: str,
    status: str,
    request_count: int = 1,
    source: str | None = None,
    old_price: Any = None,
    verified_price: Any = None,
    stock_status: str | None = None,
    duration_ms: int | None = None,
    error_code: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into live_verification_events(
              task_id, product_id, listing_id, platform, status, request_count,
              source, old_price, verified_price, stock_status, duration_ms, error_code
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (task_id, product_id, listing_id, platform, status, max(1, request_count),
             source, old_price, verified_price, stock_status, duration_ms, error_code),
        )
