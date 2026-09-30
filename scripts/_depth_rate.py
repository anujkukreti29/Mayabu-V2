from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where coalesce(metadata->>'purpose','') = 'catalog_depth_v2'
        group by 1
        """
    )
    print("TASKS", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select left(query, 32) q, metadata->>'start_page' start_page,
               result->>'valid' valid, status
        from scrape_tasks
        where coalesce(metadata->>'purpose','') = 'catalog_depth_v2'
          and status = 'completed'
        order by completed_at desc nulls last
        limit 8
        """
    )
    print("RECENT")
    for row in cur.fetchall():
        print(dict(row))
