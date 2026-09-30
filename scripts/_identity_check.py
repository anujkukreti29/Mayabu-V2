"""Identity + index consistency checks for staging catalog."""
from __future__ import annotations

from mayabu_db.connection import db_connection

PUBLIC = [
    "laptop",
    "smartphone",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
]


def main() -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select brand, specs->>'family' as family, specs->>'ram_gb' as ram,
                       specs->>'storage_gb' as storage, count(*)::int as n,
                       array_agg(left(canonical_title, 90) order by canonical_title) as titles
                from product_clusters
                where category = 'smartphone' and status = 'active'
                group by 1, 2, 3, 4
                having count(*) > 1
                order by n desc
                limit 8
                """
            )
            print("phone_dup_keys", cur.fetchall())
            cur.execute(
                """
                select brand, specs->>'family' as family,
                       specs->>'screen_size_inch' as size, count(*)::int as n,
                       array_agg(left(canonical_title, 80) order by canonical_title) as titles
                from product_clusters
                where category = 'television' and status = 'active'
                group by 1, 2, 3
                having count(*) > 1
                order by n desc
                limit 8
                """
            )
            print("tv_dup_keys", cur.fetchall())
            cur.execute(
                "select category, count(*)::int from product_search_documents "
                "group by 1 order by 1"
            )
            print("docs", cur.fetchall())
            cur.execute(
                "select count(*)::int as n from product_clusters "
                "where status = 'active' and category = any(%s)",
                (PUBLIC,),
            )
            eligible = cur.fetchone()["n"]
            cur.execute(
                "select count(*)::int as n from product_search_documents "
                "where category = any(%s)",
                (PUBLIC,),
            )
            indexed = cur.fetchone()["n"]
            print("eligible_vs_indexed", eligible, indexed)
            cur.execute(
                """
                select p.category, count(*)::int as orphans
                from product_clusters p
                left join product_search_documents d on d.product_id = p.id
                where p.status = 'active' and p.category = any(%s) and d.product_id is null
                group by 1
                """,
                (PUBLIC,),
            )
            print("missing_docs", cur.fetchall())


if __name__ == "__main__":
    main()
