"""Read-optimized multi-category search for Mayabu."""

from __future__ import annotations

import json
import logging
import re
import uuid
from functools import lru_cache
from typing import Any

from psycopg.types.json import Jsonb

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection
from mayabu.search.category_registry import (
    SEARCH_CONTRACT_VERSION,
    get_search_category,
    public_search_categories,
)
from mayabu.search.query_parser import ParsedQuery
from mayabu.search.ranker import rank_products

logger = logging.getLogger(__name__)

# Categories never shown in public product search.
_EXCLUDED_PUBLIC_CATEGORIES = frozenset({"unknown", "accessory"})


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
    return min(configured, max(limit * 6, offset + offset * 3))


def _scalar_number(value: Any) -> float | int | None:
    """Ranking conflict params must be scalars; multi-value filters stay filter-only."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (list, tuple, set)):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text) if "." in text else int(text)
    except (TypeError, ValueError):
        return None


def _query_inputs(parsed: ParsedQuery) -> dict[str, Any]:
    terms = [term for term in parsed.normalized_query.split() if len(term) >= 2][:16]
    model_tokens = sorted(
        {
            token.lower()
            for code in parsed.model_codes
            for token in code.replace("_", "-").replace("/", "-").split("-")
            if len(token) >= 4 and any(ch.isdigit() for ch in token)
        }
    )
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
        "ram_gb": _scalar_number(parsed.detected_specs.get("ram_gb")),
        "storage_gb": _scalar_number(parsed.detected_specs.get("storage_gb")),
        "screen_inch": _scalar_number(
            parsed.detected_specs.get("screen_inch")
            or parsed.detected_specs.get("screen_size_inch")
        ),
        "min_price": parsed.min_price,
        "max_price": parsed.max_price,
        "category_fallback": parsed.intent == "category_search"
        and not parsed.detected_brand
        and not parsed.family
        and not model_tokens,
        "filters": dict(parsed.category_filters or {}),
    }


def _specs_filter_sql(filters: dict[str, Any], *, param_start: int = 1) -> tuple[str, list[Any]]:
    """Build allowlisted JSONB predicates — never interpolate user keys.

    A list/tuple value means OR within that facet (Samsung OR LG).
    Distinct facets combine with AND.
    ``brand`` filters the document brand column, not specs JSON.
    """
    clauses: list[str] = []
    params: list[Any] = []
    for key, value in filters.items():
        # Key already allowlisted by parser; still refuse odd characters.
        if not re_fullmatch_key(key):
            continue
        if key == "brand":
            brands = value if isinstance(value, (list, tuple, set)) else [value]
            brands = [str(v).lower() for v in brands if v not in (None, "", [], {})]
            if not brands:
                continue
            placeholders = ", ".join(["%s"] * len(brands))
            clauses.append(f"lower(coalesce(psi.brand, '')) in ({placeholders})")
            params.extend(brands)
            continue
        if isinstance(value, (list, tuple, set)):
            values = [v for v in value if v not in (None, "", [], {})]
            if not values:
                continue
            if all(isinstance(v, bool) for v in values):
                placeholders = ", ".join(["%s"] * len(values))
                clauses.append(f"(psi.specs->>'{key}')::boolean in ({placeholders})")
                params.extend(bool(v) for v in values)
            elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                placeholders = ", ".join(["%s"] * len(values))
                clauses.append(
                    f"case when (psi.specs->>'{key}') ~ '^[0-9]+(\\.[0-9]+)?$' "
                    f"then (psi.specs->>'{key}')::numeric else null end in ({placeholders})"
                )
                params.extend(float(v) for v in values)
            else:
                placeholders = ", ".join(["%s"] * len(values))
                clauses.append(
                    f"lower(coalesce(psi.specs->>'{key}', '')) in ({placeholders})"
                )
                params.extend(str(v).lower() for v in values)
            continue
        if isinstance(value, bool):
            clauses.append(f"(psi.specs->>'{key}')::boolean = %s")
            params.append(value)
        elif isinstance(value, (int, float)):
            clauses.append(
                f"case when (psi.specs->>'{key}') ~ '^[0-9]+(\\.[0-9]+)?$' "
                f"then (psi.specs->>'{key}')::numeric else null end = %s"
            )
            params.append(float(value))
        else:
            clauses.append(f"lower(coalesce(psi.specs->>'{key}', '')) = lower(%s)")
            params.append(str(value))
    if not clauses:
        return "", []
    return " and " + " and ".join(clauses), params


def re_fullmatch_key(key: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{0,40}", key or ""))


def _order_clause(sort: str) -> str:
    if sort == "price_asc":
        return """
          case when best_price is null then 1 else 0 end asc,
          best_price asc,
          rank_score desc,
          platform_count desc,
          last_seen_at desc nulls last,
          product_id asc
        """
    if sort == "price_desc":
        return """
          case when best_price is null then 1 else 0 end asc,
          best_price desc,
          rank_score desc,
          platform_count desc,
          last_seen_at desc nulls last,
          product_id asc
        """
    if sort == "recently_checked":
        return """
          last_seen_at desc nulls last,
          platform_count desc,
          best_price asc nulls last,
          product_id asc
        """
    return """
      case match_group when 'exact_match' then 3 when 'similar_variant' then 2 else 1 end desc,
      rank_score desc,
      platform_count desc,
      last_seen_at desc nulls last,
      product_id asc
    """


def _v5_indexed_search(
    parsed: ParsedQuery,
    limit: int,
    offset: int,
    relation: str,
    *,
    sort: str = "relevance",
    categories: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank and paginate in PostgreSQL so deep pages are correct and bounded."""
    values = _query_inputs(parsed)
    filter_sql, filter_params = _specs_filter_sql(values["filters"])
    category_list = categories
    if category_list is None and values["category"]:
        category_list = [values["category"]]
    if category_list is None:
        category_list = list(public_search_categories())

    # Exclude unknown/accessory always.
    category_list = [c for c in category_list if c not in _EXCLUDED_PUBLIC_CATEGORIES]
    if not category_list:
        return []

    order_sql = _order_clause(sort)
    query = f"""
        with input as (
          select plainto_tsquery('english', %s::text) as tsq,
                 %s::text as normalized_query,
                 %s::text[] as categories,
                 %s::text as brand,
                 %s::text as family,
                 %s::text[] as model_tokens,
                 %s::text[] as like_terms,
                 %s::integer as requested_ram,
                 %s::integer as requested_storage,
                 %s::numeric as requested_screen,
                 %s::boolean as category_fallback,
                 %s::numeric as min_price,
                 %s::numeric as max_price
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
            i.requested_ram, i.requested_storage, i.requested_screen,
            i.normalized_query
          from {relation} psi cross join input i
          where psi.category = any(i.categories)
            and psi.category <> all(%s::text[])
            and psi.best_price is not null
            and psi.best_price > 0
            and coalesce(psi.platform_count, 0) >= 1
            and (i.brand is null or psi.brand = i.brand)
            and (i.min_price is null or (psi.best_price is not null and psi.best_price >= i.min_price))
            and (i.max_price is null or (psi.best_price is not null and psi.best_price <= i.max_price))
            {filter_sql}
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
              + case
                  when normalized_query like '%%gaming%%' and category = 'laptop' and
                       lower(coalesce(family,'') || ' ' || coalesce(canonical_title,'') || ' ' || coalesce(specs->>'gpu',''))
                       ~ '(gaming (laptop|notebook)|rog|tuf|legion|loq|victus|omen|nitro|predator|alienware|katana|cyborg|strix|rtx|gtx|geforce|radeon|helios|pulse)'
                  then 48.0
                  when normalized_query like '%%gaming%%' and category = 'laptop' then -36.0
                  else 0.0
                end
              + case
                  when normalized_query like '%%oled%%' and lower(coalesce(canonical_title,'') || ' ' || coalesce(specs->>'panel_type','')) like '%%oled%%' then 24.0
                  when normalized_query like '%%qled%%' and lower(coalesce(canonical_title,'') || ' ' || coalesce(specs->>'panel_type','')) like '%%qled%%' then 24.0
                  when normalized_query like '%%front load%%' and lower(coalesce(canonical_title,'')) like '%%front%%' then 20.0
                  when normalized_query like '%%top load%%' and lower(coalesce(canonical_title,'')) like '%%top%%' then 20.0
                  when normalized_query like '%%noise%%' and normalized_query like '%%cancell%%'
                       and lower(coalesce(canonical_title,'') || ' ' || coalesce(specs->>'anc','')) ~ '(anc|noise)'
                  then 16.0
                  when normalized_query like '%%mirrorless%%' and lower(coalesce(canonical_title,'')) like '%%mirrorless%%' then 20.0
                  else 0.0
                end
              + case
                  when category = 'camera'
                       and (
                         lower(trim(canonical_title)) ~ '^(dslr/?slr camera|digital camera|mirrorless camera|camera)$'
                         or lower(coalesce(canonical_title,'')) ~ 'designed for'
                       )
                  then -55.0
                  when category = 'camera'
                       and normalized_query ~ 'camera'
                       and normalized_query !~ 'lens'
                       and lower(coalesce(canonical_title,'')) ~ '(lens only|prime lens|zoom lens|telephoto|batis|kid.? camera|toy camera|tripod|camera bag)'
                  then -40.0
                  when category = 'camera'
                       and normalized_query ~ 'camera'
                       and normalized_query !~ 'lens'
                       and lower(coalesce(canonical_title,'')) ~ '(mirrorless|dslr|camera body|eos|alpha|lumix|ilce)'
                  then 28.0
                  else 0.0
                end
            )::real as rank_score
          from base
        )
        select * from scored
        order by {order_sql}
        limit %s offset %s
    """
    params: list[Any] = [
        " ".join(values["terms"]),
        parsed.normalized_query,
        category_list,
        values["brand"],
        values["family"],
        values["model_tokens"],
        values["like_terms"],
        values["ram_gb"],
        values["storage_gb"],
        values["screen_inch"],
        values["category_fallback"],
        values["min_price"],
        values["max_price"],
        list(_EXCLUDED_PUBLIC_CATEGORIES),
        *filter_params,
        limit,
        offset,
    ]
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _fair_cross_category_page(
    ranked: list[dict[str, Any]], *, limit: int, offset: int
) -> list[dict[str, Any]]:
    """Round-robin categories so one dense vertical cannot monopolize top results.

    Within each category, relevance order from ``ranked`` is preserved.
    Empty categories are skipped. Deterministic via public category order.
    """
    if limit <= 0:
        return []
    by_cat: dict[str, list[dict[str, Any]]] = {c: [] for c in public_search_categories()}
    other: list[dict[str, Any]] = []
    for row in ranked:
        cat = str(row.get("category") or "")
        if cat in by_cat:
            by_cat[cat].append(row)
        else:
            other.append(row)
    queues = [by_cat[c] for c in public_search_categories() if by_cat[c]]
    if other:
        queues.append(other)
    interleaved: list[dict[str, Any]] = []
    idxs = [0] * len(queues)
    while len(interleaved) < offset + limit:
        progressed = False
        for qi, queue in enumerate(queues):
            i = idxs[qi]
            if i < len(queue):
                interleaved.append(queue[i])
                idxs[qi] = i + 1
                progressed = True
                if len(interleaved) >= offset + limit:
                    break
        if not progressed:
            break
    return interleaved[offset : offset + limit]


