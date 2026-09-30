from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_overlap'
        group by 1 order by 1
        """
    )
    print("tasks", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select coalesce(match_evidence->>'method','') method,
               match_status,
               count(*)::int n
        from platform_listings
        where coalesce(match_evidence->>'anchor_product_id','') <> ''
           or coalesce(match_evidence->>'method','') = 'anchor_preferred_exact'
        group by 1, 2
        order by n desc
        """
    )
    print("anchor")
    for row in cur.fetchall():
        print(dict(row))
