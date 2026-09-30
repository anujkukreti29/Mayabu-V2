"""Demote accessory titles wrongly filed under public product categories."""

from __future__ import annotations

from mayabu.db.connection import db_connection
from mayabu.domain.categories.registry import detect_category_from_evidence


def remediate(*, limit: int = 200) -> dict:
    updated = 0
    samples: list[dict] = []
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, product_id, title, category, platform
                from platform_listings
                where match_status = 'matched'
                  and category = any(%s)
                  and title is not null
                order by updated_at desc
                limit %s
                """,
                (["smartphone", "laptop", "television", "camera"], limit * 3),
            )
            rows = [dict(r) for r in cur.fetchall()]
            for row in rows:
                detected = detect_category_from_evidence(title=str(row["title"] or ""))
                if detected != "accessory":
                    continue
                cur.execute(
                    """
                    update platform_listings
                    set category = 'accessory',
                        match_status = 'rejected',
                        updated_at = now()
                    where id = %s
                    """,
                    (row["id"],),
                )
                if row.get("product_id"):
                    cur.execute(
                        """
                        update product_search_documents
                        set category = 'accessory',
                            indexed_at = now()
                        where product_id = %s
                        """,
                        (row["product_id"],),
                    )
                updated += 1
                if len(samples) < 10:
                    samples.append(
                        {
                            "title": (row["title"] or "")[:100],
                            "from": row["category"],
                            "platform": row["platform"],
                        }
                    )
                if updated >= limit:
                    break
    return {"updated": updated, "samples": samples}


if __name__ == "__main__":
    import json

    print(json.dumps(remediate(), indent=2))
