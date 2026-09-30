from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scrape_tasks
        set status = 'pending', started_at = null, locked_by = null, locked_at = null
        where status = 'running'
        returning id, platform, query
        """
    )
    rows = cur.fetchall()
    print([dict(r) for r in rows])
