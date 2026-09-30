"""Three one-page Amazon exact-model queries. No-op if discovery is blocked."""
from mayabu.catalog.overlap_queries import overlap_query
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu_db.connection import db_connection
from mayabu_db.tasks import create_task

if not platform_allows_task("amazon", "discovery"):
    print("amazon_blocked")
    raise SystemExit(0)

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select c.id, c.category, c.brand, c.canonical_title, c.specs
        from product_clusters c
        join product_search_documents d on d.product_id = c.id
        where c.status = 'active'
          and c.category in ('television', 'smartphone', 'laptop')
          and coalesce(d.platform_count, 0) >= 1
          and d.best_price is not null
          and not exists (
            select 1 from platform_listings l
            where l.product_id = c.id and l.platform = 'amazon' and l.match_status = 'matched'
          )
        order by d.best_price desc nulls last
        limit 200
        """
    )
    rows = list(cur.fetchall())

created = []
seen = set()
for row in rows:
    if len(created) >= 3:
        break
    if row["category"] in seen:
        continue
    specs = row["specs"] if isinstance(row["specs"], dict) else {}
    query = overlap_query(row["category"], row["brand"], row["canonical_title"] or "", specs)
    if not query or " " in query:
        continue
    seen.add(row["category"])
    with db_connection() as conn:
        create_task(
            conn,
            "amazon",
            "discovery",
            query=query,
            priority=95,
            max_pages=1,
            max_products=8,
            metadata={
                "purpose": "catalog_overlap_v2",
                "category": row["category"],
                "anchor_product_id": str(row["id"]),
                "source": "amazon_exact_probe",
                "start_page": 1,
            },
            idempotency_key=f"overlap:{row['id']}:amazon",
            created_by="catalog_overlap",
        )
    created.append({"category": row["category"], "query": query})
print({"created": created})
