from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select name, metadata#>>'{cursor,last_page}' last_page,
               metadata#>>'{cursor,stop_reason}' stop_reason,
               metadata#>>'{cursor,new_ids}' new_ids,
               metadata->>'completion' completion
        from scheduler_plans
        where platform = 'flipkart'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata#>>'{cursor,stop_reason}','') <> ''
        order by updated_at desc
        limit 15
        """
    )
    for row in cur.fetchall():
        print(dict(row))