def _cross_category_search(
    parsed: ParsedQuery,
    limit: int,
    offset: int,
    relation: str,
    *,
    sort: str = "relevance",
) -> list[dict[str, Any]]:
    """Bounded per-category retrieval then fair merge — avoids laptop dominance."""
    cats = list(public_search_categories())
    per = min(60, max(limit + offset, 16))
    merged: dict[str, dict[str, Any]] = {}
    for cat in cats:
        # Shallow copy of parsed with forced category.
        cat_parsed = ParsedQuery(
            raw_query=parsed.raw_query,
            normalized_query=parsed.normalized_query,
            detected_category=cat,
            detected_brand=parsed.detected_brand,
            detected_specs=dict(parsed.detected_specs),
            quality_score=parsed.quality_score,
            is_relevant=True,
            intent=parsed.intent,
            family=parsed.family,
            model_codes=parsed.model_codes,
            min_price=parsed.min_price,
            max_price=parsed.max_price,
            explicit_category=parsed.explicit_category,
            search_mode="category",
            category_filters=dict(parsed.category_filters),
            category_confidence=parsed.category_confidence,
        )
        rows = _v5_indexed_search(cat_parsed, per, 0, relation, sort="relevance", categories=[cat])
        for row in rows:
            pid = str(row.get("product_id"))
            if not pid:
                continue
            prev = merged.get(pid)
            if prev is None or float(row.get("rank_score") or 0) > float(prev.get("rank_score") or 0):
                merged[pid] = dict(row)

    ranking_specs = {
        **parsed.detected_specs,
        "_query": parsed.normalized_query,
        "brand": parsed.detected_brand,
    }
    ranked = rank_products(list(merged.values()), ranking_specs)
    if sort == "price_asc":
        ranked.sort(
            key=lambda r: (
                r.get("best_price") is None,
                float(r.get("best_price") or 0),
                -float(r.get("rank_score") or 0),
                str(r.get("product_id") or ""),
            )
        )
        return ranked[offset : offset + limit]
    if sort == "price_desc":
        ranked.sort(
            key=lambda r: (
                r.get("best_price") is None,
                -float(r.get("best_price") or 0),
                -float(r.get("rank_score") or 0),
                str(r.get("product_id") or ""),
            )
        )
        return ranked[offset : offset + limit]
    if sort == "recently_checked":
        ranked.sort(
            key=lambda r: (
                r.get("last_seen_at") is None,
                # ISO timestamps sort ascending; negate via reverse on non-null path
                "" if r.get("last_seen_at") is None else str(r.get("last_seen_at")),
                -int(r.get("platform_count") or 0),
                str(r.get("product_id") or ""),
            ),
            reverse=True,
        )
        # Keep null last_seen_at at the end after reverse=True moved them first.
        ranked.sort(key=lambda r: r.get("last_seen_at") is None)
        return ranked[offset : offset + limit]
    return _fair_cross_category_page(ranked, limit=limit, offset=offset)


