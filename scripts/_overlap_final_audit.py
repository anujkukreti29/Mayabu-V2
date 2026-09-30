"""Final overlap catalog counts, zero-offer classes, and store-count checks."""
import json
from pathlib import Path

from mayabu.search.index_manager import drain_dirty_search_documents
from mayabu_db.connection import db_connection

CATEGORIES = (
    "television",
    "refrigerator",
    "camera",
    "laptop",
    "smartphone",
    "headphones",
    "tws",
    "washing_machine",
)
BASELINE = json.loads(Path("artifacts/catalog_overlap_v1/baseline.json").read_text(encoding="utf-8"))

drain = drain_dirty_search_documents(limit=5000, strict=False)

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select c.category,
               count(*)::int products,
               count(*) filter (where coalesce(d.platform_count,0) = 0)::int stores_0,
               count(*) filter (where coalesce(d.platform_count,0) = 1)::int single_store,
               count(*) filter (where coalesce(d.platform_count,0) >= 2)::int ge2,
               count(*) filter (where coalesce(d.platform_count,0) >= 3)::int ge3,
               count(*) filter (where coalesce(d.platform_count,0) >= 4)::int ge4,
               count(*) filter (where coalesce(d.platform_count,0) >= 5)::int ge5,
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
        (list(CATEGORIES),),
    )
    categories = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select coalesce(l.stock_status, 'unknown') as stock, count(*)::int n
        from platform_listings l
        join product_clusters c on c.id = l.product_id
        where c.status = 'active' and l.match_status = 'matched'
        group by 1
        order by n desc
        """
    )
    stock = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select c.category,
               count(*) filter (where coalesce(d.platform_count,0) = 0)::int zero_offers,
               count(*) filter (where d.best_price is null or d.best_price <= 0)::int no_price
        from product_clusters c
        left join product_search_documents d on d.product_id = c.id
        where c.status = 'active' and c.category = any(%s)
        group by 1
        order by 1
        """,
        (list(CATEGORIES),),
    )
    zero = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select c.id
        from product_clusters c
        join product_search_documents d on d.product_id = c.id
        join platform_listings l on l.product_id = c.id and l.match_status = 'matched'
        where c.status = 'active' and coalesce(d.platform_count,0) >= 2
        group by c.id, d.platform_count
        having count(distinct l.platform) <> d.platform_count
        limit 20
        """
    )
    mismatches = [str(row["id"]) for row in cur.fetchall()]
    cur.execute(
        """
        select product_id, platform, count(*)::int n
        from platform_listings
        where match_status = 'matched' and product_id is not null
        group by 1, 2
        having count(*) > 1
        limit 20
        """
    )
    dupes = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select count(*)::int n from platform_listings
        where match_status = 'needs_review'
          and created_at > '2026-09-25 08:01:00+00'
        """
    )
    review = cur.fetchone()["n"]
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_overlap'
        group by 1
        """
    )
    queue = {row["status"]: row["n"] for row in cur.fetchall()}

after = {
    "drain": drain,
    "categories": categories,
    "stock": stock,
    "zero_offer": zero,
    "store_count_mismatches": mismatches,
    "duplicate_public_platform_rows": len(dupes),
    "duplicate_samples": [{**row, "product_id": str(row["product_id"])} for row in dupes[:8]],
    "needs_review_since_guard": review,
    "queue": queue,
}
Path("artifacts/catalog_overlap_v1/overlap_after.json").write_text(
    json.dumps(after, indent=2, default=str), encoding="utf-8"
)
print(json.dumps({k: after[k] for k in ("drain", "zero_offer", "store_count_mismatches", "duplicate_public_platform_rows", "needs_review_since_guard", "queue")}, indent=2))
print("---categories---")
for row in categories:
    print(row)
