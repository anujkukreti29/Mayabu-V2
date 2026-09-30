from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select match_status, count(*)::int n
        from platform_listings
        where category = 'television' and created_at > now() - interval '90 minutes'
        group by 1
        """
    )
    print("created", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select count(*)::int n from product_clusters
        where category = 'television' and created_at > now() - interval '90 minutes'
        """
    )
    print("new_products", cur.fetchone()["n"])
    cur.execute(
        """
        select coalesce(match_evidence->>'demote_reason','') reason, count(*)::int n
        from platform_listings
        where category = 'television' and match_status = 'needs_review'
          and updated_at > now() - interval '90 minutes'
        group by 1 order by n desc limit 12
        """
    )
    print("review")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select left(query, 30) q, platform,
               coalesce(result->>'valid','') valid,
               coalesce(result->>'matched','') matched,
               coalesce(result->>'created','') created,
               coalesce(result->>'review','') review
        from scrape_tasks
        where created_by = 'catalog_overlap' and status = 'completed'
        order by updated_at desc limit 8
        """
    )
    print("results")
    for row in cur.fetchall():
        print(dict(row))
