"""Enqueue a 4-query, one-page Croma exact-model probe.

Stops being useful if the first task records a challenge: the caller must
not add more. This script only creates the initial four.
"""
from mayabu.catalog.overlap_queries import overlap_query
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu_db.connection import db_connection
from mayabu_db.tasks import create_task

CATEGORIES = ("television", "refrigerator", "smartphone")

if not platform_allows_task("croma", "discovery"):
    print("croma_not_healthy")
    raise SystemExit(0)

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select c.id, c.category, c.brand, c.canonical_title, c.specs
        from product_clusters c
        join product_search_documents d on d.product_id = c.id
        where c.status = 'active'
          and c.category = any(%s)
          and coalesce(d.platform_count, 0) = 1
          and d.best_price is not null
          and not exists (
            select 1 from platform_listings l
            where l.product_id = c.id and l.platform = 'croma' and l.match_status = 'matched'
          )
        order by c.category, d.best_price desc nulls last
        limit 400
        """,
        (list(CATEGORIES),),
    )
    rows = list(cur.fetchall())

created = []
for row in rows:
    if len(created) >= 4:
        break
    specs = row["specs"] if isinstance(row["specs"], dict) else {}
    query = overlap_query(row["category"], row["brand"], row["canonical_title"] or "", specs)
    if not query or " " in query:
        continue
    with db_connection() as conn:
        create_task(
            conn,
            "croma",
            "discovery",
            query=query,
            priority=95,
            max_pages=1,
            max_products=12,
            metadata={
                "purpose": "catalog_overlap_v2",
                "category": row["category"],
                "anchor_product_id": str(row["id"]),
                "source": "croma_exact_probe",
                "start_page": 1,
            },
            idempotency_key=f"overlap:{row['id']}:croma",
            created_by="catalog_overlap",
        )
    created.append({"category": row["category"], "query": query})
print({"created": created})
