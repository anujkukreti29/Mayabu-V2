from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from psycopg import Connection
from psycopg.errors import UndefinedTable
from psycopg.types.json import Jsonb

from mayabu.domain.matching import assess_product_match
from mayabu.domain.product_identity import build_identity
from mayabu_common import canonical_platform, sha1_text

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def url_hash(url: str) -> str:
    return hashlib.sha1((url or "").encode("utf-8", errors="ignore")).hexdigest()


def _money_key(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value).strip()


def observation_hash(listing_uuid: str, observed_at: Any, price: Any, mrp: Any) -> str:
    """Canonical price observation id used by discovery and refresh ingestion."""
    observed_key = str(observed_at)[:19]
    return sha1_text(
        f"{listing_uuid}|{observed_key}|{_money_key(price)}|{_money_key(mrp)}", 32
    )


def json_value(value: Any) -> Jsonb:
    return Jsonb(value if value is not None else {})


def invalidate_price_caches(
    product_id: str | None,
    *,
    category: str | None = None,
    event_type: str | None = None,
) -> None:
    """Best-effort invalidation for product-scoped price responses.

    Search results intentionally expire by TTL. Blanket search invalidation on
    every price tick destroys cache effectiveness in a write-heavy pipeline.
    ``category`` is retained for API compatibility but is no longer used here.
    """
    del category
    if event_type == "unchanged" or not product_id:
        return
    try:
        from mayabu.search.cache import get_cache

        get_cache().invalidate_product(product_id)
    except Exception:
        pass


def _tag_candidate(row: dict[str, Any], source: str) -> dict[str, Any]:
    """Copy a product row and retain how it entered the candidate pool."""
    tagged = dict(row)
    sources = list(tagged.get("candidate_sources") or [])
    if source not in sources:
        sources.append(source)
    tagged["candidate_sources"] = sources
    return tagged


def _log_repository_warning(event: str, evidence: dict[str, Any] | None = None) -> None:
    """Expose optional matching-tier failures without interrupting ingestion."""

    logger.warning(
        event,
        extra={"event": "repository_warning", "evidence": evidence or {}},
    )


