"""Re-ingest orphan unknown listings after category detection improvements."""

from __future__ import annotations

import json

from mayabu_common import normalize_raw_listing
from mayabu_db.connection import db_connection
from mayabu_db.ingestion import ingest_listing
from mayabu.search.index_manager import refresh_product_search_documents
from mayabu.search.search_repository import reset_search_source_cache
from mayabu.services.variant_groups import refresh_variant_groups


def main() -> None:
    reset_search_source_cache()
    affected: set[str] = set()
    created = matched = skipped = 0
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select listing_id, platform, title, listing_url, native_id,
                       current_price, image_url, category
                from platform_listings
                where product_id is null
                   or category = 'unknown'
                   or match_status = 'needs_review'
                """
            )
            rows = list(cur.fetchall())

    for row in rows:
        price = row["current_price"]
        if price is not None:
            price = float(price)
        raw = {
            "title": row["title"],
            "link": row["listing_url"],
            "url": row["listing_url"],
            "native_id": row["native_id"],
            "currentPrice": price,
            "price": price,
            "image": row["image_url"],
            "listing_id": row["listing_id"],
        }
        listing = normalize_raw_listing(raw, platform_hint=row["platform"], query="")
        if not listing or listing.get("category") in {"unknown", "accessory"}:
            skipped += 1
            continue
        with db_connection() as conn:
            ok, stats = ingest_listing(conn, raw, row["platform"], query=listing.get("category") or "")
            created += stats.products_created
            matched += stats.products_matched
            affected.update(stats.affected_product_ids)
            # commit via connection context if needed
            conn.commit()
        print(
            json.dumps(
                {
                    "title": (row["title"] or "")[:70],
                    "old_category": row["category"],
                    "new_category": listing.get("category"),
                    "ok": ok,
                    "created": stats.products_created,
                    "matched": stats.products_matched,
                }
            )
        )

    if affected:
        refresh_variant_groups(list(affected))
        refresh_product_search_documents(list(affected), strict=False)
    print(json.dumps({"repaired_rows": len(rows), "created": created, "matched": matched, "skipped": skipped, "affected": len(affected)}))


if __name__ == "__main__":
    main()
