#!/usr/bin/env python3
"""Multi-worker API capacity matrix for local/staging Mayabu.

Starts N Uvicorn workers against the local API and runs mixed search/health/
product workloads. Does not hit retailers.

Examples:
  python scripts/ops_capacity_matrix.py --workers 1 --concurrency 10,25,50 --requests 100
  python scripts/ops_capacity_matrix.py --workers 2,4 --rate-limit off
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parents[1]
QUERIES = (
    "laptop",
    "smartphone",
    "television",
    "camera",
    "samsung",
    "sony lg refrigerator",
    "washing machine",
    "headphones",
)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * pct))))
    return ordered[index]


async def workload(base_url: str, *, concurrency: int, requests: int, timeout: float) -> dict:
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    statuses: Counter[int | str] = Counter()

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=httpx.Limits(max_connections=concurrency + 10),
    ) as client:

        async def one(i: int) -> None:
            kind = i % 5
            if kind == 0:
                url = f"{base_url}/api/health"
            elif kind == 1:
                url = f"{base_url}/api/live"
            else:
                q = QUERIES[i % len(QUERIES)]
                params = {"q": q, "limit": 12}
                if i % 7 == 0:
                    params["sort"] = "price_asc"
                if i % 11 == 0:
                    params["category"] = "laptop"
                url = f"{base_url}/api/search?{urlencode(params)}"
            async with sem:
                started = time.perf_counter()
                try:
                    resp = await client.get(url)
                    statuses[resp.status_code] += 1
                except Exception as exc:
                    statuses[type(exc).__name__] += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)

        wall = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(requests)))
        elapsed = time.perf_counter() - wall

    success = sum(c for s, c in statuses.items() if isinstance(s, int) and 200 <= s < 300)
    limited = statuses.get(429, 0)
    return {
        "requests": requests,
        "concurrency": concurrency,
        "success": success,
        "http_429": limited,
        "errors_non_429": requests - success - (limited if isinstance(limited, int) else 0),
        "error_rate_excluding_429": round(
            (requests - success - (limited if isinstance(limited, int) else 0)) / max(1, requests),
            4,
        ),
        "elapsed_seconds": round(elapsed, 3),
        "throughput_rps": round(requests / elapsed, 2) if elapsed else 0,
        "latency_ms": {
            "median": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "p99": round(percentile(latencies, 0.99), 2),
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0,
        },
        "statuses": dict(statuses),
    }


def start_api(port: int, workers: int, *, rate_limit: bool, env_extra: dict[str, str]) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(env_extra)
    env["PYTHONPATH"] = str(ROOT)
    env["MAYABU_API_WORKERS"] = str(workers)
    env["MAYABU_ENABLE_REDIS_RATE_LIMIT"] = "1" if rate_limit else "0"
    if not rate_limit:
        env["MAYABU_PUBLIC_RATE_LIMIT_PER_MINUTE"] = "100000"
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "mayabu.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--workers",
        str(workers),
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_ready(base_url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/api/live", timeout=1.5)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.4)
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--workers", default="1,2,4")
    parser.add_argument("--concurrency", default="10,25,50,100")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--rate-limit", choices=("on", "off"), default="off")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--external-base-url", default="", help="Skip spawning; use existing API")
    args = parser.parse_args()

    worker_counts = [int(x) for x in args.workers.split(",") if x.strip()]
    conc_levels = [int(x) for x in args.concurrency.split(",") if x.strip()]
    rate_limit = args.rate_limit == "on"
    matrix: list[dict] = []

    db_url = os.getenv("MAYABU_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url and not args.external_base_url:
        raise SystemExit("Set DATABASE_URL or MAYABU_TEST_DATABASE_URL")

    for workers in worker_counts:
        proc = None
        if args.external_base_url:
            base = args.external_base_url.rstrip("/")
        else:
            base = f"http://127.0.0.1:{args.port}"
            proc = start_api(
                args.port,
                workers,
                rate_limit=rate_limit,
                env_extra={
                    "DATABASE_URL": db_url or "",
                    "MAYABU_DB_POOL_MAX_SIZE": os.getenv("MAYABU_DB_POOL_MAX_SIZE", "8"),
                },
            )
            if not wait_ready(base):
                if proc:
                    proc.terminate()
                raise SystemExit(f"API failed to become ready (workers={workers})")
        try:
            health = httpx.get(f"{base}/api/health", timeout=5).json()
            for conc in conc_levels:
                result = asyncio.run(
                    workload(base, concurrency=conc, requests=args.requests, timeout=args.timeout)
                )
                result.update(
                    {
                        "workers": workers,
                        "rate_limit": args.rate_limit,
                        "estimated_max_db_connections": health.get("api_concurrency", {}).get(
                            "estimated_max_db_connections"
                        ),
                        "db_pool": health.get("db_pool"),
                    }
                )
                matrix.append(result)
                print(json.dumps(result, separators=(",", ":")))
        finally:
            if proc is not None:
                proc.send_signal(signal.SIGTERM if hasattr(signal, "SIGTERM") else signal.CTRL_BREAK_EVENT)
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
            # brief pause so port releases
            time.sleep(1.0)

    print(json.dumps({"matrix": matrix}, indent=2))


if __name__ == "__main__":
    main()
