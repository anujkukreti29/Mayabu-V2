"""Final multi-category catalog campaign summary for mayabu."""
from __future__ import annotations

import json
from pathlib import Path

from mayabu.domain.matching_golden import score_golden
from mayabu.search.index_manager import drain_dirty_search_documents
from mayabu.search.query_parser import parse_query
from mayabu.search.search_repository import search_products
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu_db.connection import db_connection

CATS = (
    "laptop",
    "smartphone",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
    "camera",
)
SEARCH_QA = (
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

drain = drain_dirty_search_documents(limit=5000, strict=False)
golden = score_golden()

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select c.category,
               count(*)::int products,
               count(*) filter (where coalesce(d.platform_count,0)=0)::int stores_0,
               count(*) filter (where coalesce(d.platform_count,0)=1)::int single_store,
               count(*) filter (where coalesce(d.platform_count,0)>=2)::int ge2,
               count(*) filter (where coalesce(d.platform_count,0)>=3)::int ge3,
               count(*) filter (where coalesce(d.platform_count,0)>=4)::int ge4,
               count(*) filter (where coalesce(d.platform_count,0)>=5)::int ge5,
               count(*) filter (where d.best_price is not null and d.best_price > 0)::int priced,
               count(*) filter (
                 where coalesce(d.image_url,'') <> ''
                    or exists (select 1 from product_images i where i.product_id = c.id)
               )::int with_image
        from product_clusters c
        left join product_search_documents d on d.product_id = c.id
        where c.status = 'active' and c.category = any(%s)
        group by 1
        order by 1
        """,
        (list(CATS),),
    )
    categories = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select c.category, l.platform, count(*)::int listings
        from platform_listings l
        join product_clusters c on c.id = l.product_id
        where c.status = 'active' and c.category = any(%s) and l.match_status = 'matched'
        group by 1, 2
        order by 1, listings desc
        """,
        (list(CATS),),
    )
    matrix = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
        group by 1
        """
    )
    queue = {row["status"]: row["n"] for row in cur.fetchall()}
    cur.execute(
        """
        select count(*)::int n from product_clusters
        where status = 'active' and category = 'unknown'
        """
    )
    unknown_public = cur.fetchone()["n"]
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
    cur.execute(
        """
        select coalesce(l.stock_status, 'unknown') stock, count(*)::int n
        from platform_listings l
        join product_clusters c on c.id = l.product_id
        where c.status = 'active' and l.match_status = 'matched' and c.category = any(%s)
        group by 1 order by n desc
        """,
        (list(CATS),),
    )
    stock = [dict(row) for row in cur.fetchall()]
    cur.execute("select count(*)::int n from scrape_tasks where status in ('pending','running')")
    inflight = cur.fetchone()["n"]

health = {
    name: platform_allows_task(name, "discovery")
    for name in ("flipkart", "reliancedigital", "vijaysales", "poorvika", "amazon", "croma")
}

search_qa = []
for query in SEARCH_QA:
    rows = search_products(parse_query(query), limit=5)
    search_qa.append(
        {
            "query": query,
            "hits": len(rows),
            "top": [(row.get("canonical_title") or "")[:80] for row in rows[:3]],
        }
    )

report = {
    "database": {"host": "127.0.0.1", "name": "mayabu", "environment": "development"},
    "drain": drain,
    "categories": categories,
    "retailer_matrix": matrix,
    "stock": stock,
    "queue": queue,
    "inflight_any": inflight,
    "unknown_public": unknown_public,
    "duplicate_matched_platform_groups": dup_groups,
    "false_exact_merges": golden.get("false_exact_merges"),
    "true_exact": golden.get("true_exact"),
    "retailer_health_allows_discovery": health,
    "search_qa": search_qa,
}
out = Path("artifacts/catalog_campaign/final_catalog.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
print(json.dumps({k: report[k] for k in ("drain", "false_exact_merges", "unknown_public", "inflight_any", "queue", "categories")}, indent=2, default=str))
