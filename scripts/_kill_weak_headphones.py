"""Drop headphone searches that are battery-life or button features, not models."""
from mayabu_db.connection import db_connection

SQL = """
update scrape_tasks
set status = 'dead', last_error = 'weak_model_token',
    locked_at = null, locked_by = null, lease_expires_at = null, updated_at = now()
where created_by = 'catalog_overlap' and status = 'pending'
  and query ~ '(HRS|HOURS|BUTTON)'
returning query
"""

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(SQL)
    print("killed", [row["query"] for row in cur.fetchall()])
