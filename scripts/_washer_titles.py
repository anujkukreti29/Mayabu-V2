from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select l.title as hit, c.canonical_title as product
        from platform_listings l
        join product_clusters c on c.id = l.product_id
        where l.match_method = 'anchor_preferred_exact'
          and c.category = 'washing_machine'
          and l.created_at > '2026-09-25 08:01:00+00'
        """
    )
    for row in cur.fetchall():
        print("HIT", row["hit"])
        print("PRODUCT", row["product"])
        print("---")
