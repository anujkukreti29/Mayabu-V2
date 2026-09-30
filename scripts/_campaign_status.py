"""One-shot catalog expansion queue and listing snapshot. Dev mayabu only."""

from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select platform, status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
        group by 1, 2
        order by 1, 2
        """
    )
    print("TASKS")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select platform, left(coalesce(last_error,''), 120) err, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and status in ('failed','blocked','paused')
        group by 1, 2
        order by n desc
        limit 20
        """
    )
    print("FAILURES")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select platform, status, left(coalesce(query,''), 60) query,
               left(coalesce(last_error,''), 180) err
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and status in ('failed','blocked','paused','dead')
        order by updated_at desc nulls last
        limit 15
        """
    )
    print("PROBLEM_TASKS")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select category, platform, count(*)::int listings
        from platform_listings
        where created_at > now() - interval '3 hours'
        group by 1, 2
        order by 1, 2
        """
    )
    print("NEW_LISTINGS_3H")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select
          count(*) filter (where last_materialized_at is null)::int unmaterialized,
          count(*)::int plans
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'category','') = 'laptop'
        """
    )
    print("PLANS", dict(cur.fetchone()))
