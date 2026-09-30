#!/usr/bin/env python3
"""Synthetic matching-scale benchmark (isolated; does not touch staging search).

Measures candidate-generation style work using in-memory identities.
Labels results clearly as SYNTHETIC.
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import time
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mayabu.domain.matching import assess_product_match
from mayabu.domain.matching_noise import MATCHING_VERSION


def _make_product(i: int, category: str = "smartphone") -> dict[str, Any]:
    brand = random.choice(["samsung", "sony", "apple", "lg", "xiaomi"])
    storage = random.choice([128, 256, 512])
    model = f"M{i % 5000:04d}"
    return {
        "id": f"p{i}",
        "canonical_title": f"{brand} Device {model} {storage}GB",
        "title_norm": f"{brand} device {model} {storage}gb",
        "category": category,
        "specs": {
            "brand": brand,
            "category": category,
            "family": f"{brand}_device",
            "model_codes": [model],
            "storage_gb": storage,
            "ram_gb": 8,
        },
    }


def run_benchmark(n: int, samples: int = 50) -> dict[str, Any]:
    random.seed(42)
    catalog = [_make_product(i) for i in range(n)]
    # Index by (category, brand, model) — mirrors DB blocking intent.
    by_model: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for p in catalog:
        key = (p["category"], p["specs"]["brand"], p["specs"]["model_codes"][0])
        by_model.setdefault(key, []).append(p)

    times: list[float] = []
    candidate_counts: list[int] = []
    for _ in range(samples):
        listing = _make_product(random.randint(0, n - 1))
        key = (
            listing["category"],
            listing["specs"]["brand"],
            listing["specs"]["model_codes"][0],
        )
        candidates = by_model.get(key, [])[:64]
        # Also include a few same-brand distractors (bounded).
        distractors = [
            p
            for p in catalog
            if p["specs"]["brand"] == listing["specs"]["brand"] and p["id"] != listing.get("id")
        ][:8]
        pool = candidates + distractors
        candidate_counts.append(len(pool))
        t0 = time.perf_counter()
        for cand in pool:
            assess_product_match(listing, cand)
        times.append((time.perf_counter() - t0) * 1000)

    times_sorted = sorted(times)
    p95 = times_sorted[int(0.95 * (len(times_sorted) - 1))]
    return {
        "label": "SYNTHETIC",
        "matching_version": MATCHING_VERSION,
        "catalog_size": n,
        "samples": samples,
        "median_ms": round(statistics.median(times), 3),
        "p95_ms": round(p95, 3),
        "median_candidates": statistics.median(candidate_counts),
        "max_candidates": max(candidate_counts),
        "bounded": max(candidate_counts) <= 72,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="1000,10000,50000")
    parser.add_argument("--samples", type=int, default=40)
    args = parser.parse_args()
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    results = [run_benchmark(n, samples=args.samples) for n in sizes]
    import json

    print(json.dumps({"benchmark": results}, indent=2))
    if not all(r["bounded"] for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
