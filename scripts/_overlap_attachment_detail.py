"""Show identity evidence for overlap listings matched since the guard."""
from mayabu_db.connection import db_connection

SQL = """
select l.platform, l.title, l.match_evidence, c.canonical_title, c.specs, c.category,
       (select array_agg(distinct p.platform)
        from platform_listings p
        where p.product_id = c.id and p.match_status = 'matched') as platforms
from platform_listings l
join product_clusters c on c.id = l.product_id
where l.created_at > '2026-09-25 08:01:00+00'
  and l.match_method = 'anchor_preferred_exact'
order by l.created_at
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    for row in cur.fetchall():
        specs = row["specs"] if isinstance(row["specs"], dict) else {}
        print("---")
        print(row["category"], row["platforms"])
        print("HIT", row["title"])
        print("PRODUCT", row["canonical_title"])
        print("models", specs.get("model_codes") or specs.get("model_code"))
        print("capacity", specs.get("capacity_kg"), "load", specs.get("load_type"))
