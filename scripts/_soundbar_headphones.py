"""Count public headphones whose titles are soundbars or speakers."""
from mayabu_db.connection import db_connection

SQL = """
select canonical_title, id
from product_clusters
where category = 'headphones' and status = 'active'
  and canonical_title ~* '(soundbar|sound bar|\\mhw-[qb]|atmos surround|wireless subwoofer)'
order by canonical_title
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    rows = cur.fetchall()
    print("n", len(rows))
    for row in rows:
        print(row["canonical_title"][:110])
