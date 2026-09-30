#!/usr/bin/env python3
"""Bounded staging write-load: concurrent listing upserts / price observations.

Uses fixtures already in DB or synthetic titles — does not crawl retailers.

  set MAYABU_TEST_DATABASE_URL=...
  python scripts/hardening_write_load_test.py --workers 8 --iterations 20
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _one(iteration: int) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row
    from mayabu_db.ingestion import ingest_records

    url = os.environ.get("MAYABU_TEST_DATABASE_URL") or os.environ["DATABASE_URL"]
    started = time.perf_counter()
    native = f"hardening-wl-{iteration}-{uuid.uuid4().hex[:8]}"
    records = [
        {
            "platform": "amazon",
            "category": "laptop",
            "title": f"Hardening WriteLoad Test Laptop {native} 16GB 512GB",
            "url": f"https://www.amazon.in/dp/{native}",
            "native_id": native,
            "price": 49990 + (iteration % 100),
            "mrp": 59990,
            "currency": "INR",
            "stock_status": "in_stock",
            "image_url": None,
            "specs": {
                "brand": "mayabu",
                "category": "laptop",
                "ram_gb": 16,
                "storage_gb": 512,
                "model_codes": [native.upper()],
            },
        }
    ]
    with psycopg.connect(url, row_factory=dict_row) as conn:
        stats = ingest_records(
            conn,
            records,
            "amazon",
            "laptop",
            run_id=None,
            task_id=None,
        )
        conn.commit()
    accepted = getattr(stats, "valid", None)
    if accepted is None and hasattr(stats, "accepted"):
        accepted = stats.accepted
    return {
        "iteration": iteration,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "accepted": accepted,
        "stats": stats.as_dict() if hasattr(stats, "as_dict") else str(stats),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=20)
    args = parser.parse_args()
    if not (os.getenv("MAYABU_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")):
        raise SystemExit("Set MAYABU_TEST_DATABASE_URL")

    wall = time.perf_counter()
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_one, i) for i in range(args.iterations)]
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}"[:300])
    elapsed = time.perf_counter() - wall
    latencies = [r["elapsed_ms"] for r in results]
    latencies.sort()
    payload = {
        "workers": args.workers,
        "iterations": args.iterations,
        "success": len(results),
        "errors": len(errors),
        "error_samples": errors[:5],
        "elapsed_seconds": round(elapsed, 3),
        "latency_ms": {
            "median": latencies[len(latencies) // 2] if latencies else 0,
            "p95": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0,
            "max": max(latencies) if latencies else 0,
        },
    }
    print(json.dumps(payload, indent=2, default=str))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
