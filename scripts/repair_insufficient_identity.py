"""Inspect / suppress insufficient-identity products in local/staging catalogs.

Does NOT delete platform listings or raw scrape evidence.
Does NOT target production databases.

Examples:
  python scripts/repair_insufficient_identity.py --inspect
  python scripts/repair_insufficient_identity.py --remove-search-docs --limit 50
  python scripts/repair_insufficient_identity.py --mark-needs-review --limit 50
"""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse

from mayabu.domain.identity_quality import has_sufficient_product_identity
from mayabu.search.index_manager import refresh_product_search_documents
from mayabu.search.search_repository import reset_search_source_cache
from mayabu_db.connection import db_connection
from mayabu_db.quality import REASON_INSUFFICIENT_IDENTITY


def _assert_safe_database(url: str) -> None:
    name = urlparse(url).path.lstrip("/").lower()
    if not name:
        raise SystemExit("DATABASE_URL has no database name")
    if name in {"mayabu_prod", "production", "prod"} or name.endswith("_prod"):
        raise SystemExit(f"Refusing to modify database named '{name}'")
    if "test" not in name and "staging" not in name:
        raise SystemExit(
            "Refuse non-test/staging DB. Use mayabu_test or a *staging* database name."
        )


def find_candidates(limit: int) -> list[dict]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, category, brand, canonical_title, specs, status
                from product_clusters
                where status = 'active'
                  and category not in ('unknown', 'accessory')
                order by updated_at desc nulls last, id
                limit %s
                """,
                (max(1, min(limit, 5000)),),
            )
            rows = list(cur.fetchall())
    out: list[dict] = []
    for row in rows:
        title = str(row.get("canonical_title") or "")
        specs = row.get("specs") if isinstance(row.get("specs"), dict) else {}
        if has_sufficient_product_identity(title, row.get("category"), specs=specs):
            continue
        out.append(
            {
                "product_id": str(row["id"]),
                "category": row.get("category"),
                "brand": row.get("brand"),
                "title": title,
                "reason": REASON_INSUFFICIENT_IDENTITY,
            }
        )
    return out


def remove_search_docs(product_ids: list[str]) -> int:
    if not product_ids:
        return 0
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "delete from product_search_documents where product_id = any(%s::uuid[])",
                (product_ids,),
            )
            deleted = cur.rowcount
            cur.execute(
                "delete from search_document_dirty where product_id = any(%s::uuid[])",
                (product_ids,),
            )
        conn.commit()
    return int(deleted or 0)


def mark_needs_review(product_ids: list[str]) -> int:
    if not product_ids:
        return 0
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update product_clusters
                set status = 'needs_review'
                where id = any(%s::uuid[]) and status = 'active'
                """,
                (product_ids,),
            )
            updated = cur.rowcount
        conn.commit()
    # Refresh so search docs drop inactive/needs_review products.
    refresh_product_search_documents(product_ids, strict=False)
    return int(updated or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair insufficient-identity catalog rows")
    parser.add_argument("--inspect", action="store_true", help="List candidates only")
    parser.add_argument(
        "--remove-search-docs",
        action="store_true",
        help="Delete public search documents for candidates (keep product rows)",
    )
    parser.add_argument(
        "--mark-needs-review",
        action="store_true",
        help="Set product_clusters.status=needs_review and refresh search docs",
    )
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL") or ""
    if not db_url:
        raise SystemExit("DATABASE_URL is required")
    _assert_safe_database(db_url)

    reset_search_source_cache()
    candidates = find_candidates(args.limit)
    print(json.dumps({"candidate_count": len(candidates), "candidates": candidates[:40]}, indent=2))

    if args.inspect or (not args.remove_search_docs and not args.mark_needs_review):
        return 0

    ids = [c["product_id"] for c in candidates]
    result: dict[str, int] = {"candidates": len(ids)}
    if args.remove_search_docs:
        result["search_docs_removed"] = remove_search_docs(ids)
    if args.mark_needs_review:
        result["marked_needs_review"] = mark_needs_review(ids)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
