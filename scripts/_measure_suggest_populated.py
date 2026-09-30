"""Measure suggest latency/payload against a populated MAYABU_TEST_DATABASE_URL."""
from __future__ import annotations

import json
import os
import statistics
import time

os.environ.setdefault("MAYABU_ENV", "test")
# Measurement must not trip shared Redis rate limits used by pytest.
os.environ["MAYABU_ENABLE_REDIS_RATE_LIMIT"] = "false"
URL = os.environ.get("MAYABU_TEST_DATABASE_URL")
if not URL or "test" not in URL.lower():
    raise SystemExit("Set MAYABU_TEST_DATABASE_URL to a disposable DB whose name contains 'test'")
os.environ["DATABASE_URL"] = URL

from fastapi.testclient import TestClient

from mayabu.api.main import app
from mayabu.core.config import get_app_settings
from mayabu.search.cache import get_cache

get_app_settings.cache_clear()
QUERIES = ["samsung", "iphone", "sony", "oled", "gaming laptop", "sa", "asus"]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[idx]


with TestClient(app) as client:
    cache = get_cache()
    report = []
    for q in QUERIES:
        try:
            cache.invalidate_search()
        except Exception:
            pass
        cold = []
        for _ in range(5):
            try:
                cache.invalidate_search()
            except Exception:
                pass
            t0 = time.perf_counter()
            resp = client.get("/api/search/suggest", params={"q": q, "limit": 6})
            cold.append((time.perf_counter() - t0) * 1000)
            body = resp.json()
        # warm
        warm = []
        for _ in range(10):
            t0 = time.perf_counter()
            resp = client.get("/api/search/suggest", params={"q": q, "limit": 6})
            warm.append((time.perf_counter() - t0) * 1000)
            body = resp.json()
        report.append(
            {
                "q": q,
                "status": resp.status_code,
                "payload_bytes": len(resp.content),
                "products": len(body.get("products") or []),
                "categories": len(body.get("categories") or []),
                "cold_p50_ms": round(percentile(cold, 50), 2),
                "cold_p95_ms": round(percentile(cold, 95), 2),
                "warm_p50_ms": round(percentile(warm, 50), 2),
                "warm_p95_ms": round(percentile(warm, 95), 2),
                "warm_mean_ms": round(statistics.mean(warm), 2),
            }
        )

print(json.dumps(report, indent=2))
