from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Any

from mayabu_common import write_json
from mayabu_db.connection import db_connection


def clean(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def export_products(limit: int = 500) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.*, b.best_price, b.best_platform, b.platform_count, b.last_seen_at
                from product_clusters p
                left join current_product_best_prices b on b.product_id = p.id
                where p.status = 'active'
                order by b.best_price asc nulls last, p.updated_at desc
                limit %s
                """,
                (limit,),
            )
            products = cur.fetchall()
            output = []
            for p in products:
                product_id = p["id"]
                cur.execute(
                    """
                    select * from platform_listings
                    where product_id = %s and match_status = 'matched'
                    order by current_price asc nulls last, platform asc
                    """,
                    (product_id,),
                )
                listings = cur.fetchall()
                cur.execute(
                    """
                    select date, best_price, best_platform, amazon_price, flipkart_price, croma_price, reliancedigital_price, all_time_low_so_far
                    from daily_product_prices
                    where product_id = %s
                    order by date asc
                    """,
                    (product_id,),
                )
                history = cur.fetchall()
                platforms = {}
                source_listings = []
                for listing in listings:
                    block = {
                        "listing_id": listing["listing_id"],
                        "price": listing["current_price"],
                        "mrp": listing["current_mrp"],
                        "discount_pct": listing["current_discount_pct"],
                        "url": listing["listing_url"],
                        "image": listing["image_url"],
                        "last_updated": listing["last_seen_at"],
                        "stock_status": listing["stock_status"],
                        "match_confidence": listing["match_confidence"],
                    }
                    old = platforms.get(listing["platform"])
                    if old is None or (block["price"] is not None and (old.get("price") is None or block["price"] < old["price"])):
                        platforms[listing["platform"]] = block
                    source_listings.append(block | {"platform": listing["platform"], "title": listing["title"]})
                output.append(clean({
                    "id": str(product_id),
                    "title": p["canonical_title"],
                    "category": p["category"],
                    "brand": p["brand"],
                    "specs": p["specs"],
                    "best_price": p.get("best_price"),
                    "best_platform": p.get("best_platform"),
                    "platform_count": p.get("platform_count"),
                    "platforms": platforms,
                    "best_price_history": history,
                    "source_listings": source_listings,
                }))
            return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Mayabu frontend-style JSON from PostgreSQL")
    parser.add_argument("--output", default="artifacts/exports/frontend_products.json")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    products = export_products(args.limit)
    write_json(args.output, {"schema_version": "mayabu.frontend.v3", "count": len(products), "products": products})
    print(f"Exported {len(products)} products -> {args.output}")


if __name__ == "__main__":
    main()
