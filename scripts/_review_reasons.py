from collections import Counter
from mayabu_db.connection import db_connection

PUBLIC = (
    "laptop", "smartphone", "television", "refrigerator",
    "washing_machine", "tws", "headphones", "camera",
)
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select category, coalesce(match_evidence->>'demote_reason','') reason, count(*)::int n
        from platform_listings
        where match_status = 'needs_review' and category = any(%s)
        group by 1, 2
        order by n desc
        """,
        (list(PUBLIC),),
    )
    print("REVIEW8")
    total = 0
    for row in cur.fetchall():
        total += row["n"]
        print(dict(row))
    print("total", total)
    cur.execute(
        """
        select coalesce(match_status,'') status, count(*)::int n
        from platform_listings
        where category = 'unknown'
        group by 1
        """
    )
    print("UNK", [dict(r) for r in cur.fetchall()])
