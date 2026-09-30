import json

from mayabu.search.query_parser import parse_query
from mayabu.search.search_repository import search_products
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select coalesce(metadata->>'completion','open') completion, count(*)::int n
        from scheduler_plans
        where platform = 'flipkart' and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        group by 1
        """
    )
    print("FLIPKART", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select coalesce(metadata#>>'{cursor,stop_reason}','') reason, count(*)::int n
        from scheduler_plans
        where platform = 'flipkart' and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        group by 1 order by n desc
        """
    )
    print("STOPS", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select count(*)::int n
        from product_search_documents
        where offer_count is distinct from platform_count
        """
    )
    print("OFFER_MISMATCH", cur.fetchone()["n"])
    cur.execute(
        """
        select category, count(*)::int n
        from platform_listings
        where category = 'unknown'
        group by 1
        """
    )
    print("UNKNOWN", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select count(*)::int n from platform_listings where match_status = 'needs_review'
          and category in ('laptop','smartphone','television','refrigerator','washing_machine','tws','headphones','camera')
        """
    )
    print("REVIEW", cur.fetchone()["n"])

parsed = parse_query("gaming laptop")
rows = search_products(parsed, limit=10)
print("GAMING")
for row in rows:
    print("-", row.get("brand"), "|", (row.get("canonical_title") or "")[:80])
