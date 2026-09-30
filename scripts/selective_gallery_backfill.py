"""Bounded gallery backfill for high-value laptop / headphones / TWS products.

Prefers Flipkart and Reliance Digital. Skips Croma. Amazon only when explicitly
requested. Same-PDP images only via enrich_listing. Identity hard-conflicts skip
the listing before any gallery write.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from mayabu.catalog.enrichment import enrich_listing
from mayabu.db.connection import db_connection
from mayabu.domain.categories.headphones import HeadphonesAdapter
from mayabu.domain.categories.laptop import LaptopAdapter
from mayabu.domain.categories.tws import TwsAdapter

_ADAPTERS = {
    "laptop": LaptopAdapter(),
    "headphones": HeadphonesAdapter(),
    "tws": TwsAdapter(),
}
_PREFERRED = ("flipkart", "reliancedigital", "vijaysales", "poorvika")
_ACCESSORY = (
    "case",
    "cover",
    "sleeve",
    "bag",
    "mouse",
    "keyboard",
    "charger only",
    "replacement",
    "ear tip",
    "eartip",
    "protective",
    "skin",
    "stand",
)


def _img_count_sql() -> str:
    return """
        select d.product_id::text as product_id,
               d.category,
               d.canonical_title,
               d.platform_count,
               d.specs,
               coalesce(g.n, 0)::int as imgs
        from product_search_documents d
        left join (
          select product_id, count(*)::int as n
          from product_images
          where active
          group by product_id
        ) g on g.product_id = d.product_id
        where d.category = %s
          and coalesce(g.n, 0) < 2
        order by coalesce(d.platform_count, 0) desc,
                 d.best_price asc nulls last
        limit %s
    """


def _listings(product_id: str) -> list[dict]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id::text as id, platform, listing_url, title, specs, product_id::text as product_id,
                   category, match_status,
                   coalesce(match_evidence->>'listing_role','primary') as listing_role
            from platform_listings
            where product_id = %s::uuid
              and match_status = 'matched'
              and listing_url is not null
              and coalesce(match_evidence->>'listing_role','primary') <> 'alias'
            """,
            (product_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def _safe(category: str, product_specs: dict, listing: dict) -> tuple[bool, list[str]]:
    adapter = _ADAPTERS[category]
    title = listing.get("title") or ""
    low = title.lower()
    if any(tok in low for tok in _ACCESSORY):
        return False, ["accessory_title"]
    extracted = adapter.extract_specs(title)
    hard = adapter.hard_conflicts(product_specs or {}, extracted)
    return (not hard), hard


def select_targets(category: str, *, limit: int, scan: int = 40) -> list[dict]:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(_img_count_sql(), (category, scan))
        products = [dict(r) for r in cur.fetchall()]
    chosen: list[dict] = []
    for product in products:
        if len(chosen) >= limit:
            break
        specs = product["specs"] if isinstance(product.get("specs"), dict) else {}
        listings = _listings(product["product_id"])
        ranked = sorted(
            listings,
            key=lambda row: (
                0 if row["platform"] in _PREFERRED else 1,
                _PREFERRED.index(row["platform"]) if row["platform"] in _PREFERRED else 99,
            ),
        )
        for listing in ranked:
            if listing["platform"] == "croma":
                continue
            if listing["platform"] == "amazon":
                continue
            ok, reasons = _safe(category, specs, listing)
            if not ok:
                continue
            chosen.append(
                {
                    "product_id": product["product_id"],
                    "category": category,
                    "title": (product.get("canonical_title") or "")[:120],
                    "platform_count": product.get("platform_count"),
                    "imgs_before": product.get("imgs"),
                    "listing": listing,
                }
            )
            break
    return chosen


async def run(categories: list[str], per_category: int) -> dict:
    report: dict = {"targets": [], "outcomes": [], "skipped_identity": 0}
    for category in categories:
        targets = select_targets(category, limit=per_category)
        report["targets"].extend(
            {
                "product_id": t["product_id"],
                "category": t["category"],
                "platform": t["listing"]["platform"],
                "title": t["title"],
                "stores": t["platform_count"],
                "imgs_before": t["imgs_before"],
            }
            for t in targets
        )
        for target in targets:
            listing = target["listing"]
            try:
                result = await enrich_listing(listing, headless=True)
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "error": str(exc)[:240], "platform": listing["platform"]}
            report["outcomes"].append(
                {
                    "product_id": target["product_id"],
                    "category": category,
                    "platform": listing["platform"],
                    "ok": bool(result.get("ok")),
                    "gallery_written": result.get("gallery_written"),
                    "gallery_count": result.get("gallery_count"),
                    "conflicts": result.get("conflicts"),
                    "status": result.get("status"),
                    "error": result.get("error"),
                }
            )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--categories", default="laptop,headphones,tws")
    parser.add_argument("--per-category", type=int, default=4)
    parser.add_argument("--out", default="artifacts/selective_gallery_backfill.json")
    args = parser.parse_args()
    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    report = asyncio.run(run(cats, max(1, min(args.per_category, 8))))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(json.dumps({"targets": len(report["targets"]), "ok": sum(1 for o in report["outcomes"] if o["ok"]), "outcomes": report["outcomes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
