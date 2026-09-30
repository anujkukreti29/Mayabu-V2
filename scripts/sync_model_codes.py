"""Sync model_codes from matched listing titles onto product_clusters (idempotent)."""

from __future__ import annotations

import argparse
import json
from typing import Any

from psycopg.types.json import Jsonb

from mayabu.catalog.model_codes import model_codes_list
from mayabu.db.connection import db_connection
from mayabu.search.index_manager import refresh_product_search_documents


def sync_model_codes(*, category: str | None = "smartphone", limit: int = 500) -> dict[str, Any]:
    params: list[Any] = []
    cat = ""
    if category:
        cat = "and pl.category = %s"
        params.append(category)
    params.append(max(1, min(int(limit), 5_000)))
    updated = 0
    affected: list[str] = []
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select pc.id as product_id, pc.specs as cluster_specs,
                       pl.title, pl.specs as listing_specs, pl.category
                from product_clusters pc
                join platform_listings pl on pl.product_id = pc.id and pl.match_status = 'matched'
                where pl.title is not null
                  {cat}
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
                {"codes": set(), "specs": row["cluster_specs"] if isinstance(row.get("cluster_specs"), dict) else {}},
            )
            codes = model_codes_list(
                title=row.get("title"),
                specs=row.get("listing_specs") if isinstance(row.get("listing_specs"), dict) else {},
                category=row.get("category") or category,
            )
            bucket["codes"].update(codes)
        with conn.cursor() as cur:
            for pid, payload in by_product.items():
                if not payload["codes"]:
                    continue
                specs = dict(payload["specs"] or {})
                existing = {str(c).upper() for c in (specs.get("model_codes") or [])}
                merged = sorted(existing | {str(c).upper() for c in payload["codes"]})
                if merged == sorted(existing):
                    continue
                specs["model_codes"] = merged
                cur.execute(
                    "update product_clusters set specs = %s, updated_at = now() where id = %s::uuid",
                    (Jsonb(specs), pid),
                )
                updated += 1
                affected.append(pid)
    if affected:
        refresh_product_search_documents(affected[:200], strict=False)
    return {"updated": updated, "category": category, "affected": len(affected)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="smartphone")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(sync_model_codes(category=args.category, limit=args.limit), indent=2))


if __name__ == "__main__":
    main()
