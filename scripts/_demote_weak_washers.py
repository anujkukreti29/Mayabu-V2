"""Demote washer overlap attachments that have no exact model code."""
from psycopg.types.json import Jsonb

from mayabu.search.index_manager import refresh_product_search_documents
from mayabu_db.connection import db_connection

SQL = """
select l.id, l.product_id, l.title
from platform_listings l
join product_clusters c on c.id = l.product_id
where l.match_method = 'anchor_preferred_exact'
  and c.category = 'washing_machine'
  and l.created_at > '2026-09-25 08:01:00+00'
  and coalesce(c.specs->>'model_code','') = ''
  and coalesce(c.specs->'model_codes','[]'::jsonb) = '[]'::jsonb
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    rows = list(cur.fetchall())
    ids = [str(row["id"]) for row in rows]
    products = [str(row["product_id"]) for row in rows]
    for row in rows:
        print("demote", row["title"][:80])
    if ids:
        cur.execute(
            """
            update platform_listings
            set match_status = 'needs_review',
                product_id = null,
                match_method = 'needs_manual_review',
                match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                updated_at = now()
            where id = any(%s::uuid[])
            """,
            (Jsonb({"reason": "washer_without_model_code"}), ids),
        )
print("demoted", len(ids))
if products:
    print(refresh_product_search_documents(products, strict=False))
