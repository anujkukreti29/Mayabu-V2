from __future__ import annotations

import argparse
import json

from mayabu.db.connection import db_connection, pool_stats
from mayabu.jobs.maintenance import run_maintenance
from mayabu.jobs.queue import enqueue_direct_ingest, get_task
from mayabu.scrapers.platforms import detect_platform
from mayabu.search.index_manager import (
    backfill_product_search_documents,
    drain_dirty_search_documents,
    get_search_index_stats,
    refresh_product_search_documents,
    refresh_product_search_index,
)
from mayabu.search.query_classifier import classify_query
from mayabu.search.search_repository import search_products
from mayabu.services.variant_groups import refresh_variant_groups
from mayabu_db.repository import (
    approve_review_item,
    auto_merge_duplicate_products,
    find_duplicate_product_candidates,
    merge_products,
    reject_review_item,
)


def _print_json(value) -> None:
    print(json.dumps(value, indent=2, default=str))


def list_review(limit: int, review_type: str | None = None) -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select rq.id, rq.review_type, rq.score, rq.evidence,
                       l.title as listing_title, l.platform, l.current_price,
                       p.canonical_title as candidate_title, p.brand as candidate_brand,
                       sp.canonical_title as source_product_title, sp.brand as source_product_brand
                from review_queue rq
                left join platform_listings l on l.id = rq.listing_id
                left join product_clusters p on p.id = rq.candidate_product_id
                left join product_clusters sp on sp.id = rq.source_product_id
                where rq.status = 'needs_review'
                  and (%s::text is null or rq.review_type = %s)
                order by rq.created_at asc
                limit %s
                """,
                (review_type, review_type, limit),
            )
            rows = [dict(row) for row in cur.fetchall()]
    _print_json(rows)


def approve(review_id: str, note: str | None) -> None:
    with db_connection() as conn:
        result = approve_review_item(conn, review_id, note=note)
    refresh_product_search_index(strict=False)
    _print_json(result)


def reject(review_id: str, note: str | None) -> None:
    with db_connection() as conn:
        result = reject_review_item(conn, review_id, note=note)
    _print_json(result)


def merge(primary_product_id: str, duplicate_product_id: str, note: str | None) -> None:
    with db_connection() as conn:
        result = merge_products(conn, primary_product_id, duplicate_product_id, reviewer_note=note, source="admin_cli")
    refresh_product_search_documents([primary_product_id], strict=False)
    _print_json(result)


def find_duplicates(limit: int, min_score: float) -> None:
    with db_connection() as conn:
        queued = find_duplicate_product_candidates(conn, limit=limit, min_score=min_score)
    _print_json({"queued": queued, "limit": limit, "min_score": min_score})


def auto_merge(limit: int, min_score: float, scan_limit: int) -> None:
    with db_connection() as conn:
        result = auto_merge_duplicate_products(conn, limit=limit, min_score=min_score, scan_limit=scan_limit)
    drain_dirty_search_documents(limit=5000, strict=False)
    _print_json(result)


def db_stats() -> None:
    _print_json({"search": get_search_index_stats(), "pool": pool_stats()})


def explain_matching(query: str, limit: int) -> None:
    parsed = classify_query(query)
    output = {
        "query": query,
        "normalized_query": parsed.normalized_query,
        "intent": parsed.intent,
        "category": parsed.detected_category,
        "brand": parsed.detected_brand,
        "family": getattr(parsed, "family", None),
        "model_codes": list(getattr(parsed, "model_codes", ()) or ()),
        "specs": parsed.detected_specs,
        "is_relevant": parsed.is_relevant,
        "candidates": [],
    }
    if parsed.is_relevant:
        rows = search_products(parsed, limit=limit, offset=0)
        for row in rows:
            specs = row.get("specs") or {}
            output["candidates"].append({
                "product_id": row.get("product_id"),
                "group": row.get("match_group"),
                "score": row.get("rank_score"),
                "title": row.get("canonical_title"),
                "platform_count": row.get("platform_count"),
                "best_platform": row.get("best_platform"),
                "best_price": row.get("best_price"),
                "brand": row.get("brand"),
                "family": row.get("family") or specs.get("family"),
                "model_codes": row.get("model_codes_text") or specs.get("model_codes"),
                "cpu": row.get("cpu_series") or specs.get("cpu_series"),
                "ram_gb": row.get("ram_gb") or specs.get("ram_gb"),
                "storage_gb": row.get("storage_gb") or specs.get("storage_gb"),
                "screen_inch": row.get("screen_inch") or specs.get("screen_inch"),
            })
    _print_json(output)


def refresh_variants(limit: int, only_missing: bool) -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.id
                from product_clusters p
                left join product_variant_links pvl on pvl.product_id = p.id
                where p.status = 'active'
                  and (%s::boolean = false or pvl.product_id is null)
                order by p.updated_at asc
                limit %s
                """,
                (only_missing, limit),
            )
            ids = [str(row["id"]) for row in cur.fetchall()]
    result = refresh_variant_groups(ids)
    index_result = refresh_product_search_documents(ids, strict=False)
    _print_json({"selected": len(ids), "variants": result, "search_documents": index_result})


