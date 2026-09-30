"""Final catalog-campaign report against the development database mayabu."""

from __future__ import annotations

import json
from collections import Counter

from mayabu.domain.matching_golden import score_golden
from mayabu.search.homepage_discovery import build_homepage_discovery
from mayabu.search.query_parser import parse_query
from mayabu.search.search_repository import search_products
from mayabu_db.connection import db_connection

CATEGORIES = (
    "laptop",
    "smartphone",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
    "camera",
)
QUERIES = (
    "laptop",
    "MacBook",
    "gaming laptop",
    "iPhone",
    "Galaxy",
    "Samsung TV",
    "Sony TV",
    "refrigerator",
    "washing machine",
    "TWS",
    "Sony headphones",
    "camera",
    "Canon",
    "Nikon",
)


def main() -> None:
    golden = score_golden()
    report: dict = {
        "golden": {
            "false_exact_merges": golden["false_exact_merges"],
            "true_exact": golden["true_exact"],
            "sample_count": golden["sample_count"],
            "exact_precision": golden["exact_precision"],
        }
    }
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("select current_database() db, current_setting('port') port")
        ident = dict(cur.fetchone())
        if ident["db"] != "mayabu":
            raise SystemExit(f"refusing {ident['db']}")
        report["database"] = ident

        cur.execute("select count(*)::int n from search_document_dirty")
        report["dirty_search_documents"] = cur.fetchone()["n"]
        cur.execute(
            """
            select count(*)::int n
            from product_search_documents
            where offer_count is distinct from platform_count
            """
        )
        report["offer_count_mismatches"] = cur.fetchone()["n"]
        cur.execute(
            """
            select count(*)::int n from product_clusters
            where status = 'active' and category in ('unknown', 'accessory')
            """
        )
        report["public_unknown_or_accessory"] = cur.fetchone()["n"]

        cur.execute(
            """
            select
              d.category,
              count(*)::int canonical_public,
              count(*) filter (where d.best_price is not null)::int priced,
              count(*) filter (where d.image_url is not null and d.image_url <> '')::int with_image,
              count(*) filter (where d.best_price is null)::int without_price,
              coalesce(sum(d.platform_count), 0)::int public_offers
            from product_search_documents d
            join product_clusters pc on pc.id = d.product_id
            where pc.status = 'active'
              and d.category = any(%s)
            group by 1
            order by 1
            """,
            (list(CATEGORIES),),
        )
        report["category_counts"] = [dict(row) for row in cur.fetchall()]

        cur.execute(
            """
            select category, platform, match_status, stock_status, count(*)::int n
            from platform_listings
            where category = any(%s)
            group by 1, 2, 3, 4
            order by 1, 2, 3, 4
            """,
            (list(CATEGORIES),),
        )
        report["listing_matrix"] = [dict(row) for row in cur.fetchall()]

        cur.execute(
            """
            select category,
              count(*) filter (where platform_count = 1)::int stores_1,
              count(*) filter (where platform_count >= 2)::int stores_2,
              count(*) filter (where platform_count >= 3)::int stores_3,
              count(*) filter (where platform_count >= 4)::int stores_4,
              count(*) filter (where platform_count >= 5)::int stores_5,
              count(*) filter (where platform_count >= 6)::int stores_6
            from product_search_documents
            where category = any(%s)
            group by 1
            order by 1
            """,
            (list(CATEGORIES),),
        )
        report["multi_store"] = [dict(row) for row in cur.fetchall()]

        cur.execute(
            """
            with counts as (
              select product_id, count(*)::int n
              from product_images
              group by 1
            ),
            docs as (
              select d.product_id, d.category
              from product_search_documents d
              where d.category = any(%s)
            )
            select docs.category,
              count(*) filter (where coalesce(counts.n, 0) >= 1)::int ge1,
              count(*) filter (where coalesce(counts.n, 0) >= 2)::int ge2,
              count(*) filter (where coalesce(counts.n, 0) >= 4)::int ge4,
              count(*) filter (where coalesce(counts.n, 0) >= 6)::int ge6,
              percentile_cont(0.5) within group (order by coalesce(counts.n, 0))::float median
            from docs
            left join counts on counts.product_id = docs.product_id
            group by 1
            order by 1
            """,
            (list(CATEGORIES),),
        )
        report["gallery"] = [dict(row) for row in cur.fetchall()]

        cur.execute(
            """
            select match_status, count(*)::int n
            from platform_listings
            where category = any(%s)
            group by 1
            order by 1
            """,
            (list(CATEGORIES),),
        )
        report["match_status"] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select coalesce(match_evidence->>'demote_reason', 'none') reason, count(*)::int n
            from platform_listings
            where match_status = 'needs_review'
            group by 1
            order by n desc
            limit 15
            """
        )
        report["needs_review_reasons"] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select status, task_type, count(*)::int n
            from scrape_tasks
            group by 1, 2
            order by 1, 2
            """
        )
        report["queue"] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select relname, pg_size_pretty(pg_total_relation_size(oid)) size,
                   pg_total_relation_size(oid) bytes
            from pg_class
            where relname in (
              'platform_listings', 'price_observations', 'product_search_documents', 'scrape_tasks'
            )
            order by bytes desc
            """
        )
        report["table_sizes"] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select coalesce(metadata->>'category','?') cat, platform, status, count(*)::int n
            from scrape_tasks
            where created_by = 'catalog_expansion'
            group by 1, 2, 3
            order by 1, 2, 3
            """
        )
        report["campaign_tasks"] = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select coalesce(metadata->>'category','?') cat, platform,
                   count(*) filter (where metadata->>'completion' = 'circuit_blocked')::int blocked,
                   count(*)::int plans
            from scheduler_plans
            where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
            group by 1, 2
            order by 1, 2
            """
        )
        report["plans"] = [dict(row) for row in cur.fetchall()]

    searches = []
    for text in QUERIES:
        parsed = parse_query(text)
        rows = search_products(parsed, limit=5)
        categories = Counter(str(row.get("category") or "") for row in rows)
        searches.append(
            {
                "query": text,
                "detected": parsed.detected_category,
                "hits": len(rows),
                "categories": dict(categories),
                "sample": (rows[0].get("canonical_title") or rows[0].get("title") or "")[:80] if rows else "",
            }
        )
    report["search_qa"] = searches
    home = build_homepage_discovery(limit=6)
    sections = {}
    for key, value in home.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            sections[key] = Counter(str(item.get("category") or "") for item in value)
    report["homepage_sections"] = {k: dict(v) for k, v in sections.items()}

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
