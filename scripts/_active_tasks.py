from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, platform, left(coalesce(query,''), 40) q,
               max_pages, locked_by, locked_at
        from scrape_tasks
        where status in ('pending', 'running')
        order by status, created_at
        """
    )
    print("ACTIVE")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select locked_by, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and status = 'completed'
          and finished_at > now() - interval '20 minutes'
        group by 1
        """
    )
    print("RECENT_WORKERS")
    for row in cur.fetchall():
        print(dict(row))