def _legacy_indexed_search(parsed: ParsedQuery, limit: int, offset: int, relation: str) -> list[dict[str, Any]]:
    """Compatibility path for pre-v5 databases; bounded by the configured window."""
    values = _query_inputs(parsed)
    fetch_limit = _fetch_limit(limit, offset)
    cats = [values["category"]] if values["category"] else list(public_search_categories())
    query = f"""
        select psi.*, 0 as exact_model_match, 0 as family_match,
               ts_rank_cd(psi.search_vector, plainto_tsquery('english', %s))::real as text_rank,
               similarity(lower(coalesce(psi.search_text,'')), %s)::real as trigram_rank,
               (select count(*)::real from unnest(%s::text[]) t where lower(coalesce(psi.search_text,'')) like lower(t)) as listing_rank,
               'related_product'::text as match_group
        from {relation} psi
        where psi.category = any(%s::text[])
          and (%s::text is null or psi.brand = %s)
        order by text_rank desc, listing_rank desc, trigram_rank desc, platform_count desc, product_id asc
        limit %s
    """
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    " ".join(values["terms"]),
                    parsed.normalized_query,
                    values["like_terms"],
                    cats,
                    values["brand"],
                    values["brand"],
                    fetch_limit,
                ),
            )
            rows = cur.fetchall()
    ranking_specs = {**parsed.detected_specs, "_query": parsed.normalized_query}
    return rank_products(rows, ranking_specs)[offset : offset + limit]


