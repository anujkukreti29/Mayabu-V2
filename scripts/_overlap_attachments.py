"""List overlap listings that attached to an existing product."""
from mayabu_db.connection import db_connection

SQL = """
select l.platform, l.match_method, l.title, c.category, c.canonical_title, c.id
from platform_listings l
join product_clusters c on c.id = l.product_id
where l.created_at > '2026-09-25 08:01:00+00'
  and l.match_status = 'matched'
  and l.match_method <> 'needs_manual_review'
order by l.created_at
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    rows = cur.fetchall()
    print("matched_new_listings", len(rows))
    for row in rows:
        print(row["category"], row["platform"], row["match_method"])
        print("  hit", (row["title"] or "")[:100])
        print("  product", (row["canonical_title"] or "")[:100])
