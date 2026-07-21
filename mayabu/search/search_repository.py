"""Read-optimized search and product retrieval for Mayabu v5.1."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from psycopg.types.json import Jsonb

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection
from mayabu.search.query_parser import ParsedQuery
from mayabu.search.ranker import rank_products

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _source_relation() -> tuple[str, bool]:
    """Resolve the search relation once per process, not once per request."""
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select to_regclass('public.product_search_documents') as docs, "
                "to_regclass('public.product_search_index') as legacy"
            )
            row = cur.fetchone() or {}
    if row.get("docs"):
        return "product_search_documents", True
    if row.get("legacy"):
        return "product_search_index", False
    return "", False


def reset_search_source_cache() -> None:
    """Use after an in-process migration or explicit schema replacement."""
    _source_relation.cache_clear()


def warm_search_source() -> tuple[str, bool]:
    """Resolve and memoize the search source during application startup."""
    return _source_relation()


def search_source_status() -> dict[str, str | bool]:
    """Return the active search implementation for logs and health endpoints."""
    relation, is_v5 = _source_relation()
    if relation and is_v5:
        mode = "v5_indexed"
    elif relation:
        mode = "legacy_indexed"
    else:
        mode = "live_fallback"
    return {"mode": mode, "relation": relation or "none", "v5": is_v5}


def _fetch_limit(limit: int, offset: int) -> int:
    """Bound the legacy compatibility path only."""
    configured = max(50, get_app_settings().search_fetch_limit)
    return min(configured, max(limit * 6, offset + limit * 3))


def _query_inputs(parsed: ParsedQuery) -> dict[str, Any]:
    terms = [term for term in parsed.normalized_query.split() if len(term) >= 2][:16]
    model_tokens = sorted({
        token.lower()
        for code in parsed.model_codes
        for token in code.replace("_", "-").replace("/", "-").split("-")
        if len(token) >= 4 and any(ch.isdigit() for ch in token)
    })
    if not model_tokens:
        model = str(parsed.detected_specs.get("model_code") or "").lower()
        model_tokens = [model] if model else []
    return {
        "terms": terms,
        "like_terms": [f"%{term}%" for term in terms],
        "model_tokens": model_tokens,
        "family": parsed.family or str(parsed.detected_specs.get("family") or "").lower(),
        "category": parsed.detected_category,
        "brand": parsed.detected_brand,
        "ram_gb": parsed.detected_specs.get("ram_gb"),
        "storage_gb": parsed.detected_specs.get("storage_gb"),
        "screen_inch": parsed.detected_specs.get("screen_inch"),
        "category_fallback": parsed.intent == "category_search" and not parsed.detected_brand and not parsed.family and not model_tokens,
    }


def _v5_indexed_search(parsed: ParsedQuery, limit: int, offset: int, relation: str) -> list[dict[str, Any]]:
    """Rank and paginate in PostgreSQL so deep pages are correct and bounded."""
    values = _query_inputs(parsed)
    query = f"""
        with input as (
          select plainto_tsquery('english', %s::text) as tsq,
                 %s::text as normalized_query,
                 %s::text as category,
                 %s::text as brand,
                 %s::text as family,
                 %s::text[] as model_tokens,
                 %s::text[] as like_terms,
                 %s::integer as requested_ram,
                 %s::integer as requested_storage,
                 %s::numeric as requested_screen,
                 %s::boolean as category_fallback
        ), base as (
          select
            psi.product_id, psi.brand, psi.category, psi.canonical_title, psi.title_norm,
            psi.specs, psi.best_price, psi.best_platform, psi.platform_count,
            psi.offer_count, psi.last_seen_at, psi.image_url, psi.family,
            psi.model_codes_text, psi.cpu_series, psi.ram_gb, psi.storage_gb,
            psi.screen_inch, psi.variant_group_id, psi.exact_fingerprint,
            psi.family_fingerprint,
            case
              when cardinality(i.model_tokens) > 0 and
                   (select count(*) from unnest(i.model_tokens) mt
                    where lower(coalesce(psi.model_codes_text,'')) like ('%%' || lower(mt) || '%%'))
                   = cardinality(i.model_tokens)
              then 1 else 0
            end as exact_model_match,
            case when i.family <> '' and lower(coalesce(psi.family,'')) like ('%%' || lower(i.family) || '%%') then 1 else 0 end as family_match,
            case when i.requested_ram is not null and psi.ram_gb is not null and i.requested_ram <> psi.ram_gb then 1 else 0 end as ram_conflict,
            case when i.requested_storage is not null and psi.storage_gb is not null and i.requested_storage <> psi.storage_gb then 1 else 0 end as storage_conflict,
            case when i.requested_screen is not null and psi.screen_inch is not null and abs(i.requested_screen - psi.screen_inch) > 0.25 then 1 else 0 end as screen_conflict,
            case when i.tsq::text <> '' and psi.search_vector @@ i.tsq then ts_rank_cd(psi.search_vector, i.tsq)::real else 0::real end as text_rank,
            similarity(lower(coalesce(psi.search_text,'')), i.normalized_query)::real as trigram_rank,
            (select count(*)::real from unnest(i.like_terms) t where lower(coalesce(psi.search_text,'')) like lower(t)) as listing_rank,
            i.requested_ram, i.requested_storage, i.requested_screen
          from {relation} psi cross join input i
          where (i.category is null or psi.category = i.category)
            and (i.brand is null or psi.brand = i.brand)
            and (
              i.category_fallback
              or cardinality(i.like_terms) = 0
              or (cardinality(i.model_tokens) > 0 and exists (
                    select 1 from unnest(i.model_tokens) mt
                    where lower(coalesce(psi.model_codes_text,'')) like ('%%' || lower(mt) || '%%')
                 ))
              or (i.tsq::text <> '' and psi.search_vector @@ i.tsq)
              or exists (select 1 from unnest(i.like_terms) t where lower(coalesce(psi.search_text,'')) like lower(t))
              or similarity(lower(coalesce(psi.search_text,'')), i.normalized_query) >= 0.10
            )
        ), scored as (
          select base.*,
            case
              when exact_model_match = 1 and ram_conflict = 0 and storage_conflict = 0 and screen_conflict = 0 then 'exact_match'
              when exact_model_match = 1 or family_match = 1 then 'similar_variant'
              else 'related_product'
            end as match_group,
            (
              exact_model_match * 95.0
              + family_match * 36.0
              + least(32.0, text_rank * 32.0)
              + least(16.0, listing_rank * 4.0)
              + least(14.0, trigram_rank * 14.0)
              + least(20.0, coalesce(platform_count, 0) * 5.0)
              + case when best_price is not null then 8.0 else 0.0 end
              + case when image_url is not null and image_url <> '' then 2.0 else 0.0 end
              + case when requested_ram is not null and ram_gb = requested_ram then 18.0 else 0.0 end
              + case when requested_storage is not null and storage_gb = requested_storage then 18.0 else 0.0 end
              - (ram_conflict + storage_conflict + screen_conflict) * 14.0
            )::real as rank_score
          from base
        )
        select * from scored
        order by
          case match_group when 'exact_match' then 3 when 'similar_variant' then 2 else 1 end desc,
          rank_score desc,
          platform_count desc,
          last_seen_at desc nulls last,
          product_id asc
        limit %s offset %s
    """
    params = (
        " ".join(values["terms"]), parsed.normalized_query, values["category"], values["brand"],
        values["family"], values["model_tokens"], values["like_terms"], values["ram_gb"],
        values["storage_gb"], values["screen_inch"], values["category_fallback"], limit, offset,
    )
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _legacy_indexed_search(parsed: ParsedQuery, limit: int, offset: int, relation: str) -> list[dict[str, Any]]:
    """Compatibility path for pre-v5 databases; bounded by the configured window."""
    values = _query_inputs(parsed)
    fetch_limit = _fetch_limit(limit, offset)
    query = f"""
        select psi.*, 0 as exact_model_match, 0 as family_match,
               ts_rank_cd(psi.search_vector, plainto_tsquery('english', %s))::real as text_rank,
               similarity(lower(coalesce(psi.search_text,'')), %s)::real as trigram_rank,
               (select count(*)::real from unnest(%s::text[]) t where lower(coalesce(psi.search_text,'')) like lower(t)) as listing_rank,
               'related_product'::text as match_group
        from {relation} psi
        where (%s::text is null or psi.category = %s)
          and (%s::text is null or psi.brand = %s)
        order by text_rank desc, listing_rank desc, trigram_rank desc, platform_count desc
        limit %s
    """
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (
                " ".join(values["terms"]), parsed.normalized_query, values["like_terms"],
                values["category"], values["category"], values["brand"], values["brand"], fetch_limit,
            ))
            rows = cur.fetchall()
    ranking_specs = {**parsed.detected_specs, "_query": parsed.normalized_query}
    return rank_products(rows, ranking_specs)[offset:offset + limit]


def _live_search(parsed: ParsedQuery, limit: int, offset: int) -> list[dict[str, Any]]:
    """SQL-ranked fallback when the dedicated search document table is unavailable."""
    values = _query_inputs(parsed)
    patterns = values["like_terms"]
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.id as product_id, p.brand, p.category, p.canonical_title,
                       p.title_norm, p.specs, b.best_price, b.best_platform,
                       b.platform_count, b.platform_count as offer_count, b.last_seen_at,
                       null::text as image_url, 0::real as text_rank,
                       (select count(*)::real from unnest(%s::text[]) t
                        where lower(coalesce(p.canonical_title,'')) like lower(t)) as listing_rank,
                       similarity(lower(coalesce(p.canonical_title,'')), %s)::real as trigram_rank,
                       0 as exact_model_match, 0 as family_match,
                       'related_product'::text as match_group,
                       (select count(*)::real from unnest(%s::text[]) t
                        where lower(coalesce(p.canonical_title,'')) like lower(t)) * 4.0
                         + similarity(lower(coalesce(p.canonical_title,'')), %s)::real * 14.0
                         + least(20.0, coalesce(b.platform_count, 0) * 5.0) as rank_score
                from product_clusters p
                left join current_product_best_prices b on b.product_id = p.id
                where p.status = 'active'
                  and (%s::text is null or p.category = %s)
                  and (%s::text is null or p.brand = %s)
                  and (cardinality(%s::text[]) = 0 or exists (
                    select 1 from unnest(%s::text[]) t
                    where lower(coalesce(p.canonical_title,'')) like lower(t)
                  ))
                order by rank_score desc, b.last_seen_at desc nulls last, p.id asc
                limit %s offset %s
                """,
                (patterns, parsed.normalized_query, patterns, parsed.normalized_query,
                 values["category"], values["category"], values["brand"], values["brand"],
                 patterns, patterns, limit, offset),
            )
            return cur.fetchall()


