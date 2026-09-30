"""Queue exact-model searches on retailers a single-store product does not have.

Bounded batches. Does not search a retailer that already offers the product.
Amazon and Croma are excluded from this batch.
"""

from __future__ import annotations

import argparse
import json

from mayabu.catalog.overlap_queries import _codes, missing_retailers, overlap_query
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu_db.connection import db_connection
from mayabu_db.tasks import create_task

ORDER = (
    "television",
    "refrigerator",
    "camera",
    "laptop",
    "smartphone",
    "headphones",
    "tws",
    "washing_machine",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--category", default="")
    parser.add_argument("--platform", default="", help="Search only this retailer when it is missing")
    args = parser.parse_args()
    healthy = {
        name
        for name in ("reliancedigital", "flipkart", "poorvika", "vijaysales")
        if platform_allows_task(name, "discovery")
    }
    created = 0
    skipped = 0
    by_cat: dict[str, int] = {}
    categories = [args.category] if args.category else list(ORDER)
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select c.id, c.category, c.brand, c.canonical_title, c.specs,
                   array_agg(distinct l.platform) as platforms
            from product_clusters c
            join product_search_documents d on d.product_id = c.id
            join platform_listings l on l.product_id = c.id and l.match_status = 'matched'
            where c.status = 'active'
              and c.category = any(%s)
              and coalesce(d.platform_count, 0) = 1
              and d.best_price is not null
            group by c.id
            """,
            (categories,),
        )
        rows = list(cur.fetchall())
    def _rank(row: dict) -> tuple:
        specs = row["specs"] if isinstance(row["specs"], dict) else {}
        tier = 0 if _codes(specs, row["canonical_title"] or "") else 1
        order = ORDER.index(row["category"]) if row["category"] in ORDER else 99
        return (order, tier)

    rows.sort(key=_rank)
    for row in rows:
        if created >= args.limit:
            break
        specs = row["specs"] if isinstance(row["specs"], dict) else {}
        query = overlap_query(row["category"], row["brand"], row["canonical_title"] or "", specs)
        if not query:
            skipped += 1
            continue
        attached = {str(name) for name in (row["platforms"] or [])}
        missing = missing_retailers(row["category"], attached, healthy=healthy)
        if args.platform:
            missing = [name for name in missing if name == args.platform]
        if not missing:
            skipped += 1
            continue
        platform = missing[0]
        with db_connection() as conn:
            create_task(
                conn,
                platform,
                "discovery",
                query=query,
                priority=90,
                max_pages=2,
                max_products=24,
                metadata={
                    "purpose": "catalog_overlap_v2",
                    "category": row["category"],
                    "anchor_product_id": str(row["id"]),
                    "source": "exact_model_overlap",
                    "start_page": 1,
                },
                idempotency_key=f"overlap:{row['id']}:{platform}",
                created_by="catalog_overlap",
            )
        created += 1
        by_cat[row["category"]] = by_cat.get(row["category"], 0) + 1
    print(json.dumps({"created": created, "skipped_weak": skipped, "by_category": by_cat, "healthy": sorted(healthy)}))


if __name__ == "__main__":
    main()
