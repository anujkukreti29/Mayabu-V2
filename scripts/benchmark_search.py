"""Small bounded load test for the Mayabu search API.

This is not a replacement for distributed load testing. It is a repeatable
local smoke benchmark that reports latency percentiles and errors.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter
from urllib.parse import urlencode

import httpx

DEFAULT_QUERIES = (
    "laptop",
    "ASUS Vivobook 14 Ultra 5 225H",
    "Apple MacBook Air M2 8GB 256GB",
    "X1607CA-MB142WS",
)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * pct))))
    return ordered[index]


async def run(args: argparse.Namespace) -> int:
    semaphore = asyncio.Semaphore(args.concurrency)
    latencies: list[float] = []
    statuses: Counter[int | str] = Counter()

    async with httpx.AsyncClient(timeout=args.timeout, limits=httpx.Limits(max_connections=args.concurrency)) as client:
        async def one(index: int) -> None:
            query = args.query[index % len(args.query)]
            url = f"{args.base_url.rstrip('/')}/api/search?{urlencode({'q': query, 'limit': args.limit})}"
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(url)
                    statuses[response.status_code] += 1
                    response.raise_for_status()
                except Exception as exc:
                    statuses[type(exc).__name__] += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(args.requests)))
        elapsed = time.perf_counter() - started

    success = sum(count for status, count in statuses.items() if isinstance(status, int) and 200 <= status < 300)
    result = {
        "requests": args.requests,
        "concurrency": args.concurrency,
        "success": success,
        "errors": args.requests - success,
        "elapsed_seconds": round(elapsed, 3),
        "requests_per_second": round(args.requests / elapsed, 2) if elapsed else 0,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0,
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0,
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "p99": round(percentile(latencies, 0.99), 2),
            "max": round(max(latencies), 2) if latencies else 0,
        },
        "statuses": dict(statuses),
    }
    print(result)
    return 0 if result["errors"] == 0 else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded Mayabu search API load test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--query", action="append", default=[])
    args = parser.parse_args()
    args.requests = max(1, min(args.requests, 100000))
    args.concurrency = max(1, min(args.concurrency, 500))
    args.query = args.query or list(DEFAULT_QUERIES)
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
