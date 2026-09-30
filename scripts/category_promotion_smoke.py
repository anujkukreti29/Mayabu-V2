#!/usr/bin/env python3
"""Bounded live readiness probes for platform × category promotion decisions."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


async def _scrape(platform: str, query: str, *, max_products: int = 8) -> list[dict[str, Any]]:
    if platform == "vijaysales":
        from vijaysales_scraper import scrape_vijaysales

        return await scrape_vijaysales(query, max_products=max_products, max_pages=1, headless=True)
    if platform == "poorvika":
        from poorvika_scraper import scrape_poorvika

        return await scrape_poorvika(query, max_products=max_products, max_pages=1, headless=True)
    if platform == "jiomart":
        from jiomart_scraper import scrape_jiomart

        return await scrape_jiomart(query, max_products=max_products, max_pages=1, headless=True)
    raise ValueError(platform)


def _score(rows: list[dict[str, Any]], expected_category: str) -> dict[str, Any]:
    n = len(rows)
    priced = sum(1 for r in rows if r.get("price"))
    imaged = sum(1 for r in rows if r.get("image"))
    urls = sum(1 for r in rows if str(r.get("link") or "").startswith("http"))
    native = sum(1 for r in rows if r.get("native_id"))
    cats = Counter(str(r.get("category") or "unknown") for r in rows)
    correct = cats.get(expected_category, 0)
    links = [str(r.get("link") or "") for r in rows]
    dup_rate = 1.0 - (len(set(links)) / n) if n else 0.0
    return {
        "discovered": n,
        "priced": priced,
        "imaged": imaged,
        "url_rate": round(urls / n, 3) if n else 0.0,
        "price_rate": round(priced / n, 3) if n else 0.0,
        "image_rate": round(imaged / n, 3) if n else 0.0,
        "native_id_rate": round(native / n, 3) if n else 0.0,
        "category_accuracy": round(correct / n, 3) if n else 0.0,
        "duplicate_rate": round(dup_rate, 3),
        "categories": dict(cats),
        "sample": [
            {
                "title": (r.get("title") or "")[:70],
                "price": r.get("price"),
                "category": r.get("category"),
                "native_id": r.get("native_id"),
            }
            for r in rows[:3]
        ],
    }


def _passes(score: dict[str, Any], *, min_n: int = 4) -> bool:
    if score["discovered"] < min_n:
        return False
    if score["price_rate"] < 0.5:
        return False
    if score["image_rate"] < 0.5:
        return False
    if score["category_accuracy"] < 0.5:
        return False
    if score["duplicate_rate"] > 0.35:
        return False
    return True


async def main() -> int:
    probes = [
        ("vijaysales", "laptop", "laptop"),
        ("vijaysales", "laptop", "hp laptop"),
        ("vijaysales", "laptop", "laptop"),  # repeat
        ("vijaysales", "smartphone", "smartphone"),
        ("vijaysales", "smartphone", "samsung smartphone"),
        ("vijaysales", "television", "television"),
        ("vijaysales", "refrigerator", "refrigerator"),
        ("vijaysales", "refrigerator", "lg refrigerator"),
        ("vijaysales", "washing_machine", "washing_machine"),
        ("vijaysales", "washing_machine", "lg washing machine"),
        ("vijaysales", "headphones", "headphones"),
        ("vijaysales", "camera", "camera"),
        ("vijaysales", "camera", "nikon camera"),
        ("poorvika", "laptop", "laptop"),
        ("poorvika", "laptop", "laptop"),  # repeat
        ("poorvika", "smartphone", "smartphone"),
        ("poorvika", "smartphone", "smartphone"),  # repeat
        ("poorvika", "television", "television"),
        ("poorvika", "camera", "camera"),
        ("jiomart", "smartphone", "smartphone"),
    ]
    results = []
    for platform, category, query in probes:
        print(f"PROBE {platform}/{category} q={query}", flush=True)
        try:
            rows = await _scrape(platform, query, max_products=8)
            score = _score(rows, category)
            score.update(
                {
                    "platform": platform,
                    "category": category,
                    "query": query,
                    "pass": _passes(score, min_n=3 if category == "camera" else 4),
                }
            )
        except Exception as exc:
            score = {
                "platform": platform,
                "category": category,
                "query": query,
                "error": str(exc)[:200],
                "pass": False,
            }
        results.append(score)
        print(json.dumps({k: score[k] for k in ("platform", "category", "query", "pass", "discovered", "price_rate", "category_accuracy") if k in score}, ensure_ascii=True), flush=True)

    out_path = os.path.join(ROOT, "tmp_category_promotion_smoke.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=True)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