def _live_search(parsed: ParsedQuery, limit: int, offset: int) -> list[dict[str, Any]]:
    """SQL-ranked fallback when the dedicated search document table is unavailable."""
    values = _query_inputs(parsed)
    patterns = values["like_terms"]
    cats = [values["category"]] if values["category"] else list(public_search_categories())
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
                  and p.category = any(%s::text[])
                  and p.category <> all(%s::text[])
                  and (%s::text is null or p.brand = %s)
                  and (%s::numeric is null or (b.best_price is not null and b.best_price >= %s))
                  and (%s::numeric is null or (b.best_price is not null and b.best_price <= %s))
                  and (cardinality(%s::text[]) = 0 or exists (
                    select 1 from unnest(%s::text[]) t
                    where lower(coalesce(p.canonical_title,'')) like lower(t)
                  ))
                order by rank_score desc, b.last_seen_at desc nulls last, p.id asc
                limit %s offset %s
                """,
                (
                    patterns,
                    parsed.normalized_query,
                    patterns,
                    parsed.normalized_query,
                    cats,
                    list(_EXCLUDED_PUBLIC_CATEGORIES),
                    values["brand"],
                    values["brand"],
                    values["min_price"],
                    values["min_price"],
                    values["max_price"],
                    values["max_price"],
                    patterns,
                    patterns,
                    limit,
                    offset,
                ),
            )
            return cur.fetchall()


def search_products(
    parsed: ParsedQuery,
    limit: int = 20,
    offset: int = 0,
    *,
    sort: str = "relevance",
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    offset = max(0, min(int(offset), 5000))
    if sort not in {"relevance", "price_asc", "price_desc", "recently_checked"}:
        sort = "relevance"
    try:
        relation, v5 = _source_relation()
        if relation and v5:
            if parsed.search_mode == "cross_category" or parsed.detected_category is None:
                return _cross_category_search(parsed, limit, offset, relation, sort=sort)
            return _v5_indexed_search(parsed, limit, offset, relation, sort=sort)
        if relation:
            return _legacy_indexed_search(parsed, limit, offset, relation)
    except Exception as exc:
        logger.exception("indexed_search_failed", extra={"error": str(exc)[:500]})
    return _live_search(parsed, limit, offset)


_FACET_CANDIDATE_CAP = 200
# Omit facets that cover too few candidates in the query-scoped sample.
_MIN_FACET_SAMPLE = 5
_MIN_FACET_COVERAGE = 0.15
_ALWAYS_KEEP_FACETS = frozenset({"brand", "category"})


def _facet_is_useful(value_counts: dict[str, int], sample_size: int, *, key: str) -> bool:
    if not value_counts:
        return False
    if key in _ALWAYS_KEEP_FACETS:
        return True
    if sample_size < _MIN_FACET_SAMPLE:
        return True
    covered = sum(value_counts.values())
    return (covered / max(1, sample_size)) >= _MIN_FACET_COVERAGE


def build_page_facets(rows: list[dict[str, Any]], category: str | None) -> dict[str, list[dict[str, Any]]]:
    """Aggregate facet values from a candidate row set (page or query-scoped)."""
    sample_size = len(rows)
    info = get_search_category(category)
    if info is None:
        facets: dict[str, dict[str, int]] = {"brand": {}, "category": {}}
        for row in rows:
            brand = str(row.get("brand") or "").lower()
            cat = str(row.get("category") or "")
            if brand:
                facets["brand"][brand] = facets["brand"].get(brand, 0) + 1
            if cat:
                facets["category"][cat] = facets["category"].get(cat, 0) + 1
        return {
            key: [{"value": value, "count": count} for value, count in sorted(values.items())]
            for key, values in facets.items()
            if _facet_is_useful(values, sample_size, key=key)
        }

    buckets: dict[str, dict[str, int]] = {f.key: {} for f in info.facet_defs if f.key != "best_price"}
    for row in rows:
        specs = row.get("specs") if isinstance(row.get("specs"), dict) else {}
        for facet in info.facet_defs:
            if facet.key == "best_price":
                continue
            if facet.source == "column":
                raw = row.get(facet.key)
            else:
                raw = specs.get(facet.key)
                if raw is None and facet.key in {"ram_gb", "storage_gb", "screen_inch"}:
                    raw = row.get(facet.key)
            if raw in (None, "", [], {}):
                continue
            key = str(raw).lower() if not isinstance(raw, bool) else str(raw).lower()
            buckets[facet.key][key] = buckets[facet.key].get(key, 0) + 1
    return {
        key: [{"value": value, "count": count} for value, count in sorted(values.items())]
        for key, values in buckets.items()
        if _facet_is_useful(values, sample_size, key=key)
    }


def fetch_facet_candidates(parsed: ParsedQuery, *, sort: str = "relevance") -> list[dict[str, Any]]:
    """Bounded matching set for query-scoped facet aggregation (not full catalog)."""
    return search_products(parsed, limit=_FACET_CANDIDATE_CAP, offset=0, sort=sort)


def build_query_facets(
    parsed: ParsedQuery, *, sort: str = "relevance"
) -> tuple[dict[str, list[dict[str, Any]]], str, int]:
    """Return facets, facet_scope, and candidate sample size used."""
    rows = fetch_facet_candidates(parsed, sort=sort)
    facets = build_page_facets(rows, parsed.detected_category)
    # Only keep facets that have at least one value in the matching set.
    facets = {k: v for k, v in facets.items() if v}
    return facets, "query", len(rows)


def category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        cat = str(row.get("category") or "")
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    return counts


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
            cur.execute(
                "select exists(select 1 from product_clusters where id = %s) as product_exists",
                (product_id,),
            )
            row = cur.fetchone()
            return bool(row and row.get("product_exists"))


def get_product_offers(product_id: str) -> list[dict[str, Any]]:
    """Return one public offer per unique retailer for a canonical product."""
    from mayabu.platforms.coverage import public_offer_allowed
    from mayabu.search.public_offers import select_public_offers

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select p.category, p.canonical_title, p.specs,
                       l.id, l.platform, l.listing_id, l.native_id, l.listing_url, l.title, l.image_url,
                       l.current_price, l.current_mrp, l.current_effective_price,
                       l.current_discount_pct, l.currency, l.stock_status, l.rating, l.review_count,
                       l.last_successful_refresh_at, l.last_seen_at, l.match_confidence,
                       l.last_verification_attempt_at, l.last_verified_at, l.verification_status,
                       l.verification_source, l.next_allowed_verification_at,
                       l.consecutive_verification_failures, l.match_status, l.specs as listing_specs
                from platform_listings l
                join product_clusters p on p.id = l.product_id
                where l.product_id = %s and l.match_status = 'matched'
                order by (l.stock_status = 'out_of_stock'), l.current_price asc nulls last, l.platform asc
                """,
                (product_id,),
            )
            rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return []

    category = rows[0].get("category") or "unknown"
    product_title = rows[0].get("canonical_title")
    product_specs = rows[0].get("specs") if isinstance(rows[0].get("specs"), dict) else {}

    eligible: list[dict[str, Any]] = []
    for row in rows:
        platform = row.get("platform") or ""
        if not public_offer_allowed(platform, category):
            continue
        currency = str(row.get("currency") or "INR").strip().upper()
        if currency != "INR":
            continue
        item = dict(row)
        # Prefer listing-level specs for color hints when present.
        listing_specs = item.pop("listing_specs", None)
        if isinstance(listing_specs, dict) and listing_specs:
            item["specs"] = listing_specs
        else:
            item.pop("specs", None)
        item.pop("category", None)
        item.pop("canonical_title", None)
        price = item.get("current_price")
        if price is not None:
            try:
                if float(price) <= 0:
                    item["current_price"] = None
            except (TypeError, ValueError):
                item["current_price"] = None
        eligible.append(item)

    return select_public_offers(
        eligible,
        category=category,
        product_title=str(product_title) if product_title else None,
        product_specs=product_specs,
    )


