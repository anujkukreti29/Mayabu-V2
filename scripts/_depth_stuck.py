from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, left(query, 40) q, metadata->>'start_page' start_page,
               locked_by, locked_at, now() - locked_at as age
        from scrape_tasks
        where coalesce(metadata->>'purpose','') = 'catalog_depth_v2'
          and status in ('pending','running','paused')
        order by status, locked_at
        """
    )
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select worker_id, status, last_heartbeat_at, now() - last_heartbeat_at as age
        from worker_heartbeats
        order by last_heartbeat_at desc
        limit 6
        """
    )
    print("HEART")
    for row in cur.fetchall():
        print(dict(row))
