#!/usr/bin/env python3
"""Bounded rematch/repair helper for staging/test catalogs only.

Safety:
  - Default is --dry-run (report only).
  - --apply requires MAYABU_ALLOW_REMATCH=1.
  - Requires --category and/or --product-id (no full-catalog rematch).
  - Refuses when MAYABU_ENV=production unless explicitly allowed.

Usage:
  python scripts/rematch_catalog.py --category smartphone --dry-run
  python scripts/rematch_catalog.py --product-id <uuid> --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded rematch for staging/test catalogs")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--category")
    parser.add_argument("--product-id")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json-out")
    args = parser.parse_args()

    if not args.category and not args.product_id:
        print(json.dumps({"error": "require --category and/or --product-id"}))
        return 2

    env = (os.getenv("MAYABU_ENV") or "").strip().lower()
    if env == "production" and not os.getenv("MAYABU_ALLOW_PRODUCTION_REMATCH"):
        print(json.dumps({"error": "refusing production rematch without MAYABU_ALLOW_PRODUCTION_REMATCH"}))
        return 2

    if args.apply and os.getenv("MAYABU_ALLOW_REMATCH") != "1":
        print(json.dumps({"error": "--apply requires MAYABU_ALLOW_REMATCH=1"}))
        return 2

    # Rematch apply is intentionally not implemented yet; audit first.
    report = {
        "mode": "apply" if args.apply else "dry-run",
        "category": args.category,
        "product_id": args.product_id,
        "limit": args.limit,
        "matching_version": 2,
        "message": (
            "Rematch apply path reserved. Run scripts/audit_product_matching.py first; "
            "manual review required before any merge."
        ),
        "actions": [],
    }
    text = json.dumps(report, indent=2)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
