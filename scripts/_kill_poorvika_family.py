"""Keep the Poorvika pass on exact model tokens only."""
from mayabu_db.connection import db_connection

SQL = """
update scrape_tasks
set status = 'dead', last_error = 'not_exact_model',
    locked_at = null, locked_by = null, lease_expires_at = null, updated_at = now()
where created_by = 'catalog_overlap'
  and platform = 'poorvika'
  and status = 'pending'
  and (position(' ' in query) > 0 or query ~ 'WHR$')
returning query
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    rows = cur.fetchall()
    print("killed", len(rows))
