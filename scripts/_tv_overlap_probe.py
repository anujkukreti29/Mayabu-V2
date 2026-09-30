from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select status, left(query, 40) q, left(coalesce(last_error,''), 80) err, scheduled_at > now() as future
        from scrape_tasks
        where created_by = 'catalog_overlap' and status in ('pending','running')
        order by scheduled_at
        """
    )
    print("open")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select l.platform, l.match_status, count(*)::int n,
               count(*) filter (where c.id is not null and coalesce(d.platform_count,0) >= 2)::int on_multi
        from platform_listings l
        left join product_clusters c on c.id = l.product_id
        left join product_search_documents d on d.product_id = c.id
        where l.category = 'television'
          and l.updated_at > now() - interval '90 minutes'
        group by 1, 2
        order by n desc
        """
    )
    print("90m")
    for row in cur.fetchall():
        print(dict(row))
