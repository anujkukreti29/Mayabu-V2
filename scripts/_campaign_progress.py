"""Campaign progress snapshot. Development catalog only."""

from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute("select current_database() db")
    print("DB", cur.fetchone()["db"])
    cur.execute(
        """
        select coalesce(metadata->>'category','?') cat, platform,
               count(*) filter (where last_materialized_at is null)::int waiting,
               count(*) filter (where metadata->>'completion' = 'circuit_blocked')::int blocked,
               count(*)::int plans
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        group by 1, 2
        order by 1, 2
        """
    )
    print("PLANS")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select coalesce(metadata->>'category','?') cat, platform, status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
        group by 1, 2, 3
        order by 1, 2, 3
        """
    )
    print("TASKS")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        group by 1
        order by 1
        """
    )
    print("QUEUE")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select category, count(*)::int products
        from product_clusters
        where status = 'active'
        group by 1
        order by 2 desc
        """
    )
    print("PRODUCTS")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select platform, left(coalesce(query,''), 40) q, left(coalesce(last_error,''), 100) err
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and status in ('dead','failed','blocked')
          and coalesce(metadata->>'category','') in ('smartphone','television')
        order by updated_at desc nulls last
        limit 25
        """
    )
    print("RECENT_PROBLEMS")
    for row in cur.fetchall():
        print(dict(row))
