"""Bounded catalog freshness for internal health/metrics only."""

from __future__ import annotations

import logging
from typing import Any

from mayabu.db.connection import db_connection

logger = logging.getLogger(__name__)


def catalog_freshness() -> dict[str, Any]:
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select l.platform,
                           coalesce(l.category, 'unknown') as category,
                           count(*)::int as eligible,
                           count(*) filter (
                             where l.last_successful_refresh_at >= now() - interval '1 hour'
                           )::int as within_1h,
                           count(*) filter (
                             where l.last_successful_refresh_at >= now() - interval '6 hours'
                           )::int as within_6h,
                           count(*) filter (
                             where l.last_successful_refresh_at >= now() - interval '24 hours'
                           )::int as within_24h,
                           count(*) filter (
                             where l.last_successful_refresh_at is null
                                or l.last_successful_refresh_at < now() - interval '24 hours'
                           )::int as stale_over_24h
                    from platform_listings l
                    where l.listing_url is not null
                      and l.match_status in ('matched','unmatched','needs_review')
                    group by l.platform, coalesce(l.category, 'unknown')
                    order by l.platform, category
                    """
                )
                rows = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    select
                      count(*) filter (where match_status = 'needs_review')::int as unmatched_review,
                      count(*) filter (where match_status = 'unmatched')::int as unmatched,
                      count(*) filter (where match_status = 'conflict')::int as conflict,
                      count(*) filter (where match_status = 'matched')::int as matched
                    from platform_listings
                    """
                )
                matching = dict(cur.fetchone() or {})
    except Exception as exc:
        logger.debug("catalog_freshness_unavailable", extra={"error": str(exc)[:200]})
        return {"rows": [], "matching": {}}
    return {"rows": rows, "matching": matching}


def retailer_health_snapshot() -> list[dict[str, Any]]:
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select platform, status, consecutive_failures,
                           reason, last_success_at, last_failure_at,
                           circuit_open_until
                    from platform_health
                    order by platform
                    """
                )
                return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        logger.debug("retailer_health_unavailable", extra={"error": str(exc)[:200]})
        return []
