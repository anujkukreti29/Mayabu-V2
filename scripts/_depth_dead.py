from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select left(query, 40) q, metadata->>'start_page' start_page,
               left(coalesce(last_error,''), 160) err
        from scrape_tasks
        where created_by = 'catalog_depth' and status = 'dead'
        """
    )
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select name, metadata#>>'{cursor,last_page}' last_page,
               metadata#>>'{cursor,stop_reason}' reason,
               metadata#>>'{cursor,new_ids}' new_ids
        from scheduler_plans
        where platform = 'flipkart'
          and coalesce((metadata#>>'{cursor,last_page}')::int,0) > 8
        order by (metadata#>>'{cursor,last_page}')::int desc
        limit 20
        """
    )
    print("---PAST8---")
    for row in cur.fetchall():
        print(dict(row))
