"""Deeper laptop campaign snapshot. Dev mayabu only."""

from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute("select current_database() db, inet_server_addr()::text host")
    print("DB", dict(cur.fetchone()))
    cur.execute(
        """
        select platform,
               count(*) filter (where last_materialized_at is null)::int waiting,
               count(*)::int plans,
               max(max_pages) pages,
               max(max_products) products
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'category','') = 'laptop'
        group by 1
        order by 1
        """
    )
    print("PLAN_BUDGETS")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select platform, max_pages, max_products, status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and coalesce(metadata->>'category','') = 'laptop'
        group by 1, 2, 3, 4
        order by 1, 2, 4
        """
    )
    print("TASK_BUDGETS")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select category, platform, match_status, count(*)::int n
        from platform_listings
        where category = 'laptop'
        group by 1, 2, 3
        order by 2, 3
        """
    )
    print("LAPTOP_LISTINGS")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
        group by 1
        order by 1
        """
    )
    print("QUEUE")
    for row in cur.fetchall():
        print(dict(row))
