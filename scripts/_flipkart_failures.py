from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, last_error_code, consecutive_failures, circuit_open_until, last_failure_at
        from platform_health where platform = 'flipkart'
        """
    )
    print("health", dict(cur.fetchone() or {}))
    cur.execute(
        """
        select status, left(query, 40) q, left(coalesce(last_error,''), 80) err, finished_at
        from scrape_tasks
        where platform = 'flipkart' and created_by = 'catalog_depth'
          and status in ('dead','failed')
        order by finished_at desc nulls last
        limit 15
        """
    )
    for row in cur.fetchall():
        print(dict(row))
