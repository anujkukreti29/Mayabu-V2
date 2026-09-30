from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select query,
               coalesce(metadata->>'completion','') completion,
               coalesce(metadata#>>'{cursor,last_page}','') last_page,
               coalesce(metadata#>>'{cursor,stop_reason}','') stop
        from scheduler_plans
        where platform = 'flipkart'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata#>>'{cursor,stop_reason}','') = 'page_budget'
        """
    )
    print([dict(r) for r in cur.fetchall()])
