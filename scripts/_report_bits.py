from mayabu_db.connection import db_connection

CATS = (
    "laptop","smartphone","television","refrigerator",
    "washing_machine","tws","headphones","camera",
)
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select category, stock_status, count(*)::int n
        from platform_listings
        where category = any(%s) and match_status = 'matched'
        group by 1, 2
        order by 1, 2
        """,
        (list(CATS),),
    )
    print("STOCK")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select category, count(*)::int n
        from platform_listings
        where category in ('accessory','unknown')
           or match_status = 'rejected'
        group by 1
        order by 2 desc
        """
    )
    print("ACCESSORY_OR_REJECTED")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select left(coalesce(last_error,''), 80) err, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion' and status = 'dead'
        group by 1
        order by n desc
        """
    )
    print("DEAD")
    for row in cur.fetchall():
        print(dict(row))
