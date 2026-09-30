"""Probe Amazon listings and live detail price extraction."""
from __future__ import annotations

import asyncio
import json
import sys

from mayabu.db.connection import db_connection
from mayabu.scrapers.detail import scrape_product_detail


def pick_urls() -> list[dict]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select distinct on (pl.category)
                       pl.platform, pl.category, pl.listing_url, pl.title, pl.current_price
                from platform_listings pl
                where pl.platform = 'amazon'
                  and pl.match_status = 'matched'
                  and pl.category = any(%s)
                  and pl.listing_url ilike '%%amazon.in/%%'
                  and (pl.listing_url ilike '%%/dp/%%' or pl.listing_url ilike '%%/gp/product/%%')
                  and pl.title !~* '(protector|case|cover|tempered|lens protector|charger|cable|stand|mount)'
                order by pl.category, pl.last_successful_refresh_at desc nulls last
                """,
                (["smartphone", "laptop", "television"],),
            )
            return [dict(r) for r in cur.fetchall()]


async def probe(url: str, platform: str = "amazon") -> dict:
    detail = await scrape_product_detail(url, platform=platform, headless=True, debug=False)
    return {
        "status": detail.status,
        "title": (detail.title or "")[:120],
        "price": detail.current_price,
        "mrp": detail.mrp,
        "stock": detail.availability,
        "gallery": len(detail.gallery_urls()),
        "warnings": detail.warnings,
        "category": (detail.specs or {}).get("category"),
    }


async def main() -> None:
    rows = pick_urls()
    print("CATALOG", json.dumps([{k: (v[:80] if k == "listing_url" and isinstance(v, str) else v) for k, v in r.items()} for r in rows], indent=2, default=str))
    results = []
    for row in rows:
        try:
            r = await probe(row["listing_url"])
            r["url"] = row["listing_url"]
            r["catalog_category"] = row["category"]
            results.append(r)
            print("LIVE", json.dumps(r, default=str))
        except Exception as exc:  # noqa: BLE001
            print("ERR", row["category"], str(exc)[:200])
        await asyncio.sleep(1.2)
    json.dump(results, open("artifacts/amazon_price_probe.json", "w", encoding="utf-8"), indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(main())
