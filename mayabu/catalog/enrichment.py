"""Background listing enrichment — gallery, model codes, specs.

Separate from verify_listing / refresh_listing so Check Latest Price stays
price+stock focused.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from mayabu.catalog.product_images import upsert_product_images
from mayabu.db.connection import db_connection
from mayabu.domain.product_identity import build_identity
from mayabu.scrapers.circuit_breaker import (
    ensure_platform_available,
    record_platform_failure,
    record_platform_success,
)
from mayabu.scrapers.detail import scrape_product_detail
from mayabu.search.cache import get_cache
from mayabu.search.index_manager import refresh_product_search_documents
from mayabu_common import normalize_raw_listing
from mayabu_db.repository import merge_product_specs
from mayabu_db.tasks import create_task
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)

# Lower priority than verify(5) and hot refresh(40); above cold refresh(120).
ENRICH_PRIORITY = 95
ENRICH_MAX_ATTEMPTS = 2
ENRICH_COOLDOWN_HOURS = 72


def completeness_flags(
    *,
    specs: dict[str, Any] | None,
    image_count: int,
    store_count: int,
    has_price: bool,
) -> dict[str, bool]:
    specs = specs or {}
    codes = specs.get("model_codes") or []
    has_model = bool(codes) or bool(specs.get("model") or specs.get("model_number"))
    has_variant = any(
        specs.get(k) not in (None, "", [], {})
        for k in ("ram_gb", "storage_gb", "color", "variant", "screen_size_inch", "kit_lens")
    )
    key_spec_keys = (
        "cpu",
        "gpu",
        "ram_gb",
        "storage_gb",
        "chipset",
        "battery_mah",
        "screen_size_inch",
        "panel",
        "capacity_l",
        "load_type",
        "sensor",
        "anc",
    )
    has_key = sum(1 for k in key_spec_keys if specs.get(k) not in (None, "", [], {})) >= 2
    return {
        "has_model_number": has_model,
        "has_variant_identity": has_variant,
        "has_primary_image": image_count >= 1,
        "has_gallery": image_count >= 2,
        "has_key_specs": has_key,
        "has_valid_price": has_price,
        "has_multi_store": store_count >= 2,
    }


def listing_needs_enrichment(row: dict[str, Any], *, image_count: int = 0) -> bool:
    specs = row.get("specs") if isinstance(row.get("specs"), dict) else {}
    flags = completeness_flags(
        specs=specs,
        image_count=image_count,
        store_count=int(row.get("store_count") or 1),
        has_price=row.get("current_price") is not None,
    )
    if not flags["has_primary_image"] or not flags["has_gallery"]:
        return True
    if not flags["has_model_number"]:
        return True
    if not flags["has_key_specs"]:
        return True
    return False


def due_enrichment_candidates(*, limit: int = 40, category: str | None = None) -> list[dict[str, Any]]:
    """Matched listings due for background enrichment (incomplete / never enriched)."""
    params: list[Any] = []
    cat_clause = ""
    if category:
        cat_clause = "and pl.category = %s"
        params.append(category)
    params.append(max(1, min(int(limit), 200)))
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select pl.id, pl.platform, pl.listing_url, pl.product_id, pl.category,
                       pl.specs, pl.current_price, pl.image_url, pl.title,
                       pl.last_detail_enriched_at,
                       coalesce(img.cnt, 0)::int as image_count,
                       coalesce(stores.store_count, 1)::int as store_count
                from platform_listings pl
                left join lateral (
                  select count(*)::int as cnt
                  from product_images pi
                  where pi.product_id = pl.product_id and pi.active
                ) img on true
                left join lateral (
                  select count(distinct platform)::int as store_count
                  from platform_listings pl2
                  where pl2.product_id = pl.product_id and pl2.match_status = 'matched'
                ) stores on true
                where pl.match_status = 'matched'
                  and pl.listing_url is not null
                  and length(trim(pl.listing_url)) > 12
                  and coalesce(pl.match_evidence->>'listing_role', 'primary') <> 'alias'
                  and pl.platform in ('amazon','flipkart','croma','reliancedigital','vijaysales','poorvika')
                  and (
                    pl.last_detail_enriched_at is null
                    or pl.last_detail_enriched_at < now() - make_interval(hours => {int(ENRICH_COOLDOWN_HOURS)})
                  )
                  and not exists (
                    select 1 from scrape_tasks st
                    where st.task_type = 'enrich_listing'
                      and st.status in ('pending','running','paused')
                      and (st.metadata->>'platform_listing_id') = pl.id::text
                  )
                  {cat_clause}
                order by
                  case pl.category
                    when 'laptop' then 0
                    when 'camera' then 1
                    when 'television' then 2
                    when 'refrigerator' then 3
                    when 'washing_machine' then 4
                    when 'smartphone' then 5
                    when 'headphones' then 6
                    when 'tws' then 7
                    else 8
                  end,
                  case when coalesce(img.cnt, 0) < 2 then 0 else 1 end,
                  case when coalesce(stores.store_count, 1) >= 2 then 0 else 1 end,
                  case pl.platform
                    when 'amazon' then 0
                    when 'flipkart' then 1
                    when 'reliancedigital' then 2
                    when 'croma' then 3
                    else 4
                  end,
                  case when coalesce(pl.specs->'model_codes', '[]'::jsonb) = '[]'::jsonb then 0 else 1 end,
                  pl.updated_at desc
                limit %s
                """,
                tuple(params),
            )
            return [dict(r) for r in cur.fetchall()]


