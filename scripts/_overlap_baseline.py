"""Snapshot public multi-store coverage and the single-store gap."""
from __future__ import annotations

import json
from pathlib import Path

from mayabu.catalog.overlap_queries import _codes, missing_retailers, overlap_query
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu_db.connection import db_connection

OUT = Path("artifacts/catalog_overlap_v1")
CATEGORIES = (
    "laptop", "smartphone", "television", "refrigerator",
    "washing_machine", "tws", "headphones", "camera",
)


def _tier(category: str, brand: str, title: str, specs: dict) -> str:
    if _codes(specs, title):
        return "A"
    if overlap_query(category, brand, title, specs):
        return "B"
    return "C"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    healthy = {
        name
        for name in ("reliancedigital", "flipkart", "poorvika", "vijaysales")
        if platform_allows_task(name, "discovery")
    }
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select c.category,
                   count(*)::int products,
                   count(*) filter (where d.best_price > 0)::int priced,
                   count(*) filter (
                     where coalesce(d.image_url, '') <> ''
                        or exists (select 1 from product_images i where i.product_id = c.id)
                   )::int with_image,
                   count(*) filter (where coalesce(d.platform_count, 0) = 1)::int single_store,
                   count(*) filter (where coalesce(d.platform_count, 0) >= 2)::int ge2,
                   count(*) filter (where coalesce(d.platform_count, 0) >= 3)::int ge3,
                   count(*) filter (where coalesce(d.platform_count, 0) >= 4)::int ge4,
                   count(*) filter (where coalesce(d.platform_count, 0) >= 5)::int ge5
            from product_clusters c
            left join product_search_documents d on d.product_id = c.id
            where c.status = 'active' and c.category = any(%s)
            group by c.category
            order by c.category
            """,
            (list(CATEGORIES),),
        )
        counts = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select c.id, c.category, c.brand, c.canonical_title, c.specs,
                   d.best_price, d.platform_count,
                   array_agg(distinct l.platform) as platforms
            from product_clusters c
            join product_search_documents d on d.product_id = c.id
            join platform_listings l on l.product_id = c.id and l.match_status = 'matched'
            where c.status = 'active'
              and c.category = any(%s)
              and coalesce(d.platform_count, 0) = 1
              and d.best_price > 0
            group by c.id, d.best_price, d.platform_count
            """,
            (list(CATEGORIES),),
        )
        singles = list(cur.fetchall())
    gap = []
    tiers = {"A": 0, "B": 0, "C": 0}
    for row in singles:
        specs = row["specs"] if isinstance(row["specs"], dict) else {}
        title = row["canonical_title"] or ""
        tier = _tier(row["category"], row["brand"], title, specs)
        tiers[tier] += 1
        codes = _codes(specs, title)
        attached = {str(name) for name in (row["platforms"] or [])}
        gap.append({
            "product_id": str(row["id"]),
            "category": row["category"],
            "brand": row["brand"],
            "canonical_title": title,
            "model_code": codes[0] if codes else "",
            "identity": {
                "cpu": specs.get("cpu_models"),
                "ram_gb": specs.get("ram_gb"),
                "storage_gb": specs.get("storage_gb"),
                "gpu": specs.get("gpu_models") or specs.get("gpu"),
                "screen_size_inch": specs.get("screen_size_inch"),
                "capacity_l": specs.get("capacity_l"),
                "capacity_kg": specs.get("capacity_kg"),
                "door_type": specs.get("door_type"),
                "load_type": specs.get("load_type"),
                "color": specs.get("color"),
            },
            "current_retailer": next(iter(attached), ""),
            "missing_retailers": missing_retailers(row["category"], attached, healthy=healthy),
            "price": float(row["best_price"] or 0),
            "identity_confidence": tier,
            "search_visibility": "priced_search",
            "exact_query": overlap_query(row["category"], row["brand"], title, specs),
        })
    baseline = {"healthy": sorted(healthy), "categories": counts, "single_store_tiers": tiers}
    (OUT / "baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    (OUT / "overlap_before.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    (OUT / "single_store_gap.json").write_text(json.dumps(gap, indent=2), encoding="utf-8")
    print(json.dumps({"categories": len(counts), "gap": len(gap), "tiers": tiers, "healthy": sorted(healthy)}, indent=2))


if __name__ == "__main__":
    main()
