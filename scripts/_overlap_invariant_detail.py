"""Explain store-count mismatches and count duplicate matched rows."""
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select count(*)::int n from (
          select product_id, platform
          from platform_listings
          where match_status = 'matched' and product_id is not null
          group by 1, 2
          having count(*) > 1
        ) d
        """
    )
    print("duplicate_groups", cur.fetchone()["n"])
    cur.execute(
        """
        select c.category, c.canonical_title, d.platform_count,
               count(distinct l.platform)::int platforms
        from product_clusters c
        join product_search_documents d on d.product_id = c.id
        join platform_listings l on l.product_id = c.id and l.match_status = 'matched'
        where c.id = any(%s::uuid[])
        group by c.id, c.category, c.canonical_title, d.platform_count
        """,
        ([
            "5f7d8c29-d4aa-4a95-99be-1eb87bb87881",
            "6fbf1d20-23d4-48c0-87ac-57be3112fdcf",
            "98ddf632-5b96-44b5-a01a-08bc23708a25",
            "e037938a-b77b-4e3a-adb4-28c00cb2b61e",
        ],),
    )
    for row in cur.fetchall():
        print(row["category"], row["platform_count"], row["platforms"], (row["canonical_title"] or "")[:80])
    cur.execute(
        """
        select l.platform, count(distinct l.product_id)::int products
        from platform_listings l
        join product_clusters c on c.id = l.product_id
        where c.status = 'active' and l.match_status = 'matched' and c.category = any(%s)
        group by 1
        order by products desc
        """,
        (["television","refrigerator","camera","laptop","smartphone","headphones","tws","washing_machine"],),
    )
    print("retailers")
    for row in cur.fetchall():
        print(dict(row))
