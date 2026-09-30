from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select coalesce((metadata#>>'{cursor,last_page}')::int, 0) / 8 * 8 as page_band,
               count(*)::int n
        from scheduler_plans
        where platform = 'flipkart'
          and enabled and task_type = 'discovery'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'completion','') not in ('saturated', 'circuit_blocked')
          and coalesce((metadata#>>'{cursor,last_page}')::int, 0) >= 8
          and coalesce((metadata#>>'{cursor,last_page}')::int, 0) < 40
        group by 1
        order by 1
        """
    )
    print("bands", [dict(r) for r in cur.fetchall()])
    cur.execute("select status, consecutive_failures, last_error_code from platform_health where platform='flipkart'")
    print("health", dict(cur.fetchone() or {}))
