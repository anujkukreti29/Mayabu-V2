from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, platform, left(query, 40) q, max_pages, metadata->>'start_page' start_page
        from scrape_tasks
        where coalesce(metadata->>'purpose','') = 'catalog_depth_v2'
        order by created_at desc
        limit 12
        """
    )
    for row in cur.fetchall():
        print(dict(row))
