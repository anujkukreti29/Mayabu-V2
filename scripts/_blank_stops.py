from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select query,
               coalesce(metadata#>>'{cursor,last_page}','') as last_page,
               coalesce(metadata->>'completion','') as completion,
               coalesce(metadata#>>'{cursor,new_ids}','') as new_ids
        from scheduler_plans
        where platform = 'flipkart'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce((metadata#>>'{cursor,last_page}')::int, 0) > 8
          and coalesce(metadata#>>'{cursor,stop_reason}','') = ''
        order by query
        """
    )
    for row in cur.fetchall():
        print(dict(row))
