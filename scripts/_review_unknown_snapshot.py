from collections import Counter
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select category, coalesce(match_evidence->>'reason', match_evidence->>'conflict', '') as reason, count(*)::int n
        from platform_listings
        where match_status = 'needs_review'
        group by 1, 2
        order by n desc
        limit 40
        """
    )
    print("REVIEW")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute(
        """
        select category, count(*)::int n
        from platform_listings
        where match_status = 'unknown' or category = 'unknown'
        group by 1
        order by n desc
        """
    )
    print("UNKNOWN")
    for row in cur.fetchall():
        print(dict(row))
    cur.execute("select status, consecutive_failures from platform_health where platform = 'flipkart'")
    print("FK", dict(cur.fetchone() or {}))
