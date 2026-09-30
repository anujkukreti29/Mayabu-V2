"""Snapshot review, unknown, zero-offer, and health before the depth pass."""

from __future__ import annotations

import json

from mayabu_db.connection import db_connection

CATS = (
    "laptop", "smartphone", "television", "refrigerator",
    "washing_machine", "tws", "headphones", "camera",
)


def main() -> None:
    out: dict = {}
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select platform, status, consecutive_failures, circuit_open_until
            from platform_health
            order by platform
            """
        )
        out["health"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            select platform,
                   count(*) filter (where coalesce((metadata#>>'{cursor,last_page}')::int,0) >= 8) as at_least_8,
                   count(*) filter (where coalesce(metadata->>'completion','') = 'circuit_blocked') as blocked,
                   count(*)::int n
            from scheduler_plans
            where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
            group by platform
            order by platform
            """
        )
        out["plans"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            select coalesce(match_evidence->>'demote_reason', match_status) as reason, count(*)::int n
            from platform_listings
            where match_status = 'needs_review'
              and category = any(%s)
            group by 1
            order by n desc
            """,
            (list(CATS),),
        )
        out["review"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            select platform, count(*)::int n
            from platform_listings
            where category = 'unknown'
            group by 1
            order by n desc
            """
        )
        out["unknown_platforms"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            select left(title, 90) as title, platform
            from platform_listings
            where category = 'unknown'
            order by random()
            limit 25
            """
        )
        out["unknown_sample"] = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            select c.category, count(*)::int n
            from product_clusters c
            left join product_search_documents d on d.product_id = c.id
            where c.status = 'active'
              and c.category = any(%s)
              and coalesce(d.offer_count, 0) = 0
            group by 1
            order by 1
            """,
            (list(CATS),),
        )
        out["zero_offer"] = [dict(r) for r in cur.fetchall()]
    print(json.dumps(out, default=str, indent=2))


if __name__ == "__main__":
    main()
