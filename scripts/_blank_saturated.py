from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select query, coalesce(metadata#>>'{cursor,last_page}','') last_page,
               coalesce(metadata->>'completion','') completion
        from scheduler_plans
        where platform = 'flipkart'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'completion','') = 'saturated'
          and coalesce(metadata#>>'{cursor,stop_reason}','') = ''
        """
    )
    print([dict(r) for r in cur.fetchall()])
    cur.execute("select status, consecutive_failures from platform_health where platform='flipkart'")
    print("health", dict(cur.fetchone() or {}))
