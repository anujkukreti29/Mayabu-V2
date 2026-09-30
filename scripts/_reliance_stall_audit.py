"""Audit Reliance depth leases and plan cursors without changing them."""
from mayabu.scheduler.platform_health_policy import get_platform_status
from mayabu_db.connection import db_connection

print("health", {k: get_platform_status("reliancedigital")[k] for k in (
    "status", "circuit_open", "circuit_open_until", "consecutive_failures", "allows_discovery"
)})
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where platform = 'reliancedigital' and created_by = 'catalog_depth'
        group by 1 order by 1
        """
    )
    print("depth_tasks", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select status, left(query, 40) q,
               coalesce(metadata->>'start_page','') start_page,
               locked_by, locked_at, lease_expires_at,
               now() - locked_at as age,
               left(coalesce(last_error,''), 100) err
        from scrape_tasks
        where platform = 'reliancedigital'
          and task_type = 'discovery'
          and status in ('pending','running','paused')
        order by locked_at nulls last
        """
    )
    print("inflight")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select status, count(*)::int n,
               count(*) filter (where lease_expires_at < now())::int expired
        from scrape_tasks
        where status = 'running'
        group by 1
        """
    )
    print("running_any", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select coalesce(metadata->>'completion','open') completion,
               coalesce(metadata#>>'{cursor,stop_reason}','') stop,
               count(*)::int n,
               min(coalesce((metadata#>>'{cursor,last_page}')::int,0)) min_page,
               max(coalesce((metadata#>>'{cursor,last_page}')::int,0)) max_page
        from scheduler_plans
        where platform = 'reliancedigital'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        group by 1, 2
        order by n desc
        """
    )
    print("plans")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select query,
               coalesce(metadata->>'completion','') completion,
               coalesce((metadata#>>'{cursor,last_page}')::int,0) last_page,
               coalesce(metadata#>>'{cursor,stop_reason}','') stop
        from scheduler_plans
        where platform = 'reliancedigital'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and (
            coalesce(metadata->>'completion','') not in ('saturated','circuit_blocked')
            or coalesce(metadata#>>'{cursor,stop_reason}','') = ''
          )
        order by last_page desc, query
        limit 40
        """
    )
    print("unfinished_or_blank")
    for row in cur.fetchall():
        print(dict(row))
