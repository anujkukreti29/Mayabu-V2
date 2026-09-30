"""Confirm laptop splits and mark laptop search documents dirty."""

import json

from mayabu.domain.matching_golden import score_golden
from mayabu_db.connection import db_connection

golden = score_golden()
with db_connection() as conn, conn.cursor() as cur:
    cur.execute("select current_database() db")
    if cur.fetchone()["db"] != "mayabu":
        raise SystemExit("refusing non-mayabu database")
    cur.execute(
        """
        select match_status, count(*)::int n
        from platform_listings
        where category = 'laptop'
        group by 1
        order by 1
        """
    )
    print("MATCH", [dict(r) for r in cur.fetchall()])
    cur.execute(
        """
        select count(*)::int n
        from platform_listings
        where match_evidence->>'demote_reason' = 'laptop_config_hard_conflict'
        """
    )
    print("DEMOTED", cur.fetchone()["n"])
    cur.execute(
        """
        insert into search_document_dirty(product_id, reason, dirty_at, attempts, last_error)
        select product_id, 'laptop_config_split', now(), 0, null
        from product_search_documents
        where category = 'laptop'
        on conflict (product_id) do update set
          reason = excluded.reason,
          dirty_at = now(),
          claimed_at = null,
          claimed_by = null,
          last_error = null
        """
    )
    print("DIRTY_MARKED", cur.rowcount)
print("GOLDEN", golden["false_exact_merges"], golden["true_exact"])
