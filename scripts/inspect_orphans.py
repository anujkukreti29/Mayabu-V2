from __future__ import annotations

from mayabu_db.connection import db_connection


def main() -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select match_method, match_status, count(*)::int as n
                from platform_listings
                group by 1, 2
                order by n desc
                """
            )
            print("methods", cur.fetchall())
            cur.execute(
                """
                select platform, category,
                       count(*) filter (where product_id is null)::int as orphan,
                       count(*)::int as total
                from platform_listings
                group by 1, 2
                order by 1, 2
                """
            )
            print("orphans", cur.fetchall())
            cur.execute(
                """
                select title, category, match_method, match_evidence, quality_flags
                from platform_listings
                where product_id is null
                limit 8
                """
            )
            for row in cur.fetchall():
                print(
                    "orphan",
                    (row["title"] or "")[:90],
                    row["category"],
                    row["match_method"],
                    row["match_evidence"],
                    row["quality_flags"],
                )


if __name__ == "__main__":
    main()
