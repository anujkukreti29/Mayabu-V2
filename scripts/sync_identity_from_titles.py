"""Sync family/RAM/storage/model identity from listing titles onto clusters."""

from __future__ import annotations

import argparse
import json
from typing import Any

from psycopg.types.json import Jsonb

from mayabu.catalog.model_codes import model_codes_list
from mayabu.db.connection import db_connection
from mayabu.domain.categories.registry import extract_category_specs
from mayabu.search.index_manager import refresh_product_search_documents


def sync_identity(*, category: str = "smartphone", limit: int = 500) -> dict[str, Any]:
    params: list[Any] = [category, max(1, min(int(limit), 5_000))]
    updated = 0
    affected: list[str] = []
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select pc.id as product_id, pc.specs as cluster_specs,
                       pl.title, pl.specs as listing_specs, pl.category
                from product_clusters pc
                join platform_listings pl on pl.product_id = pc.id and pl.match_status = 'matched'
                where pl.category = %s and pl.title is not null
                order by pl.updated_at desc nulls last
                limit %s
                """,
                tuple(params),
            )
            rows = [dict(r) for r in cur.fetchall()]
        by_product: dict[str, dict[str, Any]] = {}
        for row in rows:
            pid = str(row["product_id"])
            bucket = by_product.setdefault(
                pid,
                {
                    "specs": row["cluster_specs"] if isinstance(row.get("cluster_specs"), dict) else {},
                    "titles": [],
                    "listing_specs": [],
                },
            )
            bucket["titles"].append(row.get("title") or "")
            if isinstance(row.get("listing_specs"), dict):
                bucket["listing_specs"].append(row["listing_specs"])
        with conn.cursor() as cur:
            for pid, payload in by_product.items():
                specs = dict(payload["specs"] or {})
                changed = False
                codes = set(str(c).upper() for c in (specs.get("model_codes") or []))
                for title in payload["titles"]:
                    extracted = extract_category_specs(title, category)
                    for key in ("family", "ram_gb", "storage_gb", "brand", "screen_size_inch", "chipset"):
                        if extracted.get(key) not in (None, "", [], {}) and specs.get(key) in (None, "", [], {}):
                            specs[key] = extracted[key]
                            changed = True
                    codes.update(model_codes_list(title=title, specs=extracted, category=category))
                    codes.update(str(c).upper() for c in (extracted.get("model_codes") or []))
                for ls in payload["listing_specs"]:
                    for key in ("family", "ram_gb", "storage_gb", "brand", "screen_size_inch"):
                        if ls.get(key) not in (None, "", [], {}) and specs.get(key) in (None, "", [], {}):
                            specs[key] = ls[key]
                            changed = True
                    codes.update(str(c).upper() for c in (ls.get("model_codes") or []))
                new_codes = sorted(c for c in codes if c)
                if new_codes and new_codes != sorted(str(c).upper() for c in (specs.get("model_codes") or [])):
                    specs["model_codes"] = new_codes
                    changed = True
                if not changed:
                    continue
                cur.execute(
                    "update product_clusters set specs = %s, brand = coalesce(%s, brand), updated_at = now() where id = %s::uuid",
                    (Jsonb(specs), specs.get("brand"), pid),
                )
                # Also refresh listing specs weakly for family/ram/storage when empty
                cur.execute(
                    """
                    update platform_listings
                    set specs = specs || %s::jsonb, updated_at = now()
                    where product_id = %s::uuid and match_status = 'matched'
                    """,
                    (
                        Jsonb(
                            {
                                k: specs[k]
                                for k in ("family", "ram_gb", "storage_gb", "model_codes", "brand")
                                if specs.get(k) not in (None, "", [], {})
                            }
                        ),
                        pid,
                    ),
                )
                updated += 1
                affected.append(pid)
    if affected:
        refresh_product_search_documents(affected[:300], strict=False)
    return {"updated": updated, "category": category, "affected": len(affected)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="smartphone")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(sync_identity(category=args.category, limit=args.limit), indent=2))


if __name__ == "__main__":
    main()
