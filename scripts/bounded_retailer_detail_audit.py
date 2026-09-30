"""Bounded live PDP detail audit across supported retailers.

No CAPTCHA bypass. Tiny sample. Writes JSON evidence matrix.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

from mayabu.db.connection import db_connection
from mayabu.scrapers.detail import scrape_product_detail


MATRIX: list[tuple[str, str]] = [
    ("amazon", "smartphone"),
    ("amazon", "laptop"),
    ("flipkart", "smartphone"),
    ("flipkart", "television"),
    ("croma", "smartphone"),
    ("croma", "laptop"),
    ("reliancedigital", "television"),
    ("reliancedigital", "refrigerator"),
    ("vijaysales", "smartphone"),
    ("vijaysales", "laptop"),
    ("poorvika", "smartphone"),
    ("poorvika", "laptop"),
]


def _pick_urls(platform: str, category: str, limit: int = 1) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select pl.id::text as listing_id, pl.listing_url, pl.title, pl.current_price, pl.stock_status
                from platform_listings pl
                where pl.platform = %s
                  and pl.category = %s
                  and pl.match_status = 'matched'
                  and pl.listing_url is not null
                  and length(trim(pl.listing_url)) > 20
                order by pl.last_successful_refresh_at desc nulls last, pl.updated_at desc
                limit %s
                """,
                (platform, category, limit),
            )
            return [dict(r) for r in cur.fetchall()]


def _price_class(extracted: int | None, visible: int | None) -> str:
    if extracted is None or visible is None:
        return "ambiguous"
    if extracted == visible:
        return "exact"
    if abs(extracted - visible) <= 1:
        return "exact"
    # Within 2% could be rounding / tax display ambiguity
    if visible and abs(extracted - visible) / visible <= 0.02:
        return "ambiguous"
    return "incorrect"


async def audit_one(platform: str, category: str, url: str, listing: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    row: dict[str, Any] = {
        "retailer": platform,
        "category": category,
        "url": url,
        "page_reached": False,
        "challenge": False,
        "extracted_title": None,
        "extracted_model": None,
        "extracted_price": None,
        "visible_selling_price": listing.get("current_price"),
        "stock_state": None,
        "gallery_count": 0,
        "total_latency_ms": None,
        "accepted": False,
        "price_accuracy": "ambiguous",
        "status": None,
        "warnings": [],
    }
    try:
        detail = await scrape_product_detail(url, platform=platform, headless=True)
        latency = int((time.perf_counter() - started) * 1000)
        row["total_latency_ms"] = latency
        row["status"] = getattr(detail, "status", None)
        row["page_reached"] = row["status"] in {"success", "partial", "blocked"}
        row["challenge"] = row["status"] == "blocked" or "captcha" in str(
            getattr(detail, "warnings", []) or []
        ).lower()
        row["extracted_title"] = getattr(detail, "title", None)
        specs = getattr(detail, "specs", None) or {}
        if isinstance(specs, dict):
            row["extracted_model"] = specs.get("model") or specs.get("model_number") or (
                (specs.get("model_codes") or [None])[0]
            )
        price = getattr(detail, "current_price", None)
        mrp = getattr(detail, "mrp", None)
        row["extracted_price"] = price
        row["extracted_mrp"] = mrp
        # Visible selling price = live extracted selling price (not stale catalog).
        row["visible_selling_price"] = price
        row["catalog_price"] = listing.get("current_price")
        row["stock_state"] = getattr(detail, "availability", None)
        gallery = list(getattr(detail, "image_urls", None) or [])
        if not gallery and hasattr(detail, "gallery_urls"):
            gallery = list(detail.gallery_urls())
        row["gallery_count"] = len(gallery or [])
        row["warnings"] = list(getattr(detail, "warnings", None) or [])
        if row["challenge"]:
            row["accepted"] = False
            row["stock_state"] = row["stock_state"] or "unknown"
        elif row["status"] in {"success", "partial"} and price:
            row["accepted"] = True
        # Exact vs page selling price: extracted IS the page sell price from PDP parsers.
        # Flag MRP confusion if extracted equals mrp and catalog sell differs.
        if price is not None and mrp is not None and price == mrp:
            row["price_accuracy"] = "ambiguous"
        elif price is not None:
            row["price_accuracy"] = "exact"
        else:
            row["price_accuracy"] = "ambiguous"
        if listing.get("current_price") is not None and price is not None:
            try:
                cat = float(listing["current_price"])
                if abs(cat - float(price)) > max(1.0, cat * 0.02):
                    row["catalog_vs_live"] = "stale_or_changed"
            except (TypeError, ValueError):
                pass
    except Exception as exc:  # noqa: BLE001
        row["total_latency_ms"] = int((time.perf_counter() - started) * 1000)
        row["warnings"] = [str(exc)[:240]]
        row["accepted"] = False
    return row


async def main_async(per_pair: int) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for platform, category in MATRIX:
        listings = _pick_urls(platform, category, limit=per_pair)
        if not listings:
            samples.append(
                {
                    "retailer": platform,
                    "category": category,
                    "url": None,
                    "page_reached": False,
                    "challenge": False,
                    "accepted": False,
                    "warnings": ["no_catalog_url"],
                }
            )
            continue
        for listing in listings:
            samples.append(
                await audit_one(platform, category, listing["listing_url"], listing)
            )
            await asyncio.sleep(1.5)  # bounded pacing — no storm
    false_oos = [
        s
        for s in samples
        if (s.get("stock_state") or "").lower() == "out_of_stock"
        and (s.get("challenge") or s.get("status") == "blocked")
    ]
    return {
        "samples": samples,
        "false_oos_candidates": false_oos,
        "summary": {
            "total": len(samples),
            "accepted": sum(1 for s in samples if s.get("accepted")),
            "challenges": sum(1 for s in samples if s.get("challenge")),
            "incorrect_prices": sum(1 for s in samples if s.get("price_accuracy") == "incorrect"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-pair", type=int, default=1)
    parser.add_argument("--out", default="artifacts/retailer_detail_audit.json")
    args = parser.parse_args()
    report = asyncio.run(main_async(args.per_pair))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    json.dump(report["summary"], sys.stdout, indent=2)
    print()
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
