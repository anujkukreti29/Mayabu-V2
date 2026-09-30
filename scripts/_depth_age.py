from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, left(query, 36) q, metadata->>'start_page' sp,
               now() - locked_at as age, left(coalesce(last_error,''), 80) err
        from scrape_tasks
        where created_by = 'catalog_depth'
          and status in ('pending','running','paused')
        order by locked_at nulls first
        """
    )
    for row in cur.fetchall():
        print(dict(row))
