"""Inspect catalog_expansion_v1 plan and public catalog state."""
from mayabu_db.connection import db_connection

CATS = (
    "laptop",
    "smartphone",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
    "camera",
)

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select coalesce(metadata->>'category','') cat,
               platform,
               count(*)::int n,
               count(*) filter (where last_materialized_at is null)::int never_mat,
               count(*) filter (where coalesce(metadata->>'completion','') = 'saturated')::int sat,
               count(*) filter (where coalesce(metadata->>'completion','') = 'circuit_blocked')::int blocked
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        group by 1, 2
        order by 1, 2
        """
    )
    print("plans")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select c.category,
               count(*)::int products,
               count(*) filter (where coalesce(d.platform_count,0) = 1)::int single,
               count(*) filter (where coalesce(d.platform_count,0) >= 2)::int ge2
        from product_clusters c
        left join product_search_documents d on d.product_id = c.id
        where c.status = 'active' and c.category = any(%s)
        group by 1
        order by 1
        """,
        (list(CATS),),
    )
    print("catalog")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where status in ('pending','running')
        group by 1
        """
    )
    print("inflight", [dict(row) for row in cur.fetchall()])