def get_price_history(product_id: str, days: int = 180) -> list[dict[str, Any]]:
    """Return daily price history."""
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
            rows = [dict(r) for r in cur.fetchall()]
            try:
                cur.execute(
                    """
                    select date, platform, min_price
                    from daily_product_platform_prices
                    where product_id = %s and date >= current_date - (%s::int * interval '1 day')
                    order by date asc, platform asc
                    """,
                    (product_id, max(1, min(days, 3650))),
                )
                by_date: dict[Any, dict[str, Any]] = {}
                for item in cur.fetchall():
                    day = item["date"]
                    by_date.setdefault(day, {})[item["platform"]] = item["min_price"]
                for row in rows:
                    row["platform_prices"] = by_date.get(row["date"], {})
            except Exception as exc:
                logger.warning(
                    "daily_platform_prices_fallback",
                    extra={"product_id": product_id, "error": str(exc)[:300]},
                )
                for row in rows:
                    row["platform_prices"] = {
                        k.replace("_price", ""): row.get(k)
                        for k in (
                            "amazon_price",
                            "flipkart_price",
                            "croma_price",
                            "reliancedigital_price",
                        )
                        if row.get(k) is not None
                    }
            try:
                cur.execute(
                    """
                    select date,
                           sum(in_stock_count)::int as in_stock_observations,
                           sum(observations_count)::int as listing_observations
                    from daily_listing_prices
                    where product_id = %s
                      and date >= current_date - (%s::int * interval '1 day')
                    group by date
                    """,
                    (product_id, max(1, min(days, 3650))),
                )
                stock_by_date = {item["date"]: item for item in cur.fetchall()}
                for row in rows:
                    stock = stock_by_date.get(row["date"]) or {}
                    row["in_stock_observations"] = stock.get("in_stock_observations")
                    row["listing_observations"] = stock.get("listing_observations")
                    row["stock_inferred_from_price"] = False
            except Exception as exc:
                logger.warning(
                    "daily_listing_stock_fallback",
                    extra={"product_id": product_id, "error": str(exc)[:300]},
                )
                for row in rows:
                    row.setdefault("in_stock_observations", None)
                    row.setdefault("stock_inferred_from_price", False)
            return rows


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


