"""Match listings recovered from unknown using the existing ingestion matcher."""

from __future__ import annotations

import json

from mayabu.domain.matching_golden import score_golden
from mayabu_db.connection import db_connection
from mayabu_db.ingestion import ingest_listing

matched = created = review = failed = 0
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select listing_id, platform, title, listing_url, native_id, current_price, category
        from platform_listings
        where match_status = 'unmatched'
          and product_id is null
          and coalesce(match_evidence->>'auto_resolution','') = 'unknown_recovered'
          and category = any(%s)
        """,
        (["smartphone", "laptop", "television", "refrigerator", "washing_machine", "tws", "headphones", "camera"],),
    )
    rows = list(cur.fetchall())

for row in rows:
    price = float(row["current_price"]) if row["current_price"] is not None else None
    raw = {
        "title": row["title"],
        "url": row["listing_url"],
        "link": row["listing_url"],
        "native_id": row["native_id"],
        "listing_id": row["listing_id"],
        "currentPrice": price,
        "price": price,
        "structured_category": row["category"],
        "category": row["category"],
    }
    try:
        with db_connection() as conn:
            ok, stats = ingest_listing(conn, raw, row["platform"], query=row["category"])
        if not ok:
            failed += 1
        elif stats.products_created:
            created += 1
        elif stats.products_matched:
            matched += 1
        else:
            review += 1
    except Exception as exc:  # noqa: BLE001
        failed += 1
        print("ERR", str(exc)[:180])

golden = score_golden()
print(json.dumps({
    "rows": len(rows),
    "matched": matched,
    "created": created,
    "review_or_unmatched": review,
    "failed": failed,
    "false_exact": golden.get("false_exact_merges") if isinstance(golden, dict) else golden,
}, default=str))
