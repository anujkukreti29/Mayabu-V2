"""See whether overlap created a second matched row for a retailer already on the product."""
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select count(*)::int n
        from platform_listings newer
        where newer.created_at > '2026-09-25 08:01:00+00'
          and newer.match_status = 'matched'
          and newer.product_id is not null
          and exists (
            select 1 from platform_listings older
            where older.product_id = newer.product_id
              and older.platform = newer.platform
              and older.id <> newer.id
              and older.match_status = 'matched'
              and older.created_at < newer.created_at
          )
        """
    )
    print("overlap_duplicate_public_rows", cur.fetchone()["n"])