def search_products(parsed: ParsedQuery, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    offset = max(0, min(int(offset), 5000))
    try:
        relation, v5 = _source_relation()
        if relation and v5:
            return _v5_indexed_search(parsed, limit, offset, relation)
        if relation:
            return _legacy_indexed_search(parsed, limit, offset, relation)
    except Exception as exc:
        logger.exception("indexed_search_failed", extra={"error": str(exc)[:500]})
    return _live_search(parsed, limit, offset)


def get_product(product_id: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.*, b.best_price, b.best_platform, b.platform_count, b.last_seen_at,
                       d.image_url, pvl.group_id as variant_group_id
                from product_clusters p
                left join current_product_best_prices b on b.product_id = p.id
                left join product_search_documents d on d.product_id = p.id
                left join product_variant_links pvl on pvl.product_id = p.id
                where p.id = %s
                """,
                (product_id,),
            )
            return cur.fetchone()


def product_exists(product_id: str) -> bool:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select exists(select 1 from product_clusters where id = %s) as product_exists", (product_id,))
            row = cur.fetchone()
            return bool(row and row.get("product_exists"))


def get_product_offers(product_id: str) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, platform, listing_id, native_id, listing_url, title, image_url,
                       current_price, current_mrp, current_effective_price,
                       current_discount_pct, currency, stock_status, rating, review_count,
                       last_successful_refresh_at, last_seen_at, match_confidence,
                       last_verification_attempt_at, last_verified_at, verification_status,
                       verification_source, next_allowed_verification_at,
                       consecutive_verification_failures
                from platform_listings
                where product_id = %s and match_status = 'matched'
                order by (stock_status = 'out_of_stock'), current_price asc nulls last, platform asc
                """,
                (product_id,),
            )
            return cur.fetchall()


def get_price_history(product_id: str, days: int = 180) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select date, amazon_price, flipkart_price, croma_price, reliancedigital_price,
                       best_price, best_platform, platform_count, observations_count, all_time_low_so_far
                from daily_product_prices
                where product_id = %s and date >= current_date - (%s::int * interval '1 day')
                order by date asc
                """,
                (product_id, max(1, min(days, 3650))),
            )
            return cur.fetchall()


def get_similar_variants(product_id: str, limit: int = 12) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select d.*
                from product_variant_links source
                join product_variant_links peer on peer.group_id = source.group_id and peer.product_id <> source.product_id
                join product_search_documents d on d.product_id = peer.product_id
                where source.product_id = %s
                order by d.platform_count desc, d.best_price asc nulls last, d.last_seen_at desc nulls last
                limit %s
                """,
                (product_id, max(1, min(limit, 50))),
            )
            return cur.fetchall()


def log_search_query(parsed: ParsedQuery, result_count: int, top_product_id: str | None, confidence: float, ip_hash: str | None, session_hash: str | None) -> str:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into search_queries(raw_query, normalized_query, detected_category, detected_brand,
                                           detected_specs, result_count, top_product_id, confidence,
                                           ip_hash, session_hash)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id
                """,
                (parsed.raw_query, parsed.normalized_query, parsed.detected_category,
                 parsed.detected_brand, Jsonb(parsed.detected_specs), result_count,
                 top_product_id, confidence, ip_hash, session_hash),
            )
            return str(cur.fetchone()["id"])
