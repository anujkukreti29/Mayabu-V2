"""Write one overlap category checkpoint from the current queue and store counts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mayabu_db.connection import db_connection

CATEGORY = sys.argv[1]
OUT = Path("artifacts/catalog_overlap_v1") / f"{CATEGORY if CATEGORY != 'washing_machine' else 'washing_machine'}.json"
NAME = {
    "washing_machine": "washing_machine",
}.get(CATEGORY, CATEGORY)


def main() -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select status, count(*)::int n
            from scrape_tasks
            where created_by = 'catalog_overlap'
              and coalesce(metadata->>'category','') = %s
            group by 1
            """,
            (CATEGORY,),
        )
        tasks = {row["status"]: row["n"] for row in cur.fetchall()}
        cur.execute(
            """
            select
              count(*) filter (where coalesce(d.platform_count,0) = 1)::int single_store,
              count(*) filter (where coalesce(d.platform_count,0) >= 2)::int ge2,
              count(*) filter (where coalesce(d.platform_count,0) >= 3)::int ge3,
              count(*) filter (where coalesce(d.platform_count,0) >= 4)::int ge4,
              count(*) filter (where coalesce(d.platform_count,0) >= 5)::int ge5
            from product_clusters c
            left join product_search_documents d on d.product_id = c.id
            where c.status = 'active' and c.category = %s
            """,
            (CATEGORY,),
        )
        stores = dict(cur.fetchone())
        cur.execute(
            """
            select count(*)::int n from product_clusters
            where category = %s and created_at > now() - interval '6 hours'
            """,
            (CATEGORY,),
        )
        created = cur.fetchone()["n"]
    report = {
        "category": CATEGORY,
        "tasks": tasks,
        "stores_now": stores,
        "products_created_recently": created,
        "note": "Exact attachment requires the anchor matcher. Unmatched overlap hits are review, not new products, after the overlap create guard.",
    }
    path = OUT.parent / f"{NAME}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
