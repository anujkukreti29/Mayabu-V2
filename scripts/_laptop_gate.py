"""Laptop campaign integrity gate. Refuses any database other than mayabu."""

import json
from collections import Counter

from mayabu.domain.matching_golden import score_golden
from mayabu.search.index_manager import drain_dirty_search_documents, get_search_index_stats
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute("select current_database() db")
    if cur.fetchone()["db"] != "mayabu":
        raise SystemExit("refusing non-mayabu database")

    golden = score_golden()
    print("GOLDEN", {k: golden.get(k) for k in (
        "false_exact_merges", "true_exact", "needs_review", "pairs", "false_exact"
    ) if k in golden or True})
    print("GOLDEN_KEYS", sorted(golden))

    cur.execute(
        """
        select status, task_type, count(*)::int n
        from scrape_tasks
        group by 1, 2
        order by 1, 2
        """
    )
    print("ALL_QUEUE")
    for row in cur.fetchall():
        print(dict(row))

    cur.execute(
        """
        select platform, status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and coalesce(metadata->>'category','') = 'laptop'
        group by 1, 2
        order by 1, 2
        """
    )
    print("LAPTOP_TASKS")
    for row in cur.fetchall():
        print(dict(row))

    cur.execute(
        """
        select match_status, count(*)::int n
        from platform_listings
        where category = 'laptop'
        group by 1
        order by 1
        """
    )
    print("LAPTOP_MATCH")
    for row in cur.fetchall():
        print(dict(row))

    cur.execute("select count(*)::int n from search_document_dirty")
    print("DIRTY_BEFORE", cur.fetchone()["n"])

stats = get_search_index_stats()
print("SEARCH_STATS", stats)
drained = drain_dirty_search_documents(limit=5000, strict=False)
print("DRAINED", drained)

with db_connection() as conn, conn.cursor() as cur:
    cur.execute("select count(*)::int n from search_document_dirty")
    print("DIRTY_AFTER", cur.fetchone()["n"])
    cur.execute(
        """
        select pc.category, count(*)::int products
        from product_clusters pc
        where pc.status = 'active'
        group by 1
        order by 2 desc
        """
    )
    print("ACTIVE_PRODUCTS")
    for row in cur.fetchall():
        print(dict(row))
