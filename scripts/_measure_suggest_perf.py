"""Measure /api/search/suggest latency and payload size on the harden test DB."""
from __future__ import annotations

import json
import os
import time

os.environ["MAYABU_TEST_DATABASE_URL"] = (
    "postgresql://mayabu:mayabu_dev_password@127.0.0.1:5433/mayabu_ux_harden_test"
)
os.environ["DATABASE_URL"] = os.environ["MAYABU_TEST_DATABASE_URL"]
os.environ.setdefault("MAYABU_ENV", "test")

from fastapi.testclient import TestClient

from mayabu.api.main import app
from mayabu.core.config import get_app_settings
from mayabu.search.cache import get_cache

get_app_settings.cache_clear()

with TestClient(app) as client:
    cache = get_cache()
    try:
        cache.invalidate_search()
    except Exception:
        pass

    rows = []
    for label, q in [("min_len_skip_db", "s"), ("bounded", "sa"), ("samsung", "samsung")]:
        try:
            cache.invalidate_search()
        except Exception:
            pass
        t0 = time.perf_counter()
        resp = client.get("/api/search/suggest", params={"q": q, "limit": 6})
        elapsed = (time.perf_counter() - t0) * 1000
        payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        rows.append(
            {
                "case": label,
                "q": q,
                "status": resp.status_code,
                "elapsed_ms": round(elapsed, 2),
                "payload_bytes": len(resp.content),
                "products": len(payload.get("products") or []),
                "categories": len(payload.get("categories") or []),
                "popular": len(payload.get("popular_queries") or []),
            }
        )

    t0 = time.perf_counter()
    resp = client.get("/api/search/suggest", params={"q": "samsung", "limit": 6})
    rows.append(
        {
            "case": "cache_hit_samsung",
            "q": "samsung",
            "status": resp.status_code,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
            "payload_bytes": len(resp.content),
            "products": len(resp.json().get("products") or []),
            "categories": len(resp.json().get("categories") or []),
            "popular": len(resp.json().get("popular_queries") or []),
        }
    )

print(json.dumps(rows, indent=2))
