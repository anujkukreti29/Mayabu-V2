"""Refresh policy for known platform listings."""

from __future__ import annotations

from typing import Any

from mayabu.db.connection import db_connection


def due_refresh_candidates(limit: int = 100, platform: str | None = None) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select l.*
                from platform_listings l
                left join platform_health ph on ph.platform = l.platform
                where (%s::text is null or l.platform = %s)
                  and coalesce(ph.status, 'healthy') not in ('paused','blocked')
                  and l.listing_url is not null
                  and l.match_status in ('matched','unmatched','needs_review')
                  and not exists (
                    select 1 from scrape_tasks t
                    where t.status in ('pending','running')
                      and t.task_type = 'refresh_listing'
                      and (
                        t.metadata->>'platform_listing_id' = l.id::text
                        or t.url = l.listing_url
                      )
                  )
                  and (
                    l.last_successful_refresh_at is null
                    or l.last_successful_refresh_at < now() - (l.refresh_interval_minutes * interval '1 minute')
                  )
                order by l.refresh_priority asc, l.last_successful_refresh_at asc nulls first, l.updated_at asc
                limit %s
                """,
                (platform, platform, limit),
            )
            return cur.fetchall()
