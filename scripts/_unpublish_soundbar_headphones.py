"""Unpublish soundbars and TVs that were stored as public headphones."""
from psycopg.types.json import Jsonb

from mayabu_db.connection import db_connection

SQL = """
select id, canonical_title
from product_clusters
where category = 'headphones' and status = 'active'
  and canonical_title ~* '(soundbar|sound bar|\\mhw-[qb]|atmos surround|wireless subwoofer|\\d+\\s*cm \\(\\d+ inch\\))'
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    rows = list(cur.fetchall())
    ids = [str(row["id"]) for row in rows]
    for row in rows:
        print((row["canonical_title"] or "")[:90])
    if not ids:
        print("count", 0)
        raise SystemExit(0)
    cur.execute(
        """
        update product_clusters
        set status = 'archived', updated_at = now()
        where id = any(%s::uuid[])
        """,
        (ids,),
    )
    cur.execute(
        """
        update platform_listings
        set match_status = 'rejected',
            product_id = null,
            match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
            updated_at = now()
        where product_id = any(%s::uuid[])
        """,
        (Jsonb({"auto_resolution": "soundbar_not_headphone"}), ids),
    )
    cur.execute(
        "delete from product_search_documents where product_id = any(%s::uuid[])",
        (ids,),
    )
print("count", len(ids))