def _coerce_specs(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _duplicate_of_from_specs(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    specs = _coerce_specs(row.get("specs"))
    duplicate_of = specs.get("duplicate_of")
    return str(duplicate_of) if duplicate_of else None


def resolve_product_root(
    conn: Connection, product_id: str, *, max_depth: int = 12
) -> dict[str, Any]:
    """Resolve a product id through duplicate_of pointers to its active root.

    If the input already points to an active product, that row is returned. If a
    duplicate chain is broken or loops, a ValueError is raised instead of moving
    listings onto a hidden cluster.
    """
    current = str(product_id)
    seen: set[str] = set()
    with conn.cursor() as cur:
        for _ in range(max_depth):
            if current in seen:
                raise ValueError(f"Duplicate chain loop detected at product {current}")
            seen.add(current)
            cur.execute("select * from product_clusters where id = %s", (current,))
            row = cur.fetchone()
            if not row:
                raise ValueError(
                    f"Product not found while resolving duplicate chain: {current}"
                )
            if row.get("status") == "active":
                return row
            duplicate_of = _duplicate_of_from_specs(row)
            if not duplicate_of:
                raise ValueError(
                    f"Product {current} is not active and has no duplicate_of root"
                )
            current = duplicate_of
    raise ValueError(f"Duplicate chain too deep for product {product_id}")


def _candidate_source_priority(row: dict[str, Any]) -> int:
    sources = set(row.get("candidate_sources") or [])
    if "exact_fingerprint" in sources:
        return 120
    if "variant_key" in sources:
        return 110
    if "model_code" in sources:
        return 100
    if "family_fingerprint" in sources:
        return 80
    if "brand_family" in sources:
        return 70
    if "listing_title_trigram" in sources:
        return 55
    if "title_trigram" in sources or "title_similarity_relaxed" in sources:
        return 50
    return 10


def list_candidate_products(
    conn: Connection, listing: dict[str, Any], limit: int = 150
) -> list[dict[str, Any]]:
    """Return a unioned candidate pool for product matching.

    v4.4 used a waterfall: model-code candidates OR brand-family candidates OR
    recent products. That made duplicate clusters whenever the first non-empty
    tier was weak or the true match was outside the recency window. v4.5 runs
    identity, family, trigram title, and small recency fallback tiers in parallel,
    de-duplicates them, and lets the unified deterministic matcher choose the best row.
    """
    specs = listing.get("specs") or {}
    model_codes = specs.get("model_codes") or []
    brand = specs.get("brand")
    family = specs.get("family")
    category = listing.get("category") or specs.get("category") or "unknown"
    title_norm = listing.get("title_norm") or listing.get("title") or ""

    candidates: dict[str, dict[str, Any]] = {}
    identity = build_identity(
        listing.get("title") or title_norm,
        specs,
        category,
    )

    def add_rows(rows: list[dict[str, Any]], source: str) -> None:
        for row in rows:
            pid = str(row.get("id"))
            if not pid:
                continue
            if pid in candidates:
                sources = list(candidates[pid].get("candidate_sources") or [])
                if source not in sources:
                    sources.append(source)
                candidates[pid]["candidate_sources"] = sources
                # Preserve the strongest DB-side similarity observed.
                for key in ("title_similarity", "listing_title_similarity"):
                    if row.get(key) is not None:
                        candidates[pid][key] = max(
                            float(candidates[pid].get(key) or 0),
                            float(row.get(key) or 0),
                        )
            else:
                candidates[pid] = _tag_candidate(row, source)

    with conn.cursor() as cur:
        # Deterministic fingerprints are the fastest and safest v5 candidate anchors.
        if identity.exact_fingerprint:
            cur.execute(
                """
                select * from product_clusters
                where status = 'active' and exact_fingerprint = %s
                limit %s
                """,
                (identity.exact_fingerprint, limit),
            )
            add_rows(cur.fetchall(), "exact_fingerprint")

        if identity.family_fingerprint:
            cur.execute(
                """
                select * from product_clusters
                where status = 'active' and family_fingerprint = %s
                order by updated_at desc
                limit %s
                """,
                (identity.family_fingerprint, limit),
            )
            add_rows(cur.fetchall(), "family_fingerprint")

        # Exact variant key is a strong compatibility anchor for pre-v5 rows.
        try:
            from mayabu_db.variant import build_variant_key

            variant_key = build_variant_key(specs, title_norm)
        except Exception:
            variant_key = None
        if variant_key:
            cur.execute(
                """
                select * from product_clusters
                where status = 'active' and variant_key = %s
                limit %s
                """,
                (variant_key, limit),
            )
            add_rows(cur.fetchall(), "variant_key")

        if model_codes:
            cur.execute(
                """
                select * from product_clusters
                where status = 'active'
                  and category = %s
                  and specs ? 'model_codes'
                  and specs->'model_codes' ?| %s
                limit %s
                """,
                (category, model_codes, limit),
            )
            add_rows(cur.fetchall(), "model_code")

        if brand and family:
            cur.execute(
                """
                select * from product_clusters
                where status = 'active'
                  and category = %s
                  and brand = %s
                  and specs->>'family' = %s
                order by updated_at desc
                limit %s
                """,
                (category, brand, family, limit),
            )
            add_rows(cur.fetchall(), "brand_family")

        # Use pg_trgm for relevance-ordered candidate recall. The index already
        # exists in schema.sql, so this is cheap and fixes recency-ordered misses.
        if title_norm and len(title_norm) >= 8:
            try:
                cur.execute(
                    """
                    select p.*, similarity(coalesce(p.title_norm, ''), %s) as title_similarity
                    from product_clusters p
                    where p.status = 'active'
                      and p.category = %s
                      and (%s::text is null or p.brand = %s)
                      and coalesce(p.title_norm, '') %% %s
                    order by title_similarity desc, p.updated_at desc
                    limit 50
                    """,
                    (title_norm, category, brand, brand, title_norm),
                )
                trigram_rows = cur.fetchall()
                add_rows(trigram_rows, "title_trigram")

                # If the % operator is too strict for noisy marketplace titles,
                # allow a relaxed ordered similarity tier at small bounded cost.
                if len(trigram_rows) < 10:
                    cur.execute(
                        """
                        select p.*, similarity(coalesce(p.title_norm, ''), %s) as title_similarity
                        from product_clusters p
                        where p.status = 'active'
                          and p.category = %s
                          and (%s::text is null or p.brand = %s)
                          and similarity(coalesce(p.title_norm, ''), %s) >= 0.18
                        order by title_similarity desc, p.updated_at desc
                        limit 50
                        """,
                        (title_norm, category, brand, brand, title_norm),
                    )
                    add_rows(cur.fetchall(), "title_similarity_relaxed")

                # Matched listing titles are sometimes more complete than the
                # cluster title. Pull products whose listing titles are similar.
                cur.execute(
                    """
                    select distinct on (p.id) p.*, similarity(coalesce(l.title_norm, ''), %s) as listing_title_similarity
                    from platform_listings l
                    join product_clusters p on p.id = l.product_id
                    where p.status = 'active'
                      and l.match_status = 'matched'
                      and l.category = %s
                      and (%s::text is null or p.brand = %s)
                      and coalesce(l.title_norm, '') %% %s
                    order by p.id, listing_title_similarity desc
                    limit 50
                    """,
                    (title_norm, category, brand, brand, title_norm),
                )
                add_rows(cur.fetchall(), "listing_title_trigram")
            except Exception as exc:
                # Keep ingestion alive, but never hide SQL/operator bugs again.
                _log_repository_warning(
                    "trigram_candidate_query_failed",
                    {"category": category, "brand": brand, "error": str(exc)[:500]},
                )

        # Small fallback only, no longer the primary candidate source.
        fallback_limit = max(25, min(50, limit - len(candidates)))
        if fallback_limit > 0:
            cur.execute(
                """
                select * from product_clusters
                where status = 'active'
                  and category = %s
                  and (%s::text is null or brand = %s)
                order by updated_at desc
                limit %s
                """,
                (category, brand, brand, fallback_limit),
            )
            add_rows(cur.fetchall(), "recent_fallback")

    ordered = list(candidates.values())
    ordered.sort(
        key=lambda r: (
            _candidate_source_priority(r),
            max(
                float(r.get("title_similarity") or 0),
                float(r.get("listing_title_similarity") or 0),
            ),
            str(r.get("updated_at") or ""),
        ),
        reverse=True,
    )
    return ordered[:limit]


def get_listing_by_public_id(
    conn: Connection, listing_public_id: str
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            "select * from platform_listings where listing_id = %s",
            (listing_public_id,),
        )
        return cur.fetchone()


def create_product(
    conn: Connection, listing: dict[str, Any], variant_key: str | None
) -> str:
    from mayabu.catalog.title_quality import sanitize_product_title

    specs = listing.get("specs") or {}
    title = sanitize_product_title(listing.get("title")) or (listing.get("title") or "")
    title_norm = sanitize_product_title(listing.get("title_norm")) or (listing.get("title_norm") or "")
    identity = build_identity(
        title or title_norm,
        specs,
        listing.get("category") or specs.get("category") or "unknown",
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into product_clusters(
              category, brand, canonical_title, title_norm, variant_key, specs,
              quality_score, exact_fingerprint, family_fingerprint
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (variant_key)
            do update set
              updated_at = now(),
              canonical_title = case
                when length(excluded.canonical_title) > length(product_clusters.canonical_title)
                then excluded.canonical_title else product_clusters.canonical_title end,
              specs = product_clusters.specs || excluded.specs,
              exact_fingerprint = coalesce(product_clusters.exact_fingerprint, excluded.exact_fingerprint),
              family_fingerprint = coalesce(product_clusters.family_fingerprint, excluded.family_fingerprint)
            returning id
            """,
            (
                listing.get("category"),
                specs.get("brand"),
                title,
                title_norm,
                variant_key,
                json_value(specs),
                listing.get("quality_score") or 0,
                identity.exact_fingerprint,
                identity.family_fingerprint,
            ),
        )
        return str(cur.fetchone()["id"])


def _cpu_specificity(models: Any) -> int:
    values = models if isinstance(models, (list, tuple, set)) else ([models] if models else [])
    best = 0
    for value in values:
        text = str(value or "")
        if text:
            best = max(best, text.count(":"))
    return best


def _cpu_less_specific(incoming: Any, current: Any) -> bool:
    return _cpu_specificity(incoming) < _cpu_specificity(current)


def merge_product_specs(
    conn: Connection, product_id: str, listing: dict[str, Any]
) -> None:
    from mayabu.catalog.title_quality import is_marketing_bullet_title, sanitize_product_title

    specs = dict(listing.get("specs") or {})
    title = sanitize_product_title(listing.get("title")) or (listing.get("title") or "")
    title_norm = sanitize_product_title(listing.get("title_norm")) or (listing.get("title_norm") or "")
    # Prefer cleaner product-like titles over longer SEO filler.
    prefer_incoming = bool(title) and not is_marketing_bullet_title(title)
    with conn.cursor() as cur:
        cur.execute("select specs from product_clusters where id = %s::uuid", (product_id,))
        current_row = cur.fetchone()
        current = current_row.get("specs") if current_row and isinstance(current_row.get("specs"), dict) else {}
        if _cpu_less_specific(specs.get("cpu_models"), current.get("cpu_models")):
            specs.pop("cpu_models", None)
            specs.pop("cpu_series", None)
        cur.execute(
            """
            update product_clusters
            set specs = product_clusters.specs || %s,
                brand = coalesce(product_clusters.brand, %s),
                canonical_title = case
                  when %s and (
                    coalesce(canonical_title, '') = ''
                    or length(%s) between 12 and greatest(length(coalesce(canonical_title, '')), 12)
                    or coalesce(canonical_title, '') ilike '%%best price%%'
                    or coalesce(canonical_title, '') ilike '%%online at%%'
                  ) then %s
                  when length(%s) > length(coalesce(canonical_title, '')) then %s
                  else canonical_title
                end,
                title_norm = case
                  when length(%s) > length(coalesce(title_norm, '')) then %s else title_norm end,
                updated_at = now()
            where id = %s
            """,
            (
                json_value(specs),
                specs.get("brand"),
                prefer_incoming,
                title,
                title,
                title,
                title,
                title_norm,
                title_norm,
                product_id,
            ),
        )


def upsert_platform_listing(
    conn: Connection,
    listing: dict[str, Any],
    product_id: str | None,
    match_confidence: float,
    match_method: str,
    match_evidence: dict[str, Any],
    quality_flags: list[dict[str, Any]],
) -> tuple[str, bool]:
    public_id = listing["listing_id"]
    stock_status = listing.get("stock_status") or (
        "in_stock" if listing.get("price") is not None else "unknown"
    )
    match_status = (
        "matched"
        if product_id and match_method != "needs_manual_review"
        else ("needs_review" if match_method == "needs_manual_review" else "unmatched")
    )
    with conn.cursor() as cur:
        cur.execute(
            "select id, current_price from platform_listings where listing_id = %s",
            (public_id,),
        )
        before = cur.fetchone()
        cur.execute(
            """
            insert into platform_listings(
              product_id, platform, listing_id, native_id, listing_url, listing_url_hash,
              title, title_norm, image_url, category, specs, current_price, current_mrp,
              current_discount_pct, currency, stock_status, seller_name, match_status,
              match_confidence, match_method, match_evidence, quality_flags,
              first_seen_at, last_seen_at, last_price_change_at
            ) values (
              %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s,
              %s, %s, %s, %s,
              now(), %s, now()
            )
            on conflict (listing_id) do update set
              product_id = coalesce(excluded.product_id, platform_listings.product_id),
              native_id = coalesce(excluded.native_id, platform_listings.native_id),
              listing_url = excluded.listing_url,
              listing_url_hash = excluded.listing_url_hash,
              title = excluded.title,
              title_norm = excluded.title_norm,
              image_url = coalesce(nullif(excluded.image_url, ''), platform_listings.image_url),
              category = excluded.category,
              specs = platform_listings.specs || excluded.specs,
              current_price = excluded.current_price,
              current_mrp = excluded.current_mrp,
              current_discount_pct = excluded.current_discount_pct,
              currency = coalesce(nullif(excluded.currency, ''), platform_listings.currency, 'INR'),
              stock_status = excluded.stock_status,
              seller_name = coalesce(excluded.seller_name, platform_listings.seller_name),
              match_status = case
                when excluded.match_status = 'matched' then 'matched'
                when platform_listings.match_status = 'matched' then platform_listings.match_status
                else excluded.match_status end,
              match_confidence = greatest(platform_listings.match_confidence, excluded.match_confidence),
              match_method = coalesce(excluded.match_method, platform_listings.match_method),
              match_evidence = platform_listings.match_evidence || excluded.match_evidence,
              quality_flags = excluded.quality_flags,
              last_seen_at = excluded.last_seen_at,
              last_price_change_at = case
                when platform_listings.current_price is distinct from excluded.current_price then now()
                else platform_listings.last_price_change_at end,
              updated_at = now()
            returning id
            """,
            (
                product_id,
                canonical_platform(listing.get("platform") or "unknown"),
                public_id,
                listing.get("native_id"),
                listing.get("url") or "",
                url_hash(listing.get("url") or ""),
                listing.get("title") or "",
                listing.get("title_norm") or "",
                listing.get("image") or "",
                listing.get("category") or "unknown",
                json_value(listing.get("specs") or {}),
                listing.get("price"),
                listing.get("mrp"),
                listing.get("discount_pct"),
                listing.get("currency") or "INR",
                stock_status,
                listing.get("seller_name"),
                match_status,
                float(match_confidence or 0),
                match_method,
                json_value(match_evidence or {}),
                Jsonb(quality_flags or []),
                listing.get("scraped_at"),
            ),
        )
        listing_uuid = str(cur.fetchone()["id"])
        created = before is None
    return listing_uuid, created


def insert_price_observation(
    conn: Connection,
    listing_uuid: str,
    listing_public_id: str,
    product_id: str | None,
    listing: dict[str, Any],
    run_id: str | None,
    quality_flags: list[dict[str, Any]],
) -> bool:
    observed_at = listing.get("scraped_at") or utc_now().isoformat()
    ohash = observation_hash(
        listing_uuid, observed_at, listing.get("price"), listing.get("mrp")
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            select price, stock_status from price_observations
            where listing_id = %s and price is not null
            order by observed_at desc
            limit 1
            """,
            (listing_uuid,),
        )
        prev = cur.fetchone()
        event = "initial"
        if prev and listing.get("price") is not None:
            previous_price = prev.get("price")
            if previous_price is None:
                event = "initial"
            elif listing["price"] < previous_price:
                event = "drop"
            elif listing["price"] > previous_price:
                event = "rise"
            else:
                event = "unchanged"
        stock_status = listing.get("stock_status") or (
            "in_stock" if listing.get("price") is not None else "unknown"
        )
        cur.execute(
            """
            insert into price_observations(
              observation_hash, listing_id, product_id, platform, observed_at,
              price, mrp, discount_pct, currency, stock_status, seller_name, source_run_id,
              event_type, quality_flags
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (observation_hash) do nothing
            """,
            (
                ohash,
                listing_uuid,
                product_id,
                canonical_platform(listing.get("platform") or "unknown"),
                observed_at,
                listing.get("price"),
                listing.get("mrp"),
                listing.get("discount_pct"),
                listing.get("currency") or "INR",
                stock_status,
                listing.get("seller_name"),
                run_id,
                event,
                Jsonb(quality_flags or []),
            ),
        )
        inserted = cur.rowcount == 1
        if inserted:
            cur.execute(
                "update platform_listings set observation_count = observation_count + 1 where id = %s",
                (listing_uuid,),
            )
    if inserted:
        invalidate_price_caches(
            product_id, category=listing.get("category"), event_type=event
        )
    return inserted


def insert_raw_item(
    conn: Connection,
    run_id: str | None,
    task_id: str | None,
    platform: str,
    query: str | None,
    raw: dict[str, Any],
    listing_public_id: str | None,
    parse_status: str = "pending",
    parse_error: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into raw_scrape_items(run_id, task_id, platform, query, listing_id, raw_payload, parse_status, parse_error)
            values (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                run_id,
                task_id,
                canonical_platform(platform),
                query,
                listing_public_id,
                Jsonb(raw),
                parse_status,
                parse_error,
            ),
        )


def add_review_item(
    conn: Connection,
    listing_uuid: str,
    candidate_product_id: str | None,
    score: float,
    evidence: dict[str, Any],
) -> None:
    if not candidate_product_id:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into review_queue(listing_id, candidate_product_id, score, evidence)
            values (%s,%s,%s,%s)
            on conflict (listing_id, candidate_product_id, status) do nothing
            """,
            (listing_uuid, candidate_product_id, score, Jsonb(evidence or {})),
        )


def add_duplicate_review_item(
    conn: Connection,
    source_product_id: str,
    candidate_product_id: str,
    score: float,
    evidence: dict[str, Any],
) -> None:
    """Queue a possible product-cluster duplicate for review.

    listing_id is intentionally null for product-vs-product reviews. v4.5 adds
    review_type/source_product_id so the same review_queue can power both listing
    assignment and cluster merge review.
    """
    if (
        not source_product_id
        or not candidate_product_id
        or source_product_id == candidate_product_id
    ):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into review_queue(review_type, source_product_id, listing_id, candidate_product_id, score, evidence)
            select 'duplicate_product', %s, null, %s, %s, %s
            where not exists (
                select 1 from review_queue rq
                where rq.review_type = 'duplicate_product'
                  and (
                    (rq.source_product_id = %s and rq.candidate_product_id = %s)
                    or (rq.source_product_id = %s and rq.candidate_product_id = %s)
                  )
                  and rq.status in ('needs_review', 'rejected', 'ignored')
            )
            on conflict do nothing
            """,
            (
                source_product_id,
                candidate_product_id,
                score,
                Jsonb(evidence or {}),
                source_product_id,
                candidate_product_id,
                candidate_product_id,
                source_product_id,
            ),
        )


def _merge_json_specs(
    primary: dict[str, Any], duplicate: dict[str, Any]
) -> dict[str, Any]:
    """Merge specs conservatively, preserving primary values and unioning lists."""
    merged = dict(primary or {})
    for key, value in (duplicate or {}).items():
        if value is None or value == "" or value == []:
            continue
        current = merged.get(key)
        if current is None or current == "" or current == []:
            merged[key] = value
        elif isinstance(current, list) or isinstance(value, list):
            cur_list = current if isinstance(current, list) else [current]
            val_list = value if isinstance(value, list) else [value]
            seen: set[str] = set()
            union: list[Any] = []
            for item in cur_list + val_list:
                marker = str(item).lower()
                if item is not None and marker not in seen:
                    union.append(item)
                    seen.add(marker)
            merged[key] = union
        elif current == value:
            merged[key] = current
        else:
            # Keep the primary scalar to avoid silently corrupting identity. Store
            # disagreement for later review without blocking the merge.
            conflicts = dict(merged.get("merge_conflicts") or {})
            conflicts[key] = sorted({str(current), str(value)})
            merged["merge_conflicts"] = conflicts
    return merged


def merge_products(
    conn: Connection,
    primary_product_id: str,
    duplicate_product_id: str,
    *,
    reviewer_note: str | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    """Merge an already-split product cluster into its active root cluster.

    v4.5.1 hardens v4.5 edge cases:
    - primary ids that are already duplicates are resolved to their active root;
    - duplicate chains never move listings onto hidden products;
    - price alerts move with the duplicate product;
    - merge rows remain idempotent and cache invalidation stays scoped.
    """
    if str(primary_product_id) == str(duplicate_product_id):
        raise ValueError("primary_product_id and duplicate_product_id must differ")

    requested_primary_id = str(primary_product_id)
    requested_duplicate_id = str(duplicate_product_id)

    primary_root = resolve_product_root(conn, requested_primary_id)
    primary_product_id = str(primary_root["id"])

    if primary_product_id == requested_duplicate_id:
        return {
            "merged": False,
            "reason": "duplicate_already_points_to_primary_root",
            "primary_product_id": primary_product_id,
            "duplicate_product_id": requested_duplicate_id,
        }

    with conn.cursor() as cur:
        cur.execute(
            """
            select * from product_clusters
            where id in (%s, %s)
            order by id
            for update
            """,
            (primary_product_id, requested_duplicate_id),
        )
        rows = cur.fetchall()
        by_id = {str(row["id"]): row for row in rows}
        primary = by_id.get(primary_product_id)
        duplicate = by_id.get(requested_duplicate_id)
        if not primary or not duplicate:
            raise ValueError("primary or duplicate product not found")
        if primary.get("status") != "active":
            raise ValueError(
                f"Resolved primary product is not active: {primary_product_id}"
            )
        if duplicate.get("status") == "duplicate":
            return {
                "merged": False,
                "reason": "duplicate_already_marked",
                "primary_product_id": primary_product_id,
                "duplicate_product_id": requested_duplicate_id,
                "duplicate_of": _duplicate_of_from_specs(duplicate),
            }
        if duplicate.get("status") != "active":
            raise ValueError(
                f"Duplicate product is not active: {requested_duplicate_id}"
            )

        # Capture dates before deleting/rebuilding product rollups.
        cur.execute(
            """
            select distinct date from daily_listing_prices where product_id in (%s, %s)
            union
            select distinct date(observed_at) from price_observations where product_id in (%s, %s)
            order by 1
            """,
            (
                primary_product_id,
                requested_duplicate_id,
                primary_product_id,
                requested_duplicate_id,
            ),
        )
        affected_dates = [
            row["date"] for row in cur.fetchall() if row.get("date") is not None
        ]

        primary_specs = _coerce_specs(primary.get("specs"))
        duplicate_specs = _coerce_specs(duplicate.get("specs"))
        merged_specs = _merge_json_specs(primary_specs, duplicate_specs)

        primary_title = primary.get("canonical_title") or ""
        duplicate_title = duplicate.get("canonical_title") or ""
        canonical_title = (
            duplicate_title
            if len(duplicate_title) > len(primary_title)
            else primary_title
        )
        title_norm = (
            duplicate.get("title_norm")
            if len(str(duplicate.get("title_norm") or ""))
            > len(str(primary.get("title_norm") or ""))
            else primary.get("title_norm")
        )

        cur.execute(
            """
            update platform_listings
            set product_id = %s,
                match_status = 'matched',
                match_method = 'cluster_merge',
                match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s,
                updated_at = now()
            where product_id = %s
            """,
            (
                primary_product_id,
                Jsonb(
                    {
                        "merged_from_product_id": requested_duplicate_id,
                        "merge_source": source,
                    }
                ),
                requested_duplicate_id,
            ),
        )
        listings_moved = cur.rowcount

        cur.execute(
            "update price_observations set product_id = %s where product_id = %s",
            (primary_product_id, requested_duplicate_id),
        )
        observations_moved = cur.rowcount

        cur.execute(
            "update daily_listing_prices set product_id = %s where product_id = %s",
            (primary_product_id, requested_duplicate_id),
        )
        daily_listing_rows_moved = cur.rowcount

        cur.execute(
            "update price_alerts set product_id = %s where product_id = %s",
            (primary_product_id, requested_duplicate_id),
        )
        price_alerts_moved = cur.rowcount

        cur.execute(
            "delete from daily_product_prices where product_id in (%s, %s)",
            (primary_product_id, requested_duplicate_id),
        )

        cur.execute(
            """
            update product_clusters
            set specs = %s,
                brand = coalesce(product_clusters.brand, %s),
                canonical_title = %s,
                title_norm = coalesce(%s, product_clusters.title_norm),
                updated_at = now()
            where id = %s
            """,
            (
                json_value(merged_specs),
                duplicate.get("brand"),
                canonical_title,
                title_norm,
                primary_product_id,
            ),
        )

        cur.execute(
            """
            update product_clusters
            set status = 'duplicate',
                quality_score = 0,
                updated_at = now(),
                specs = specs || %s
            where id = %s
            """,
            (
                Jsonb(
                    {"duplicate_of": str(primary_product_id), "merge_source": source}
                ),
                requested_duplicate_id,
            ),
        )

        cur.execute(
            """
            insert into product_merge_log(primary_product_id, duplicate_product_id, source, reviewer_note, evidence)
            values (%s, %s, %s, %s, %s)
            on conflict do nothing
            """,
            (
                primary_product_id,
                requested_duplicate_id,
                source,
                reviewer_note,
                Jsonb(
                    {
                        "requested_primary_product_id": requested_primary_id,
                        "resolved_primary_product_id": primary_product_id,
                        "affected_dates": [str(d) for d in affected_dates],
                        "price_alerts_moved": price_alerts_moved,
                    }
                ),
            ),
        )

    # Rebuild product-day rollups after reassignment. Use the existing single-day
    # rollup function so the logic stays in one place.
    for date_value in affected_dates:
        refresh_daily_product_price(conn, primary_product_id, date_expr=str(date_value))

    invalidate_price_caches(
        primary_product_id, category=primary.get("category"), event_type="merge"
    )
    invalidate_price_caches(
        requested_duplicate_id, category=duplicate.get("category"), event_type="merge"
    )

    return {
        "merged": True,
        "primary_product_id": str(primary_product_id),
        "requested_primary_product_id": requested_primary_id,
        "duplicate_product_id": str(requested_duplicate_id),
        "listings_moved": listings_moved,
        "observations_moved": observations_moved,
        "daily_listing_rows_moved": daily_listing_rows_moved,
        "price_alerts_moved": price_alerts_moved,
        "rollup_dates_rebuilt": len(affected_dates),
    }


def _product_as_listing(row: dict[str, Any]) -> dict[str, Any]:
    specs = row.get("specs") or {}
    if isinstance(specs, str):
        specs = json.loads(specs)
    return {
        "title": row.get("canonical_title") or "",
        "title_norm": row.get("title_norm") or row.get("canonical_title") or "",
        "category": row.get("category"),
        "specs": specs,
    }


def _row_as_match_product(row: dict[str, Any]) -> dict[str, Any]:
    specs = _coerce_specs(row.get("specs"))
    return {
        "product_id": str(row.get("id")),
        "category": row.get("category"),
        "canonical_title": row.get("canonical_title") or "",
        "title_norm": row.get("title_norm") or row.get("canonical_title") or "",
        "brand": row.get("brand"),
        "specs": specs,
    }


def _safe_auto_merge(
    score: float, evidence: dict[str, Any], left: dict[str, Any], right: dict[str, Any]
) -> bool:
    """Return True only for high-confidence duplicate product clusters.

    This is intentionally stricter than the review queue. It auto-merges only
    when identity signals are strong enough to improve UX without risking false
    product merges.
    """
    if score < 92:
        return False
    if (
        evidence.get("identity_rule") == "deterministic_exact"
        and evidence.get("deterministic_relation") == "exact"
    ):
        return True
    if evidence.get("reject"):
        return False
    if evidence.get("weak_identity"):
        return False

    if left.get("category") != right.get("category"):
        return False
    if (left.get("brand") or "") != (right.get("brand") or ""):
        return False

    left_variant = left.get("variant_key")
    right_variant = right.get("variant_key")
    if left_variant and left_variant == right_variant:
        return True

    exact_signals = sum(
        1
        for key in [
            "family",
            "model_code",
            "cpu_model",
            "ram_gb",
            "storage_gb",
            "screen_inch",
            "gpu",
        ]
        if key in evidence
    )

    if "model_code" in evidence and exact_signals >= 2:
        return True

    # Marketplace titles often omit exact SKU, but same brand + family + CPU +
    # RAM + storage + close screen size is strong enough for laptop comparison.
    if exact_signals >= 5 and float(evidence.get("title_jaccard") or 0) >= 0.38:
        return True

    # Very high score with at least four non-text signals is also safe.
    if (
        score >= 98
        and exact_signals >= 4
        and float(evidence.get("title_sequence") or 0) >= 0.55
    ):
        return True

    return False


def auto_merge_duplicate_products(
    conn: Connection,
    *,
    limit: int = 100,
    scan_limit: int = 1500,
    min_score: float = 92.0,
) -> dict[str, Any]:
    """Auto-merge only safe duplicate product clusters.

    This is designed for local testing and scheduled maintenance after discovery
    runs. It fixes the UX issue where the same product stays as separate
    one-platform cards, while still avoiding risky fuzzy-only merges.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, category, brand, canonical_title, title_norm, variant_key, specs, updated_at
            from product_clusters
            where status = 'active'
            order by updated_at desc
            limit %s
            """,
            (max(1, int(scan_limit)),),
        )
        rows = cur.fetchall()

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("category") or "unknown"),
            str(row.get("brand") or "_unknown"),
        )
        groups.setdefault(key, []).append(row)

    candidates: list[tuple[float, str, str, dict[str, Any]]] = []
    for group_rows in groups.values():
        if len(group_rows) < 2:
            continue
        # Bound pairwise work for large catalogues. Matching should be run often,
        # not as an unbounded blocking search request.
        group_rows = group_rows[:250]
        for i, left in enumerate(group_rows):
            for right in group_rows[i + 1 :]:
                assessment = assess_product_match(
                    _product_as_listing(left), _row_as_match_product(right)
                )
                score, evidence = assessment.score, assessment.evidence
                if not assessment.merge_allowed or score < min_score:
                    continue
                if not _safe_auto_merge(score, evidence, left, right):
                    continue
                # Keep the older/stronger-looking cluster as primary. If both are
                # similar, choose the title with more detail.
                left_title_len = len(str(left.get("canonical_title") or ""))
                right_title_len = len(str(right.get("canonical_title") or ""))
                primary = str(left["id"])
                duplicate = str(right["id"])
                if right_title_len > left_title_len + 30:
                    primary, duplicate = duplicate, primary
                candidates.append((float(score), primary, duplicate, evidence))

    candidates.sort(key=lambda item: item[0], reverse=True)
    merged = 0
    skipped = 0
    results: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for score, primary, duplicate, evidence in candidates:
        if merged >= limit:
            break
        pair = tuple(sorted((primary, duplicate)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        try:
            result = merge_products(
                conn,
                primary,
                duplicate,
                reviewer_note=f"auto merge score={score:.2f}",
                source="auto_merge_safe_duplicate",
            )
            if result.get("merged"):
                merged += 1
            else:
                skipped += 1
            results.append({"score": round(score, 2), "evidence": evidence, **result})
        except Exception as exc:
            skipped += 1
            results.append(
                {
                    "score": round(score, 2),
                    "primary_product_id": primary,
                    "duplicate_product_id": duplicate,
                    "error": str(exc)[:300],
                }
            )

    return {
        "scanned_products": len(rows),
        "candidate_pairs": len(candidates),
        "merged": merged,
        "skipped": skipped,
        "results": results[:20],
    }


def find_duplicate_product_candidates(
    conn: Connection, limit: int = 100, min_score: float = 70.0
) -> int:
    """Find likely duplicate clusters and queue product-level review items."""
    queued = 0
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                select p1.*, p2.id as candidate_id, p2.category as candidate_category,
                       p2.brand as candidate_brand, p2.canonical_title as candidate_title,
                       p2.title_norm as candidate_title_norm, p2.specs as candidate_specs,
                       similarity(coalesce(p1.title_norm, ''), coalesce(p2.title_norm, '')) as db_title_similarity
                from product_clusters p1
                join product_clusters p2
                  on p1.id < p2.id
                 and p1.status = 'active'
                 and p2.status = 'active'
                 and p1.category = p2.category
                 and coalesce(p1.brand, '') = coalesce(p2.brand, '')
                where coalesce(p1.title_norm, '') %% coalesce(p2.title_norm, '')
                  and not exists (
                    select 1 from review_queue rq
                    where rq.review_type = 'duplicate_product'
                      and (
                        (rq.source_product_id = p1.id and rq.candidate_product_id = p2.id)
                        or (rq.source_product_id = p2.id and rq.candidate_product_id = p1.id)
                      )
                      and rq.status in ('needs_review', 'rejected', 'ignored')
                  )
                order by db_title_similarity desc, p1.updated_at desc
                limit %s
                """,
                (max(limit * 3, limit),),
            )
            rows = cur.fetchall()
        except Exception as exc:
            _log_repository_warning(
                "duplicate_product_finder_query_failed",
                {"limit": limit, "min_score": min_score, "error": str(exc)[:500]},
            )
            return 0

    for row in rows:
        source = dict(row)
        candidate = {
            "id": row["candidate_id"],
            "category": row["candidate_category"],
            "brand": row["candidate_brand"],
            "canonical_title": row["candidate_title"],
            "title_norm": row["candidate_title_norm"],
            "specs": row["candidate_specs"],
        }
        assessment = assess_product_match(
            _product_as_listing(source),
            {
                "product_id": str(candidate["id"]),
                "category": candidate["category"],
                "canonical_title": candidate["canonical_title"],
                "title_norm": candidate["title_norm"],
                "brand": candidate["brand"],
                "specs": candidate["specs"] or {},
            },
        )
        score, evidence = assessment.score, assessment.evidence
        if (assessment.merge_allowed or assessment.needs_review) and score >= min_score:
            evidence = {
                **evidence,
                "db_title_similarity": round(
                    float(row.get("db_title_similarity") or 0), 3
                ),
            }
            add_duplicate_review_item(
                conn, str(row["id"]), str(candidate["id"]), score, evidence
            )
            queued += 1
            if queued >= limit:
                break
    return queued


def approve_review_item(
    conn: Connection, review_id: str, note: str | None = None
) -> dict[str, Any]:
    """Approve a listing-match or duplicate-product review item."""
    with conn.cursor() as cur:
        cur.execute(
            "select * from review_queue where id = %s and status = 'needs_review' for update",
            (review_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Review item not found or already resolved")
        review_type = row.get("review_type") or "listing_match"

    if review_type == "duplicate_product":
        result = merge_products(
            conn,
            str(row["source_product_id"]),
            str(row["candidate_product_id"]),
            reviewer_note=note,
            source="review_queue",
        )
        with conn.cursor() as cur:
            cur.execute(
                "update review_queue set status = 'approved', reviewer_note = %s, reviewed_at = now() where id = %s",
                (note, review_id),
            )
        return {"review_id": review_id, "action": "approved_duplicate_merge", **result}

    with conn.cursor() as cur:
        cur.execute(
            """
            update platform_listings
            set product_id = %s, match_status = 'matched', match_method = 'manual_review_approved',
                match_confidence = greatest(match_confidence, coalesce(%s, 0)), updated_at = now()
            where id = %s
            """,
            (row["candidate_product_id"], row["score"], row["listing_id"]),
        )
        cur.execute(
            "update price_observations set product_id = %s where listing_id = %s and product_id is null",
            (row["candidate_product_id"], row["listing_id"]),
        )
        cur.execute(
            "update review_queue set status = 'approved', reviewer_note = %s, reviewed_at = now() where id = %s",
            (note, review_id),
        )
    refresh_daily_product_price(conn, str(row["candidate_product_id"]))
    invalidate_price_caches(
        str(row["candidate_product_id"]), event_type="review_approve"
    )
    return {"review_id": review_id, "action": "approved_listing_match"}


def reject_review_item(
    conn: Connection, review_id: str, note: str | None = None
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            update review_queue set status = 'rejected', reviewer_note = %s, reviewed_at = now()
            where id = %s and status = 'needs_review'
            """,
            (note, review_id),
        )
        if cur.rowcount != 1:
            raise ValueError("Review item not found or already resolved")
    return {"review_id": review_id, "action": "rejected"}


def add_anomaly(
    conn: Connection,
    severity: str,
    event_type: str,
    message: str,
    platform: str | None = None,
    product_id: str | None = None,
    listing_id: str | None = None,
    run_id: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into anomaly_events(severity, event_type, platform, product_id, listing_id, run_id, message, evidence)
            values (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                severity,
                event_type,
                canonical_platform(platform or "") if platform else None,
                product_id,
                listing_id,
                run_id,
                message,
                Jsonb(evidence or {}),
            ),
        )


def refresh_daily_listing_price(
    conn: Connection, listing_uuid: str, date_expr: str | None = None
) -> None:
    """
    Refresh daily listing price rollup for one listing.

    Important PostgreSQL fix:
    product_id is UUID, so we cannot use max(product_id).
    PostgreSQL does not support max(uuid). Instead, we pick the latest
    product_id/platform using array_agg(... order by observed_at desc)[1].
    """
    params: tuple[Any, ...]

    with conn.cursor() as cur:
        if date_expr is None:
            params = (listing_uuid,)

            cur.execute(
                """
                insert into daily_listing_prices(
                    listing_id,
                    product_id,
                    platform,
                    date,
                    open_price,
                    close_price,
                    min_price,
                    max_price,
                    last_mrp,
                    observations_count,
                    in_stock_count
                )
                select
                    listing_id,
                    (array_agg(product_id order by observed_at desc))[1],
                    (array_agg(platform order by observed_at desc))[1],
                    date(observed_at),
                    (array_agg(price order by observed_at asc))[1],
                    (array_agg(price order by observed_at desc))[1],
                    min(price),
                    max(price),
                    (array_agg(mrp order by observed_at desc))[1],
                    count(*),
                    count(*) filter (where stock_status = 'in_stock')
                from price_observations
                where listing_id = %s
                  and price is not null
                group by listing_id, date(observed_at)
                on conflict (listing_id, date) do update set
                    product_id = excluded.product_id,
                    platform = excluded.platform,
                    open_price = excluded.open_price,
                    close_price = excluded.close_price,
                    min_price = excluded.min_price,
                    max_price = excluded.max_price,
                    last_mrp = excluded.last_mrp,
                    observations_count = excluded.observations_count,
                    in_stock_count = excluded.in_stock_count,
                    updated_at = now()
                """,
                params,
            )

        else:
            params = (date_expr, listing_uuid, date_expr)

            cur.execute(
                """
                insert into daily_listing_prices(
                    listing_id,
                    product_id,
                    platform,
                    date,
                    open_price,
                    close_price,
                    min_price,
                    max_price,
                    last_mrp,
                    observations_count,
                    in_stock_count
                )
                select
                    listing_id,
                    (array_agg(product_id order by observed_at desc))[1],
                    (array_agg(platform order by observed_at desc))[1],
                    %s::date,
                    (array_agg(price order by observed_at asc))[1],
                    (array_agg(price order by observed_at desc))[1],
                    min(price),
                    max(price),
                    (array_agg(mrp order by observed_at desc))[1],
                    count(*),
                    count(*) filter (where stock_status = 'in_stock')
                from price_observations
                where listing_id = %s
                  and date(observed_at) = %s::date
                  and price is not null
                group by listing_id
                on conflict (listing_id, date) do update set
                    product_id = excluded.product_id,
                    platform = excluded.platform,
                    open_price = excluded.open_price,
                    close_price = excluded.close_price,
                    min_price = excluded.min_price,
                    max_price = excluded.max_price,
                    last_mrp = excluded.last_mrp,
                    observations_count = excluded.observations_count,
                    in_stock_count = excluded.in_stock_count,
                    updated_at = now()
                """,
                params,
            )


def refresh_daily_product_price(
    conn: Connection, product_id: str, date_expr: Any | None = None
) -> None:
    """Incrementally refresh one product/day rollup.

    Source of truth is daily_product_platform_prices (one row per platform).
    Legacy amazon_price/flipkart_price/... columns remain as compatibility
    surfaces for older API consumers.
    """
    with conn.cursor() as cur:
        cur.execute("savepoint daily_platform_prices")
        try:
            cur.execute(
            """
            with target as (
              select %s::uuid as product_id, coalesce(%s::date, current_date) as date
            ), platform_day as (
              select d.product_id, d.date, d.platform,
                     min(d.min_price) as min_price,
                     max(d.max_price) as max_price,
                     coalesce(sum(d.observations_count), 0)::integer as observations_count
              from daily_listing_prices d
              join target t on t.product_id = d.product_id and t.date = d.date
              group by d.product_id, d.date, d.platform
            )
            insert into daily_product_platform_prices(
              product_id, date, platform, min_price, max_price, observations_count, updated_at
            )
            select product_id, date, platform, min_price, max_price, observations_count, now()
            from platform_day
            on conflict (product_id, date, platform) do update set
              min_price = excluded.min_price,
              max_price = excluded.max_price,
              observations_count = excluded.observations_count,
              updated_at = now()
            """,
            (product_id, date_expr),
            )
        except UndefinedTable:
            cur.execute("rollback to savepoint daily_platform_prices")
            logger.warning(
                "daily_product_platform_prices missing; skipping platform-day rollup"
            )
        else:
            cur.execute("release savepoint daily_platform_prices")
        cur.execute("savepoint daily_product_prices")
        try:
            cur.execute(
            """
            with target as (
              select %s::uuid as product_id, coalesce(%s::date, current_date) as date
            ), day_row as (
              select p.product_id, p.date,
                     min(p.min_price) filter (where p.platform = 'amazon') as amazon_price,
                     min(p.min_price) filter (where p.platform = 'flipkart') as flipkart_price,
                     min(p.min_price) filter (where p.platform = 'croma') as croma_price,
                     min(p.min_price) filter (where p.platform = 'reliancedigital') as reliancedigital_price,
                     count(distinct p.platform) filter (where p.min_price is not null) as platform_count,
                     coalesce(sum(p.observations_count), 0)::integer as observations_count
              from daily_product_platform_prices p
              join target t on t.product_id = p.product_id and t.date = p.date
              group by p.product_id, p.date
            ), best_row as (
              select d.*, b.best_price_calc, b.best_platform_calc
              from day_row d
              left join lateral (
                select min_price as best_price_calc, platform as best_platform_calc
                from daily_product_platform_prices p
                where p.product_id = d.product_id and p.date = d.date and p.min_price is not null
                order by p.min_price asc, p.platform asc
                limit 1
              ) b on true
            ), final_row as (
              select b.*,
                     least(
                       coalesce((
                         select dpp.all_time_low_so_far
                         from daily_product_prices dpp
                         where dpp.product_id = b.product_id and dpp.date < b.date
                         order by dpp.date desc
                         limit 1
                       ), 999999999),
                       coalesce(b.best_price_calc, 999999999)
                     ) as all_time_low_calc
              from best_row b
            )
            insert into daily_product_prices(
              product_id, date, best_price, best_platform, amazon_price, flipkart_price,
              croma_price, reliancedigital_price, platform_count, observations_count,
              all_time_low_so_far
            )
            select product_id, date,
                   best_price_calc,
                   best_platform_calc,
                   amazon_price, flipkart_price, croma_price, reliancedigital_price,
                   platform_count, observations_count,
                   nullif(all_time_low_calc, 999999999)
            from final_row
            on conflict (product_id, date) do update set
              best_price = excluded.best_price,
              best_platform = excluded.best_platform,
              amazon_price = excluded.amazon_price,
              flipkart_price = excluded.flipkart_price,
              croma_price = excluded.croma_price,
              reliancedigital_price = excluded.reliancedigital_price,
              platform_count = excluded.platform_count,
              observations_count = excluded.observations_count,
              all_time_low_so_far = least(
                coalesce(daily_product_prices.all_time_low_so_far, excluded.all_time_low_so_far),
                coalesce(excluded.all_time_low_so_far, daily_product_prices.all_time_low_so_far)
              ),
              updated_at = now()
            """,
            (product_id, date_expr),
            )
        except UndefinedTable:
            cur.execute("rollback to savepoint daily_product_prices")
            logger.warning(
                "daily_product_prices missing; observation ingest continues without product-day rollup"
            )
        else:
            cur.execute("release savepoint daily_product_prices")


def rebuild_daily_product_prices(
    conn: Connection, product_id: str | None = None
) -> int:
    """Rebuild daily product rollups with a full historical window scan.

    Use this from maintenance after backfills, manual corrections, or nightly
    repair jobs. The normal ingest path should call refresh_daily_product_price().
    """
    with conn.cursor() as cur:
        cur.execute(
            "delete from daily_product_platform_prices where %s::uuid is null or product_id = %s::uuid",
            (product_id, product_id),
        )
        cur.execute(
            "delete from daily_product_prices where %s::uuid is null or product_id = %s::uuid",
            (product_id, product_id),
        )
        cur.execute(
            """
            insert into daily_product_platform_prices(
              product_id, date, platform, min_price, max_price, observations_count, updated_at
            )
            select product_id, date, platform,
                   min(min_price), max(max_price),
                   coalesce(sum(observations_count), 0)::integer, now()
            from daily_listing_prices
            where %s::uuid is null or product_id = %s::uuid
            group by product_id, date, platform
            """,
            (product_id, product_id),
        )
        cur.execute(
            """
            with day_rows as (
              select product_id, date,
                     min(min_price) filter (where platform = 'amazon') as amazon_price,
                     min(min_price) filter (where platform = 'flipkart') as flipkart_price,
                     min(min_price) filter (where platform = 'croma') as croma_price,
                     min(min_price) filter (where platform = 'reliancedigital') as reliancedigital_price,
                     count(distinct platform) filter (where min_price is not null) as platform_count,
                     coalesce(sum(observations_count), 0)::integer as observations_count
              from daily_product_platform_prices
              where %s::uuid is null or product_id = %s::uuid
              group by product_id, date
            ), best_rows as (
              select d.*, b.best_price_calc, b.best_platform_calc
              from day_rows d
              left join lateral (
                select min_price as best_price_calc, platform as best_platform_calc
                from daily_product_platform_prices p
                where p.product_id = d.product_id and p.date = d.date and p.min_price is not null
                order by p.min_price asc, p.platform asc
                limit 1
              ) b on true
            ), final_rows as (
              select *,
                     min(best_price_calc) over (
                       partition by product_id order by date
                       rows between unbounded preceding and current row
                     ) as all_time_low_calc
              from best_rows
            )
            insert into daily_product_prices(
              product_id, date, best_price, best_platform, amazon_price, flipkart_price,
              croma_price, reliancedigital_price, platform_count, observations_count,
              all_time_low_so_far
            )
            select product_id, date,
                   best_price_calc,
                   best_platform_calc,
                   amazon_price, flipkart_price, croma_price, reliancedigital_price,
                   platform_count, observations_count, all_time_low_calc
            from final_rows
            """,
            (product_id, product_id),
        )
        return int(cur.rowcount or 0)
