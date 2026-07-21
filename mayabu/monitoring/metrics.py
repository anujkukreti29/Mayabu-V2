"""Lightweight DB metrics helpers."""

from __future__ import annotations

from mayabu.db.connection import db_connection


def platform_summary() -> list[dict]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select platform,
                       count(*) as listings,
                       count(*) filter (where current_price is not null) as priced_listings,
                       max(last_successful_refresh_at) as last_refresh
                from platform_listings
                group by platform
                order by platform
                """
            )
            return cur.fetchall()


def live_verification_summary() -> dict:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select status, count(*) as count
                from scrape_tasks
                where task_type = 'verify_listing'
                group by status
                """
            )
            queue = {row["status"]: int(row["count"]) for row in cur.fetchall()}
            cur.execute(
                """
                select platform,
                       count(*) filter (where status = 'verified') as verified,
                       count(*) filter (where status in ('failed','blocked')) as failed,
                       round(avg(duration_ms))::int as avg_duration_ms,
                       sum(request_count) as user_requests,
                       count(*) as scraper_jobs
                from live_verification_events
                where created_at >= now() - interval '24 hours'
                group by platform
                order by platform
                """
            )
            platforms = [dict(row) for row in cur.fetchall()]
    return {
        "queue": queue,
        "active": sum(queue.get(key, 0) for key in ("pending", "running", "paused")),
        "last_24_hours": platforms,
    }
