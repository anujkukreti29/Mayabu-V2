from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select platform, query, status, metadata->>'start_page' start_page
        from scrape_tasks
        where created_by = 'catalog_expansion' and status in ('pending','running')
        order by created_at desc
        limit 20
        """
    )
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select platform, count(*)::int n
        from scheduler_plans
        where coalesce(metadata->>'purpose','')='catalog_expansion_v1'
          and coalesce(metadata->>'category','')='laptop'
          and last_materialized_at is null
          and coalesce(metadata->>'completion','') not in ('saturated','circuit_blocked')
        group by 1
        """
    )
    print("due", [dict(row) for row in cur.fetchall()])