def get_similar_products(product_id: str, limit: int = 8) -> list[dict[str, Any]]:
    """Same-category public neighbors in a compatible price/spec band (not personalization)."""
    cap = max(4, min(int(limit), 12))
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select product_id, category, brand, best_price, specs
            from product_search_documents
            where product_id = %s
            """,
            (product_id,),
        )
        seed = cur.fetchone()
        if not seed or not seed.get("category"):
            return []
        category = str(seed["category"])
        brand = (seed.get("brand") or "").strip().lower() or None
        price = seed.get("best_price")
        try:
            price_f = float(price) if price is not None else None
        except (TypeError, ValueError):
            price_f = None
        lo = (price_f * 0.55) if price_f and price_f > 0 else None
        hi = (price_f * 1.8) if price_f and price_f > 0 else None

        cur.execute(
            """
            select d.*
            from product_search_documents d
            where d.category = %s
              and d.product_id <> %s
              and d.best_price is not null
              and d.best_price > 0
              and (%s::numeric is null or d.best_price between %s and %s)
              and not exists (
                select 1
                from product_variant_links src
                join product_variant_links peer
                  on peer.group_id = src.group_id
                 and peer.product_id = d.product_id
                where src.product_id = %s
              )
            order by
              case when %s::text is not null and lower(coalesce(d.brand,'')) = %s then 0 else 1 end,
              abs(coalesce(d.best_price, 0) - coalesce(%s::numeric, d.best_price, 0)) asc,
              d.platform_count desc nulls last,
              d.last_seen_at desc nulls last
            limit %s
            """,
            (
                category,
                product_id,
                lo,
                lo,
                hi,
                product_id,
                brand,
                brand,
                price_f,
                cap,
            ),
        )
        return cur.fetchall()


def popular_search_queries(*, limit: int = 6, days: int = 14) -> list[dict[str, Any]]:
    """Aggregate popular normalized queries.

    Privacy: requires ≥5 hits AND ≥3 distinct actors (session_hash/ip_hash)
    within the window. Length 2–80; result_count > 0; sensitive tokens excluded.
    Single-user or low-volume queries never surface. Empty when table/data missing.
    """
    from psycopg.errors import UndefinedTable

    cap = max(1, min(int(limit), 12))
    window = max(1, min(int(days), 90))
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select normalized_query as query,
                           count(*)::int as hits,
                           count(distinct coalesce(session_hash, ip_hash, ''))::int as actors
                    from search_queries
                    where created_at >= now() - (%s::int * interval '1 day')
                      and result_count > 0
                      and length(trim(coalesce(normalized_query, ''))) between 2 and 80
                      and normalized_query !~* '(password|otp|token|ssn|aadhaar)'
                    group by normalized_query
                    having count(*) >= 5
                       and count(distinct coalesce(session_hash, ip_hash, '')) >= 3
                    order by hits desc, normalized_query asc
                    limit %s
                    """,
                    (window, cap),
                )
                return [
                    {"query": str(row["query"]).strip(), "hits": int(row["hits"])}
                    for row in cur.fetchall()
                    if row.get("query") and str(row["query"]).strip()
                ]
    except UndefinedTable:
        return []
    except Exception:
        logger.warning("popular_search_queries_unavailable", exc_info=True)
        return []


