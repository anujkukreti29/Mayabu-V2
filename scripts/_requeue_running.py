from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scrape_tasks
        set status = 'pending',
            locked_at = null,
            locked_by = null,
            lease_expires_at = null,
            updated_at = now()
        where created_by = 'catalog_expansion'
          and status = 'running'
        returning platform, query
        """
    )
    rows = cur.fetchall()
    print("requeued", len(rows))
    for row in rows:
        print(dict(row))
