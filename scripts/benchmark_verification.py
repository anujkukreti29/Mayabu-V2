"""Small HTTP benchmark for a running Mayabu v5.2 API.

This intentionally uses the public endpoint and therefore exercises rate limits.
Use a staging environment and a controlled product-id list; it creates real
verification tasks.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * pct))))
    return ordered[index]


def _post(base_url: str, product_id: str, timeout: float) -> tuple[int, float, str]:
    started = time.perf_counter()
    request = Request(
        f"{base_url.rstrip('/')}/api/products/{product_id}/verify-price",
        data=b'{"mode":"best_offer"}',
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return int(response.status), (time.perf_counter() - started) * 1000, str(body.get("status"))
    except HTTPError as exc:
        return int(exc.code), (time.perf_counter() - started) * 1000, "http_error"
    except (URLError, TimeoutError, OSError):
        return 0, (time.perf_counter() - started) * 1000, "network_error"


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Mayabu live-verification admission")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--product-ids", required=True, help="Text file with one product UUID per line")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    ids = [line.strip() for line in Path(args.product_ids).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not ids:
        raise SystemExit("Product-id file is empty")
    targets = [ids[index % len(ids)] for index in range(max(1, args.requests))]
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = [executor.submit(_post, args.base_url, product_id, args.timeout) for product_id in targets]
        for future in as_completed(futures):
            results.append(future.result())

    latencies = [item[1] for item in results]
    status_counts: dict[str, int] = {}
    http_counts: dict[int, int] = {}
    for http_status, _, logical_status in results:
        http_counts[http_status] = http_counts.get(http_status, 0) + 1
        status_counts[logical_status] = status_counts.get(logical_status, 0) + 1
    print(json.dumps({
        "requests": len(results),
        "concurrency": args.concurrency,
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2),
            "p50": round(_percentile(latencies, 0.50), 2),
            "p95": round(_percentile(latencies, 0.95), 2),
            "p99": round(_percentile(latencies, 0.99), 2),
            "max": round(max(latencies), 2),
        },
        "http_statuses": http_counts,
        "logical_statuses": status_counts,
    }, indent=2))


if __name__ == "__main__":
    main()