def log_search_query(
    parsed: ParsedQuery,
    result_count: int,
    top_product_id: str | None,
    confidence: float,
    ip_hash: str | None,
    session_hash: str | None,
) -> str:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into search_queries(raw_query, normalized_query, detected_category, detected_brand,
                                           detected_specs, result_count, top_product_id, confidence,
                                           ip_hash, session_hash)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id
                """,
                (
                    parsed.raw_query,
                    parsed.normalized_query,
                    parsed.detected_category,
                    parsed.detected_brand,
                    Jsonb(parsed.detected_specs),
                    result_count,
                    top_product_id,
                    confidence,
                    ip_hash,
                    session_hash,
                ),
            )
            return str(cur.fetchone()["id"])


def parse_filters_param(raw: str | None, category: str | None) -> dict[str, Any]:
    """Parse optional filters JSON against category allowlist."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise ValueError("invalid_filters") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid_filters")
    info = get_search_category(category)
    if info is None:
        raise ValueError("filters_require_category")
    out: dict[str, Any] = {}
    for key, value in data.items():
        if not isinstance(key, str) or key not in info.filterable_keys:
            raise ValueError(f"unsupported_filter:{key}")
        if value in (None, "", [], {}):
            continue
        out[key] = value
    return out


def _valid_product_uuids(product_ids: list[str]) -> list[str]:
    """Keep only well-formed UUIDs so Postgres uuid[] casts never 500."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in product_ids:
        pid = str(raw).strip()
        if not pid or pid in seen:
            continue
        try:
            uuid.UUID(pid)
        except ValueError:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def get_products_by_ids(product_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch multiple product_clusters rows in one query. Returns id -> row."""
    cleaned = _valid_product_uuids(product_ids)
    if not cleaned:
        return {}
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
                where p.id = any(%s::uuid[])
                """,
                (cleaned,),
            )
            rows = cur.fetchall()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = str(row.get("id") or "")
        if pid:
            out[pid] = row
    return out


def get_public_offer_counts(product_ids: list[str]) -> dict[str, int]:
    """Count unique public retailers per product (not raw listing rows)."""
    from mayabu.platforms.coverage import public_offer_allowed

    cleaned = _valid_product_uuids(product_ids)
    if not cleaned:
        return {}
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select l.product_id, p.category, l.platform
                from platform_listings l
                join product_clusters p on p.id = l.product_id
                where l.product_id = any(%s::uuid[])
                  and l.match_status = 'matched'
                  and l.current_price is not null
                  and l.current_price > 0
                """,
                (cleaned,),
            )
            rows = cur.fetchall()
    seen: dict[str, set[str]] = {pid: set() for pid in cleaned}
    for row in rows:
        pid = str(row.get("product_id") or "")
        category = row.get("category") or "unknown"
        platform = str(row.get("platform") or "").strip().lower()
        if not pid or not platform or not public_offer_allowed(platform, category):
            continue
        seen.setdefault(pid, set()).add(platform)
    return {pid: len(platforms) for pid, platforms in seen.items()}


__all__ = [
    "SEARCH_CONTRACT_VERSION",
    "build_page_facets",
    "build_query_facets",
    "category_counts",
    "fetch_facet_candidates",
    "get_price_history",
    "get_product",
    "get_product_offers",
    "get_products_by_ids",
    "get_public_offer_counts",
    "get_similar_variants",
    "get_similar_products",
    "log_search_query",
    "parse_filters_param",
    "product_exists",
    "reset_search_source_cache",
    "search_products",
    "search_source_status",
    "warm_search_source",
]
