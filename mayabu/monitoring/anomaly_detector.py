"""Batch anomaly checks that can be run from cron or CLI."""

from __future__ import annotations


from mayabu.db.connection import db_connection


def flag_stale_hot_listings(hours: int = 24) -> int:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into anomaly_events(severity, event_type, platform, listing_id, message, evidence)
                select 'medium', 'stale_hot_listing', l.platform, l.id,
                       'High priority listing has not refreshed recently',
                       jsonb_build_object('refresh_priority', l.refresh_priority, 'last_successful_refresh_at', l.last_successful_refresh_at)
                from platform_listings l
                where l.refresh_priority <= 50
                  and (l.last_successful_refresh_at is null or l.last_successful_refresh_at < now() - (%s::int * interval '1 hour'))
                  and not exists (
                    select 1 from anomaly_events a
                    where a.event_type = 'stale_hot_listing' and a.listing_id = l.id and a.status = 'open'
                  )
                """,
                (hours,),
            )
            return cur.rowcount
