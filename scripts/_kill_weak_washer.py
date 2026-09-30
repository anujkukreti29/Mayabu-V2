"""Drop washer searches that are spin speed or capacity-only."""
from mayabu_db.connection import db_connection

SQL = """
update scrape_tasks
set status = 'dead', last_error = 'weak_model_token',
    locked_at = null, locked_by = null, lease_expires_at = null, updated_at = now()
where created_by = 'catalog_overlap'
  and metadata->>'category' = 'washing_machine'
  and status = 'pending'
  and (
    query ~ 'RPM$'
    or query ~ 'washing machine$'
    or query ~ '^[0-9]{4,6}$'
  )
returning query
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    rows = cur.fetchall()
    print("killed", len(rows))
