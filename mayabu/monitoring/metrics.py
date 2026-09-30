"""DB snapshot helpers and queue lag collectors for operations."""

from __future__ import annotations

from typing import Any

from mayabu.db.connection import db_connection
from mayabu.monitoring import instrumentation as m


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


def collect_queue_lag() -> dict[str, Any]:
    """Return pending/running counts and oldest runnable pending age."""
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) as count from scrape_tasks where status = 'pending'")
            pending = int(cur.fetchone()["count"])
            cur.execute("select count(*) as count from scrape_tasks where status = 'running'")
            running = int(cur.fetchone()["count"])
            cur.execute(
                """
                select extract(epoch from (now() - min(scheduled_at))) as age_seconds
                from scrape_tasks
                where status = 'pending' and scheduled_at <= now()
                """
            )
            age_row = cur.fetchone()
            age = float(age_row["age_seconds"] or 0) if age_row and age_row["age_seconds"] is not None else 0.0
            cur.execute(
                """
                select count(*) as count from scrape_tasks
                where status = 'dead'
                  and updated_at >= now() - interval '24 hours'
                """
            )
            dead_24h = int(cur.fetchone()["count"])
    m.QUEUE_PENDING.set(pending)
    m.QUEUE_RUNNING.set(running)
    m.QUEUE_OLDEST_AGE.set(max(0.0, age))
    return {
        "pending": pending,
        "running": running,
        "oldest_pending_age_seconds": round(age, 1),
        "dead_last_24h": dead_24h,
    }
