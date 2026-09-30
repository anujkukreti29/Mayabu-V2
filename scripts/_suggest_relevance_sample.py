"""One-shot suggest relevance + payload sample against MAYABU_TEST_DATABASE_URL."""
from __future__ import annotations

import json
import os

os.environ.setdefault("MAYABU_ENV", "test")
os.environ["MAYABU_ENABLE_REDIS_RATE_LIMIT"] = "false"
URL = os.environ.get("MAYABU_TEST_DATABASE_URL")
if not URL or "test" not in URL.lower():
    raise SystemExit("Set MAYABU_TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = URL

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
    out = []
    for q in ["samsung", "iphone", "sony", "oled", "gaming laptop", "sa", "asus"]:
        r = client.get("/api/search/suggest", params={"q": q, "limit": 6})
        body = r.json()
        titles = []
        for p in body.get("products") or []:
            titles.append(p.get("title") or p.get("canonical_title") or p.get("name"))
        cats = [
            c.get("label") or c.get("name") or c.get("slug") for c in (body.get("categories") or [])
        ]
        out.append(
            {
                "q": q,
                "status": r.status_code,
                "bytes": len(r.content),
                "products": len(body.get("products") or []),
                "categories": cats,
                "titles": titles[:4],
                "prices": [
                    p.get("best_price") or p.get("price") for p in (body.get("products") or [])[:4]
                ],
            }
        )
    sr = client.get("/api/search", params={"q": "samsung", "limit": 24})
    sj = sr.json()
    results = sj.get("results") or sj.get("items") or sj.get("exact") or []
    if isinstance(results, dict):
        results = results.get("items") or []
    out.append(
        {
            "endpoint": "search",
            "q": "samsung",
            "status": sr.status_code,
            "bytes": len(sr.content),
            "result_keys": list(sj.keys())[:12],
        }
    )
    print(json.dumps(out, indent=2))
