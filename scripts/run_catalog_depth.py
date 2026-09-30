"""Depth pass for healthy Flipkart and Reliance discovery.

Continues catalog-expansion plans that previously stopped on the page-8
budget. Natural stops stay finished. Amazon and Croma are not deepened.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from urllib.parse import urlparse

from psycopg.types.json import Jsonb

from mayabu.platforms.coverage import discovery_allowed
from mayabu.scheduler.discovery_cursor import start_page_from_metadata, supports_page_cursor
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu.scrapers.page_saturation import EMERGENCY_PAGE, natural_stop
from mayabu_db.connection import db_connection
from mayabu_db.tasks import create_task

PURPOSE = "catalog_expansion_v1"
CHUNK_PAGES = 8
CHUNK_PRODUCTS = 400
NATURAL = (
    "empty_page",
    "repeated_page",
    "consecutive_no_new",
    "retailer_last_page",
    "emergency_ceiling",
    "end_of_results",
)


def assert_dev_database() -> None:
    parsed = urlparse(os.environ["DATABASE_URL"])
    name = (parsed.path or "").lstrip("/").split("?")[0]
    host = parsed.hostname or ""
    if name != "mayabu" or host not in {"127.0.0.1", "localhost"}:
        raise SystemExit(f"refusing {host}/{name}")


def eligible_plans(platform: str) -> list[dict]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, name, platform, query, metadata, max_pages
            from scheduler_plans
            where enabled
              and task_type = 'discovery'
              and platform = %s
              and coalesce(metadata->>'purpose','') = %s
              and coalesce(metadata->>'completion','') not in ('saturated', 'circuit_blocked')
              and coalesce(metadata#>>'{cursor,stop_reason}','') <> all(%s)
              and coalesce((metadata#>>'{cursor,last_page}')::int, 0) >= 8
              and coalesce((metadata#>>'{cursor,last_page}')::int, 0) < %s
              and not exists (
                select 1 from scrape_tasks t
                where t.idempotency_key = 'discovery:' || scheduler_plans.id::text
                  and t.status in ('pending','running','paused')
              )
            order by name
            """,
            (platform, PURPOSE, list(NATURAL), EMERGENCY_PAGE),
        )
        return list(cur.fetchall())


def materialize(platform: str, limit: int) -> int:
    created = 0
    if not platform_allows_task(platform, "discovery"):
        return 0
    with db_connection() as conn, conn.cursor() as cur:
        for plan in eligible_plans(platform):
            if created >= limit:
                break
            category = str((plan.get("metadata") or {}).get("category") or "")
            if category and not discovery_allowed(platform, category):
                continue
            metadata = plan.get("metadata") or {}
            if natural_stop(str((metadata.get("cursor") or {}).get("stop_reason") or "")):
                continue
            start_page = start_page_from_metadata(metadata) if supports_page_cursor(platform) else 1
            if start_page <= 1 or start_page > EMERGENCY_PAGE:
                continue
            remaining = EMERGENCY_PAGE - start_page + 1
            pages = max(1, min(CHUNK_PAGES, remaining))
            create_task(
                conn,
                platform,
                "discovery",
                query=plan.get("query"),
                priority=70,
                max_pages=pages,
                max_products=CHUNK_PRODUCTS,
                metadata={
                    "scheduler_plan_id": str(plan["id"]),
                    "scheduler_plan_name": plan["name"],
                    "category": category,
                    "purpose": "catalog_depth_v2",
                    "source": "catalog_depth_v2",
                    "task_source": "catalog_depth",
                    "start_page": start_page,
                    "page_cursor": True,
                    "prior_last_page": int((metadata.get("cursor") or {}).get("last_page") or 0),
                },
                idempotency_key=f"discovery:{plan['id']}",
                created_by="catalog_depth",
            )
            cur.execute(
                """
                update scheduler_plans
                set last_materialized_at = now(),
                    max_pages = %s,
                    max_products = %s,
                    updated_at = now()
                where id = %s
                """,
                (pages, CHUNK_PRODUCTS, plan["id"]),
            )
            created += 1
    return created


def pending(platform: str) -> int:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select count(*)::int n
            from scrape_tasks
            where task_type = 'discovery'
              and platform = %s
              and status in ('pending','running','paused')
              and coalesce(metadata->>'purpose','') = 'catalog_depth_v2'
            """,
            (platform,),
        )
        return int(cur.fetchone()["n"] or 0)


def snapshot(platform: str) -> dict:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select coalesce(metadata->>'completion','open') as completion,
                   coalesce(metadata#>>'{cursor,stop_reason}','') as stop_reason,
                   count(*)::int n
            from scheduler_plans
            where platform = %s
              and coalesce(metadata->>'purpose','') = %s
            group by 1, 2
            order by 3 desc
            """,
            (platform, PURPOSE),
        )
        return {
            "eligible": len(eligible_plans(platform)),
            "pending": pending(platform),
            "plans": [dict(row) for row in cur.fetchall()],
        }


def feed(platform: str, *, loops: int) -> None:
    for _ in range(loops):
        active = pending(platform)
        if active < 4:
            materialize(platform, 4 - active)
        state = snapshot(platform)
        print(json.dumps({"platform": platform, **state}), flush=True)
        if state["eligible"] == 0 and state["pending"] == 0:
            print(f"DEPTH_DRAINED {platform}", flush=True)
            return
        time.sleep(25)
    print(f"DEPTH_LOOP_CAP {platform}", flush=True)


def main() -> None:
    assert_dev_database()
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=["flipkart", "reliancedigital"])
    parser.add_argument("--materialize", type=int, default=0)
    parser.add_argument("--feed", action="store_true")
    parser.add_argument("--loops", type=int, default=400)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.report:
        print(json.dumps(snapshot(args.platform), default=str))
        return
    if args.feed:
        feed(args.platform, loops=args.loops)
        return
    created = materialize(args.platform, args.materialize)
    print(json.dumps({"created": created, **snapshot(args.platform)}))


if __name__ == "__main__":
    main()
