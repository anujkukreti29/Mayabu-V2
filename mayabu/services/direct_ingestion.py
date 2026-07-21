"""Direct product URL ingestion service."""

from __future__ import annotations

import time
from typing import Any

from mayabu.db.connection import db_connection
from mayabu.domain.product_identity import build_identity
from mayabu.scrapers.circuit_breaker import ensure_platform_available, record_platform_failure, record_platform_success
from mayabu.scrapers.detail import detect_platform, scrape_product_detail
from mayabu.search.cache import get_cache
from mayabu.search.index_manager import refresh_product_search_documents
from mayabu.services.variant_groups import refresh_variant_group
from mayabu_common import normalize_raw_listing
from mayabu_db.ingestion import ingest_records
from mayabu_db.repository import add_anomaly


async def ingest_product_url(
    url: str,
    *,
    platform: str | None = None,
    headless: bool = True,
    debug: bool = True,
    run_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    platform = platform or detect_platform(url)
    ensure_platform_available(platform)
    started = time.perf_counter()
    result = await scrape_product_detail(url, platform=platform, headless=headless, debug=debug)
    latency_ms = int((time.perf_counter() - started) * 1000)

    if result.status in {"failed", "blocked", "not_found"} or not result.title:
        record_platform_failure(platform, result.status, latency_ms)
        with db_connection() as conn:
            add_anomaly(
                conn,
                "high" if result.status == "blocked" else "medium",
                "direct_ingest_failed",
                "Direct product URL ingestion failed",
                platform=platform,
                run_id=run_id,
                evidence=result.as_dict(),
            )
        return {"ok": False, "platform": platform, "detail": result.as_dict()}

    raw = result.to_raw_listing(query=result.title)
    normalized = normalize_raw_listing(raw, platform_hint=platform, query=result.title)
    if not normalized:
        record_platform_failure(platform, "normalization_failed", latency_ms)
        return {"ok": False, "platform": platform, "detail": result.as_dict(), "error": "normalization_failed"}

    listing = None
    with db_connection() as conn:
        stats = ingest_records(
            conn, [raw], platform, result.title, run_id=run_id, task_id=task_id,
            observed_at=result.scraped_at,
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, product_id from platform_listings
                where listing_id = %s
                order by updated_at desc limit 1
                """,
                (normalized["listing_id"],),
            )
            listing = cur.fetchone()
            if listing:
                cur.execute(
                    """
                    update platform_listings
                    set rating = %s, review_count = %s,
                        last_detail_enriched_at = now(),
                        extraction_version = 'v5-jsonld-meta',
                        updated_at = now()
                    where id = %s
                    """,
                    (result.rating, result.review_count, listing["id"]),
                )

    product_id = str(listing["product_id"]) if listing and listing.get("product_id") else None
    variant_result: dict[str, Any] | None = None
    if product_id:
        identity = build_identity(result.title or "", result.specs, "laptop")
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update product_clusters
                    set exact_fingerprint = %s,
                        family_fingerprint = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (identity.exact_fingerprint, identity.family_fingerprint, product_id),
                )
        variant_result = refresh_variant_group(product_id)
        refresh_product_search_documents([product_id])
        get_cache().invalidate_product(product_id)

    record_platform_success(platform, latency_ms)
    return {
        "ok": stats.valid > 0,
        "platform": platform,
        "listing_id": normalized["listing_id"],
        "product_id": product_id,
        "stats": stats.as_dict(),
        "variant": variant_result,
        "detail": result.as_dict(),
        "latency_ms": latency_ms,
    }
