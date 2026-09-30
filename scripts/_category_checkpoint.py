"""Write a category campaign checkpoint after discovery drains."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mayabu.domain.matching_golden import score_golden
from mayabu.search.index_manager import drain_dirty_search_documents
from mayabu_db.connection import db_connection

CATEGORY = sys.argv[1]
OUT = Path("artifacts/catalog_campaign") / f"{CATEGORY}.json"


def main() -> None:
    drain = drain_dirty_search_documents(limit=5000, strict=False)
    golden = score_golden()
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select
              count(*)::int products,
              count(*) filter (where coalesce(d.platform_count,0)=1)::int single_store,
              count(*) filter (where coalesce(d.platform_count,0)>=2)::int ge2,
              count(*) filter (where coalesce(d.platform_count,0)>=3)::int ge3,
              count(*) filter (where d.best_price is not null and d.best_price > 0)::int priced,
              count(*) filter (
                where coalesce(d.image_url,'') <> ''
                   or exists (select 1 from product_images i where i.product_id = c.id)
              )::int with_image
            from product_clusters c
            left join product_search_documents d on d.product_id = c.id
            where c.status = 'active' and c.category = %s
            """,
            (CATEGORY,),
        )
        catalog = dict(cur.fetchone())
        cur.execute(
            """
            select platform,
                   count(*)::int plans,
                   count(*) filter (where coalesce(metadata->>'completion','')='saturated')::int saturated,
                   count(*) filter (where coalesce(metadata->>'completion','')='circuit_blocked')::int circuit_blocked,
                   count(*) filter (where coalesce(metadata->>'completion','')='limited_budget_held')::int limited
            from scheduler_plans
            where coalesce(metadata->>'purpose','')='catalog_expansion_v1'
              and coalesce(metadata->>'category','')=%s
            group by 1
            order by 1
            """,
            (CATEGORY,),
        )
        plans = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select status, count(*)::int n
            from scrape_tasks
            where created_by = 'catalog_expansion'
              and coalesce(metadata->>'category','') = %s
            group by 1
            """,
            (CATEGORY,),
        )
        tasks = {row["status"]: row["n"] for row in cur.fetchall()}
        cur.execute(
            """
            select l.platform, count(*)::int listings
            from platform_listings l
            join product_clusters c on c.id = l.product_id
            where c.status = 'active' and c.category = %s and l.match_status = 'matched'
            group by 1
            order by listings desc
            """,
            (CATEGORY,),
        )
        retailers = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select count(*)::int n from (
              select product_id, platform
              from platform_listings
              where match_status = 'matched' and product_id is not null
              group by 1, 2 having count(*) > 1
            ) d
            """
        )
        dup_groups = cur.fetchone()["n"]
    report = {
        "category": CATEGORY,
        "catalog": catalog,
        "plans": plans,
        "tasks": tasks,
        "retailers": retailers,
        "drain": drain,
        "false_exact_merges": golden.get("false_exact_merges"),
        "true_exact": golden.get("true_exact"),
        "duplicate_matched_platform_groups": dup_groups,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    if golden.get("false_exact_merges", 0) != 0:
        raise SystemExit("STOP: false exact merges > 0")


if __name__ == "__main__":
    main()
