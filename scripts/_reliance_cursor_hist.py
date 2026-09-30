from collections import Counter
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select coalesce((metadata#>>'{cursor,last_page}')::int,0) last_page,
               coalesce(metadata#>>'{cursor,stop_reason}','') stop,
               count(*)::int n
        from scheduler_plans
        where platform = 'reliancedigital'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        group by 1, 2
        order by 1, 2
        """
    )
    print("cursor")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select left(coalesce(last_error,''), 80) err, status, count(*)::int n
        from scrape_tasks
        where platform = 'reliancedigital' and created_by = 'catalog_depth'
        group by 1, 2
        order by n desc
        limit 20
        """
    )
    print("task_errors")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select left(query, 36) q, status,
               coalesce(metadata->>'start_page','') sp,
               left(coalesce(result->>'status',''), 20) result_status,
               updated_at
        from scrape_tasks
        where platform = 'reliancedigital' and created_by = 'catalog_depth'
        order by updated_at desc
        limit 12
        """
    )
    print("recent")
    for row in cur.fetchall():
        print(dict(row))
