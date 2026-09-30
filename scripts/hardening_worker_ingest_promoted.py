#!/usr/bin/env python3
"""Bounded worker-driven ingestion for production-enabled VS / Poorvika pairs.

Uses the real enqueue + claim + discovery/ingest path against local PostgreSQL.
Keep max_pages/max_products tiny; do not use for production crawls.

  set MAYABU_TEST_DATABASE_URL=postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_test
  python scripts/hardening_worker_ingest_promoted.py --dry-run
  python scripts/hardening_worker_ingest_promoted.py --max-products 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Production-enabled pairs only (coverage matrix).
PROMOTED_PAIRS: tuple[tuple[str, str], ...] = (
    ("vijaysales", "laptop"),
    ("vijaysales", "smartphone"),
    ("poorvika", "laptop"),
    ("poorvika", "smartphone"),
)


def _ensure_db() -> None:
    if not (os.getenv("MAYABU_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")):
        raise SystemExit("Set MAYABU_TEST_DATABASE_URL or DATABASE_URL")


async def _run_one(platform: str, category: str, *, max_pages: int, max_products: int) -> dict[str, Any]:
    from mayabu.jobs.queue import enqueue_task
    from mayabu.jobs.worker import run_once_async
    from mayabu.platforms.coverage import discovery_allowed

    if not discovery_allowed(platform, category):
        return {"platform": platform, "category": category, "skipped": True, "reason": "not_production"}

    started = time.perf_counter()
    enqueued = enqueue_task(
        "discovery",
        platform,
        query=category,
        priority=10,
        max_pages=max_pages,
        max_products=max_products,
        metadata={"category": category, "source": "hardening_promoted_ingest"},
        created_by="hardening_script",
        force=True,
    )
    worker_id = f"hardening-{platform}-{category}"
    ran = await run_once_async(worker_id)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    return {
        "platform": platform,
        "category": category,
        "enqueued": enqueued.get("created"),
        "task_id": str((enqueued.get("task") or {}).get("id")),
        "worker_ran": ran,
        "elapsed_ms": elapsed_ms,
    }


async def main_async(args: argparse.Namespace) -> int:
    _ensure_db()
    results: list[dict[str, Any]] = []
    pairs = PROMOTED_PAIRS
    if args.platform:
        pairs = tuple(p for p in pairs if p[0] == args.platform)
    if args.category:
        pairs = tuple(p for p in pairs if p[1] == args.category)

    if args.dry_run:
        from mayabu.platforms.coverage import discovery_allowed

        payload = [
            {
                "platform": p,
                "category": c,
                "discovery_allowed": discovery_allowed(p, c),
            }
            for p, c in pairs
        ]
        print(json.dumps({"dry_run": True, "pairs": payload}, indent=2))
        return 0

    for platform, category in pairs:
        try:
            results.append(
                await _run_one(
                    platform,
                    category,
                    max_pages=args.max_pages,
                    max_products=args.max_products,
                )
            )
        except Exception as exc:
            results.append(
                {
                    "platform": platform,
                    "category": category,
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                }
            )
    print(json.dumps({"results": results}, indent=2, default=str))
    try:
        from mayabu_db.connection import close_connection_pool

        close_connection_pool(timeout=1.0)
    except Exception:
        pass
    return 0 if all("error" not in r for r in results) else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--max-products", type=int, default=2)
    parser.add_argument("--platform")
    parser.add_argument("--category")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
