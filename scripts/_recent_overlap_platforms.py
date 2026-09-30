from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select platform, metadata->>'category' as category, status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_overlap' and created_at > now() - interval '45 minutes'
        group by 1, 2, 3
        order by 1, 2, 3
        """
    )
    for row in cur.fetchall():
        print(dict(row))
