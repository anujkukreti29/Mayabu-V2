from mayabu_db.connection import db_connection

CATEGORY = "smartphone"
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select platform,
               coalesce(metadata->>'completion','') completion,
               count(*)::int n,
               count(*) filter (where last_materialized_at is null)::int due
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'category','') = %s
        group by 1, 2
        order by 1, 2
        """,
        (CATEGORY,),
    )
    print("plans")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select platform, query, status
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and coalesce(metadata->>'category','') = %s
          and created_at > now() - interval '1 hour'
        order by created_at desc
        limit 20
        """,
        (CATEGORY,),
    )
    print("recent_tasks")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select query, platform
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'category','') = %s
          and last_materialized_at is null
          and coalesce(metadata->>'completion','') not in ('saturated','circuit_blocked','limited_budget_held')
        limit 20
        """,
        (CATEGORY,),
    )
    print("still_due", [dict(row) for row in cur.fetchall()])
