"""Admin and monitoring read models."""

from __future__ import annotations

from typing import Any


from mayabu.db.connection import db_connection
from mayabu_common import canonical_platform


def list_tasks(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, platform, task_type, query, url, priority, status, attempts, max_attempts,
                       scheduled_at, locked_at, locked_by, last_error, created_at, updated_at
                from scrape_tasks
                where (%s::text is null or status = %s)
                order by created_at desc
                limit %s
                """,
                (status, status, limit),
            )
            return cur.fetchall()


def list_anomalies(status: str | None = "open", limit: int = 50) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, severity, event_type, platform, product_id, listing_id, run_id,
                       message, evidence, status, created_at, resolved_at
                from anomaly_events
                where (%s::text is null or status = %s)
                order by created_at desc
                limit %s
                """,
                (status, status, limit),
            )
            return cur.fetchall()


def list_review_items(status: str | None = "needs_review", review_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select rq.*,
                       l.platform, l.title as listing_title, l.listing_url,
                       p.canonical_title as candidate_title, p.brand as candidate_brand,
                       sp.canonical_title as source_product_title, sp.brand as source_product_brand
                from review_queue rq
                left join platform_listings l on l.id = rq.listing_id
                left join product_clusters p on p.id = rq.candidate_product_id
                left join product_clusters sp on sp.id = rq.source_product_id
                where (%s::text is null or rq.status = %s)
                  and (%s::text is null or rq.review_type = %s)
                order by rq.created_at desc
                limit %s
                """,
                (status, status, review_type, review_type, limit),
            )
            return cur.fetchall()


def pause_platform(platform: str) -> None:
    platform = canonical_platform(platform)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into platform_health(platform, status, reason, updated_at)
                values (%s, 'paused', 'manual pause', now())
                on conflict (platform) do update set status = 'paused', reason = 'manual pause', updated_at = now()
                """,
                (platform,),
            )


def resume_platform(platform: str) -> None:
    platform = canonical_platform(platform)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into platform_health(platform, status, reason, updated_at)
                values (%s, 'healthy', 'manual resume', now())
                on conflict (platform) do update set status = 'healthy', reason = 'manual resume', updated_at = now()
                """,
                (platform,),
            )
