"""Mark remaining feature-token smartphone searches as dead."""
from mayabu_db.connection import db_connection

SQL = """
update scrape_tasks
set status = 'dead', last_error = 'weak_model_token',
    locked_at = null, locked_by = null, lease_expires_at = null, updated_at = now()
where created_by = 'catalog_overlap'
  and status = 'pending'
  and (
    query ~ '(MAH|BIT|CORE|1600W)'
    or query ~ '^[0-9]+GB'
  )
returning query
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    print("killed", len(cur.fetchall()))