def enqueue_url(url: str, platform: str | None, force: bool) -> None:
    platform = platform or detect_platform(url)
    _print_json(enqueue_direct_ingest(url, platform, force=force))


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu v5 operations, review, matching, index, and maintenance CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    ls = sub.add_parser("list")
    ls.add_argument("--limit", type=int, default=20)
    ls.add_argument("--type", dest="review_type", choices=["listing_match", "duplicate_product"])

    ap = sub.add_parser("approve")
    ap.add_argument("review_id")
    ap.add_argument("--note")

    rj = sub.add_parser("reject")
    rj.add_argument("review_id")
    rj.add_argument("--note")

    mg = sub.add_parser("merge-products")
    mg.add_argument("primary_product_id")
    mg.add_argument("duplicate_product_id")
    mg.add_argument("--note")

    fd = sub.add_parser("find-duplicates")
    fd.add_argument("--limit", type=int, default=100)
    fd.add_argument("--min-score", type=float, default=70.0)

    am = sub.add_parser("auto-merge-duplicates")
    am.add_argument("--limit", type=int, default=100)
    am.add_argument("--min-score", type=float, default=92.0)
    am.add_argument("--scan-limit", type=int, default=1500)

    sub.add_parser("refresh-search-index", help="Compatibility command; drains v5 dirty documents")

    drain = sub.add_parser("drain-search-documents")
    drain.add_argument("--limit", type=int, default=500)
    drain.add_argument("--strict", action="store_true")

    backfill = sub.add_parser("backfill-search-documents")
    backfill.add_argument("--batch-size", type=int, default=500)

    variants = sub.add_parser("refresh-variant-groups")
    variants.add_argument("--limit", type=int, default=5000)
    variants.add_argument("--only-missing", action="store_true")

    maint = sub.add_parser("maintenance")
    maint.add_argument("--job", choices=["all", "queue", "search", "storage"], default="all")

    eu = sub.add_parser("enqueue-url")
    eu.add_argument("url")
    eu.add_argument("--platform", choices=["amazon", "flipkart", "croma", "reliancedigital"])
    eu.add_argument("--force", action="store_true")

    task = sub.add_parser("task-status")
    task.add_argument("task_id")

    sub.add_parser("db-stats")

    em = sub.add_parser("explain-matching")
    em.add_argument("query")
    em.add_argument("--limit", type=int, default=12)

    args = parser.parse_args()
    if args.command == "list":
        list_review(args.limit, args.review_type)
    elif args.command == "approve":
        approve(args.review_id, args.note)
    elif args.command == "reject":
        reject(args.review_id, args.note)
    elif args.command == "merge-products":
        merge(args.primary_product_id, args.duplicate_product_id, args.note)
    elif args.command == "find-duplicates":
        find_duplicates(args.limit, args.min_score)
    elif args.command == "auto-merge-duplicates":
        auto_merge(args.limit, args.min_score, args.scan_limit)
    elif args.command == "refresh-search-index":
        _print_json({"ok": refresh_product_search_index(strict=True), **get_search_index_stats()})
    elif args.command == "drain-search-documents":
        _print_json(drain_dirty_search_documents(limit=args.limit, strict=args.strict))
    elif args.command == "backfill-search-documents":
        _print_json(backfill_product_search_documents(batch_size=args.batch_size))
    elif args.command == "refresh-variant-groups":
        refresh_variants(args.limit, args.only_missing)
    elif args.command == "maintenance":
        _print_json(run_maintenance(args.job))
    elif args.command == "enqueue-url":
        enqueue_url(args.url, args.platform, args.force)
    elif args.command == "task-status":
        _print_json(get_task(args.task_id) or {"error": "task_not_found"})
    elif args.command == "db-stats":
        db_stats()
    elif args.command == "explain-matching":
        explain_matching(args.query, args.limit)


if __name__ == "__main__":
    main()