def materialize_enrichment(*, limit: int = 20, category: str | None = None) -> int:
    rows = due_enrichment_candidates(limit=limit, category=category)
    created = 0
    with db_connection() as conn:
        for row in rows:
            if not listing_needs_enrichment(row, image_count=int(row.get("image_count") or 0)):
                continue
            listing_id = str(row["id"])
            create_task(
                conn,
                row["platform"],
                "enrich_listing",
                url=row["listing_url"],
                priority=ENRICH_PRIORITY,
                metadata={
                    "source": "enrichment_v1",
                    "platform_listing_id": listing_id,
                    "product_id": str(row["product_id"]) if row.get("product_id") else None,
                    "category": row.get("category"),
                    "purpose": "gallery_specs_model",
                },
                idempotency_key=f"enrich_listing:{listing_id}",
                created_by="scheduler",
            )
            created += 1
    return created


def _merge_specs_conservative(existing: dict[str, Any], incoming: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Merge specs without overwriting identity conflicts silently."""
    out = dict(existing or {})
    conflicts: list[str] = []
    identity_keys = {
        "ram_gb",
        "storage_gb",
        "screen_size_inch",
        "kit_lens",
        "body_only",
        "cpu",
        "gpu",
    }
    for key, value in (incoming or {}).items():
        if value in (None, "", [], {}):
            continue
        if key == "model_codes":
            from mayabu.catalog.model_codes import normalize_model_code

            left = {
                str(x).upper()
                for x in (out.get("model_codes") or [])
                if normalize_model_code(str(x))
            }
            right_raw = value if isinstance(value, list) else [value]
            right = {
                str(x).upper()
                for x in right_raw
                if normalize_model_code(str(x))
            }
            merged = sorted(left | right)
            if merged != list(out.get("model_codes") or []):
                out["model_codes"] = merged
            continue
        if key in identity_keys and key in out and out[key] not in (None, "", [], {}) and out[key] != value:
            conflicts.append(key)
            continue
        if key not in out or out[key] in (None, "", [], {}):
            out[key] = value
    return out, conflicts


async def enrich_listing(
    listing: dict[str, Any],
    *,
    headless: bool = True,
    debug: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Visit PDP for gallery + model/specs. Does not alter price observation path."""
    platform = str(listing.get("platform") or "")
    url = str(listing.get("listing_url") or "")
    product_id = str(listing["product_id"]) if listing.get("product_id") else None
    ensure_platform_available(platform)
    started = time.perf_counter()
    try:
        from mayabu.monitoring import instrumentation as metrics
    except Exception:
        metrics = None  # type: ignore

    detail = await scrape_product_detail(url, platform=platform, headless=headless, debug=debug)
    latency_ms = int((time.perf_counter() - started) * 1000)

    if detail.status in {"failed", "blocked", "not_found"}:
        record_platform_failure(platform, detail.status, latency_ms)
        if metrics:
            try:
                metrics.ENRICHMENT_TOTAL.inc(platform=platform, result=detail.status)
            except Exception:
                pass
        return {"ok": False, "platform": platform, "status": detail.status, "latency_ms": latency_ms}

    gallery = detail.gallery_urls()
    raw = detail.to_raw_listing(query=detail.title)
    normalized = normalize_raw_listing(raw, platform_hint=platform, query=detail.title or "")
    incoming_specs = (normalized or {}).get("specs") or detail.specs or {}

    gallery_written = 0
    rematch_enqueued = False
    conflicts: list[str] = []
    merged: dict[str, Any] = dict(incoming_specs)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, product_id, specs, image_url, match_status from platform_listings where id = %s::uuid",
                (str(listing["id"]),),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "listing_missing"}
            product_id = str(row["product_id"]) if row.get("product_id") else product_id
            existing_specs = row["specs"] if isinstance(row.get("specs"), dict) else {}
            merged, conflicts = _merge_specs_conservative(existing_specs, incoming_specs)
            primary = gallery[0] if gallery else row.get("image_url")
            cur.execute(
                """
                update platform_listings
                set specs = %s,
                    image_url = coalesce(nullif(%s, ''), image_url),
                    title = coalesce(nullif(%s, ''), title),
                    last_detail_enriched_at = now(),
                    extraction_version = 'v1-enrich-gallery',
                    updated_at = now()
                where id = %s::uuid
                """,
                (
                    Jsonb(merged),
                    primary,
                    detail.title,
                    str(listing["id"]),
                ),
            )
        if product_id and normalized:
            merge_product_specs(
                conn,
                product_id,
                {
                    "title": detail.title,
                    "title_norm": (normalized or {}).get("title_norm"),
                    "specs": merged,
                },
            )
            if gallery:
                gallery_written = upsert_product_images(
                    conn,
                    product_id=product_id,
                    urls=gallery,
                    listing_id=str(listing["id"]),
                    source_platform=platform,
                )
            # Fingerprints from stronger identity
            identity = build_identity(detail.title or "", merged, str(listing.get("category") or "unknown"))
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update product_clusters
                    set exact_fingerprint = coalesce(%s, exact_fingerprint),
                        family_fingerprint = coalesce(%s, family_fingerprint),
                        updated_at = now()
                    where id = %s::uuid
                    """,
                    (identity.exact_fingerprint, identity.family_fingerprint, product_id),
                )
            # Rematch weakly identified siblings when model codes newly available
            if merged.get("model_codes") and not existing_specs.get("model_codes"):
                rematch_enqueued = _enqueue_rematch_candidates(conn, product_id, merged)

    if product_id:
        refresh_product_search_documents([product_id], strict=False)
        get_cache().invalidate_product(product_id)

    record_platform_success(platform, latency_ms)
    result = {
        "ok": True,
        "platform": platform,
        "product_id": product_id,
        "gallery_count": len(gallery),
        "gallery_written": gallery_written,
        "model_codes": merged.get("model_codes"),
        "conflicts": conflicts,
        "rematch_enqueued": rematch_enqueued,
        "latency_ms": latency_ms,
        "run_id": run_id,
    }
    if metrics:
        try:
            metrics.ENRICHMENT_TOTAL.inc(platform=platform, result="completed")
            metrics.ENRICHMENT_DURATION.observe(float(latency_ms), platform=platform)
            if gallery:
                metrics.ENRICHMENT_GALLERY.observe(float(len(gallery)), platform=platform)
            if result.get("model_codes"):
                metrics.ENRICHMENT_MODEL.inc(platform=platform, result="found")
            for _key in conflicts:
                metrics.SPEC_CONFLICT.inc(category=str(listing.get("category") or "unknown"))
        except Exception:
            pass
    return result


def _enqueue_rematch_candidates(conn, product_id: str, specs: dict[str, Any]) -> bool:
    """Enqueue bounded rematch discovery for unmatched listings sharing model codes."""
    codes = [str(c).upper() for c in (specs.get("model_codes") or []) if str(c).strip()]
    if not codes:
        return False
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, platform, listing_url
            from platform_listings
            where match_status in ('unmatched', 'needs_review')
              and listing_url is not null
              and specs->'model_codes' ?| %s
            limit 8
            """,
            (codes,),
        )
        rows = cur.fetchall()
    created = False
    for row in rows:
        create_task(
            conn,
            row["platform"],
            "enrich_listing",
            url=row["listing_url"],
            priority=ENRICH_PRIORITY + 5,
            metadata={
                "source": "rematch_after_enrich",
                "platform_listing_id": str(row["id"]),
                "purpose": "rematch_evidence",
                "anchor_product_id": product_id,
            },
            idempotency_key=f"enrich_listing:rematch:{row['id']}",
            created_by="enrichment",
        )
        created = True
    return created


def query_fingerprint(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()[:32]


__all__ = [
    "ENRICH_PRIORITY",
    "completeness_flags",
    "due_enrichment_candidates",
    "enrich_listing",
    "listing_needs_enrichment",
    "materialize_enrichment",
    "query_fingerprint",
]
