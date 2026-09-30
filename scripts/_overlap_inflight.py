"""Print overlap queue counts. Optional category filter as argv[1]."""
from __future__ import annotations

import sys

from mayabu_db.connection import db_connection

CATEGORY = sys.argv[1] if len(sys.argv) > 1 else None


def main() -> None:
    with db_connection() as conn, conn.cursor() as cur:
        if CATEGORY:
            cur.execute(
                """
                select status, count(*)::int n
                from scrape_tasks
                where created_by = 'catalog_overlap' and metadata->>'category' = %s
                group by 1 order by 1
                """,
                (CATEGORY,),
            )
        else:
            cur.execute(
                """
                select status, count(*)::int n
                from scrape_tasks
                where created_by = 'catalog_overlap'
                group by 1 order by 1
                """
            )
        print("tasks", [dict(row) for row in cur.fetchall()])
        cur.execute(
            """
            select count(*)::int n from scrape_tasks
            where created_by = 'catalog_overlap' and status in ('pending','running')
            """
        )
        print("inflight", cur.fetchone()["n"])
        if CATEGORY:
            cur.execute(
                """
                select query, count(*)::int n
                from scrape_tasks
                where created_by = 'catalog_overlap'
                  and metadata->>'category' = %s
                  and status in ('pending','running')
                group by 1
                order by n desc, query
                limit 20
                """,
                (CATEGORY,),
            )
            print("sample", [dict(row) for row in cur.fetchall()])


if __name__ == "__main__":
    main()
