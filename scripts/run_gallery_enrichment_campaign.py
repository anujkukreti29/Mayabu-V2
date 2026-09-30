"""Bounded gallery enrichment campaign for camera / TV / appliances.

Materializes enrich_listing tasks and optionally executes a small batch inline
(no broad crawl). Same-PDP images only via existing enrich_listing pipeline.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from mayabu.catalog.enrichment import due_enrichment_candidates, enrich_listing, materialize_enrichment
from mayabu.catalog.image_backfill import backfill_product_images


async def _run_inline(category: str, limit: int) -> list[dict]:
    rows = due_enrichment_candidates(limit=limit, category=category)
    outcomes: list[dict] = []
    for row in rows:
        listing_id = str(row["id"])
        try:
            result = await enrich_listing(row, headless=True)
            outcomes.append(
                {
                    "listing_id": listing_id,
                    "platform": row["platform"],
                    "ok": bool(result.get("ok")) if isinstance(result, dict) else False,
                    "result": result if isinstance(result, dict) else {"status": str(result)},
                }
            )
        except Exception as exc:  # noqa: BLE001 — campaign report
            outcomes.append(
                {
                    "listing_id": listing_id,
                    "platform": row["platform"],
                    "ok": False,
                    "error": str(exc)[:240],
                }
            )
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--categories",
        default="camera,television,refrigerator,washing_machine",
        help="Comma-separated categories",
    )
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--inline", action="store_true", help="Execute enrichments inline")
    parser.add_argument("--backfill-only", action="store_true")
    args = parser.parse_args()

    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    report: dict = {"categories": {}, "backfill": {}}

    for cat in cats:
        report["backfill"][cat] = backfill_product_images(limit=200, category=cat)
        if args.backfill_only:
            continue
        created = materialize_enrichment(limit=args.limit, category=cat)
        entry: dict = {"tasks_created": created}
        if args.inline and created >= 0:
            entry["inline"] = asyncio.run(_run_inline(cat, args.limit))
        report["categories"][cat] = entry

    json.dump(report, sys.stdout, indent=2, default=str)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
