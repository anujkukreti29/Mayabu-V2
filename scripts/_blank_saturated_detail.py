from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select query, metadata->'cursor' as cursor, metadata->>'stop_reason' as top_stop
        from scheduler_plans
        where platform = 'flipkart' and query in ('hp omen','dell g15')
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        """
    )
    for row in cur.fetchall():
        print(row["query"], row["top_stop"], row["cursor"])
    cur.execute(
        """
        select query, status, left(coalesce(last_error,''), 60) err,
               coalesce(metadata->>'start_page','') start_page
        from scrape_tasks
        where platform = 'flipkart' and created_by = 'catalog_depth'
          and query in ('hp omen','dell g15')
        order by updated_at desc
        limit 8
        """
    )
    for row in cur.fetchall():
        print(dict(row))
