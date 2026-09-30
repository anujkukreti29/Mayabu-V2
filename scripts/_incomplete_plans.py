"""Inspect incomplete expansion plans and pending discovery tasks."""
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select platform, coalesce(metadata->>'category','') cat,
               coalesce(metadata->>'completion','') completion,
               coalesce(metadata#>>'{cursor,last_page}','') last_page,
               coalesce(metadata#>>'{cursor,stop_reason}','') stop,
               count(*)::int n
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'completion','') not in ('saturated','circuit_blocked')
        group by 1,2,3,4,5
        order by 2,1, n desc
        limit 40
        """
    )
    print("incomplete")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select platform, query, status, created_by, coalesce(metadata->>'purpose','') purpose
        from scrape_tasks
        where status in ('pending','running')
        order by created_at
        limit 30
        """
    )
    print("pending")
    for row in cur.fetchall():
        print(dict(row))
