#!/usr/bin/env python3
"""Local/staging API load test (search + product + health). Does not hit retailers.

  python scripts/hardening_api_load_test.py --base-url http://127.0.0.1:8000 --concurrency 25 --requests 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter
from urllib.parse import urlencode

import httpx

QUERIES = (
    "laptop",
    "smartphone",
    "television",
    "refrigerator",
    "washing machine",
    "tws",
    "headphones",
    "camera",
    "samsung",
    "sony",
    "lg",
)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * pct))))
    return ordered[index]


async def run(args: argparse.Namespace) -> dict:
    sem = asyncio.Semaphore(args.concurrency)
    latencies: list[float] = []
    statuses: Counter[int | str] = Counter()
    paths = ["search", "health", "search"]

    async with httpx.AsyncClient(
        timeout=args.timeout,
        limits=httpx.Limits(max_connections=args.concurrency + 5),
    ) as client:

        async def one(i: int) -> None:
            kind = paths[i % len(paths)]
            if kind == "health":
                url = f"{args.base_url.rstrip('/')}/api/health"
            else:
                q = QUERIES[i % len(QUERIES)]
                url = f"{args.base_url.rstrip('/')}/api/search?{urlencode({'q': q, 'limit': 12})}"
            async with sem:
                started = time.perf_counter()
                try:
                    resp = await client.get(url)
                    statuses[resp.status_code] += 1
                except Exception as exc:
                    statuses[type(exc).__name__] += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)

        wall_start = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(args.requests)))
        elapsed = time.perf_counter() - wall_start

    success = sum(c for s, c in statuses.items() if isinstance(s, int) and 200 <= s < 300)
    return {
        "requests": args.requests,
        "concurrency": args.concurrency,
        "success": success,
        "errors": args.requests - success,
        "error_rate": round((args.requests - success) / max(1, args.requests), 4),
        "elapsed_seconds": round(elapsed, 3),
        "throughput_rps": round(args.requests / elapsed, 2) if elapsed else 0,
        "latency_ms": {
            "median": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "p99": round(percentile(latencies, 0.99), 2),
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0,
        },
        "statuses": dict(statuses),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    result = asyncio.run(run(args))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["errors"] == 0 else 2)


if __name__ == "__main__":
    main()
