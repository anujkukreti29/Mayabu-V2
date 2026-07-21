"""Demand signal clustering and controlled promotion logic."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from mayabu.db.connection import db_connection
from mayabu.search.query_parser import ParsedQuery


def canonical_demand_key(parsed: ParsedQuery) -> str:
    specs = parsed.detected_specs
    parts = [parsed.detected_brand or "unknown"]
    for key in ("model_code", "cpu", "ram_gb", "storage_gb", "gpu"):
        if specs.get(key) is not None:
            parts.append(str(specs[key]).lower().replace(" ", ""))
    if len(parts) == 1:
        parts.append(parsed.normalized_query[:80])
    return "|".join(parts)


def demand_priority_score(parsed: ParsedQuery, result_count: int) -> float:
    score = float(parsed.quality_score)
    if result_count == 0:
        score += 20
    if parsed.intent == "exact_product":
        score += 20
    if parsed.detected_specs.get("model_code"):
        score += 15
    return min(100.0, score)


def upsert_demand_cluster(parsed: ParsedQuery, result_count: int, top_product_id: str | None = None) -> str | None:
    if not parsed.is_relevant:
        return None
    key = canonical_demand_key(parsed)
    score = demand_priority_score(parsed, result_count)
    coverage_status = "covered" if result_count > 0 else "missing"
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into query_demand_clusters(
                  canonical_query, normalized_query, detected_category, detected_brand, detected_specs,
                  query_count_24h, query_count_7d, unique_user_count_24h, best_matching_product_id,
                  coverage_status, priority_score, last_seen_at, status
                ) values (%s,%s,%s,%s,%s,1,1,1,%s,%s,%s,now(),'active')
                on conflict (normalized_query) do update set
                  query_count_24h = (
                    select count(*) from search_queries sq
                    where sq.normalized_query = excluded.normalized_query
                      and sq.created_at > now() - interval '24 hours'
                  ),
                  query_count_7d = (
                    select count(*) from search_queries sq
                    where sq.normalized_query = excluded.normalized_query
                      and sq.created_at > now() - interval '7 days'
                  ),
                  unique_user_count_24h = (
                    select count(distinct coalesce(sq.ip_hash, sq.session_hash, sq.id::text))
                    from search_queries sq
                    where sq.normalized_query = excluded.normalized_query
                      and sq.created_at > now() - interval '24 hours'
                  ),
                  best_matching_product_id = coalesce(excluded.best_matching_product_id, query_demand_clusters.best_matching_product_id),
                  coverage_status = excluded.coverage_status,
                  priority_score = greatest(query_demand_clusters.priority_score, excluded.priority_score),
                  last_seen_at = now(),
                  updated_at = now(),
                  detected_specs = query_demand_clusters.detected_specs || excluded.detected_specs
                returning id
                """,
                (
                    key,
                    key,
                    parsed.detected_category,
                    parsed.detected_brand,
                    Jsonb(parsed.detected_specs),
                    top_product_id,
                    coverage_status,
                    score,
                ),
            )
            return str(cur.fetchone()["id"])


def list_promotable_demand(limit: int = 25, min_score: float = 70.0) -> list[dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select * from query_demand_clusters
                where status = 'active'
                  and coverage_status = 'missing'
                  and priority_score >= %s
                  and (last_promoted_at is null or last_promoted_at < now() - interval '24 hours')
                order by priority_score desc, query_count_24h desc, last_seen_at desc
                limit %s
                """,
                (min_score, limit),
            )
            return cur.fetchall()


def refresh_demand_counters() -> int:
    """Recalculate rolling demand counters from search_queries."""
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update query_demand_clusters qdc
                set query_count_24h = coalesce(w.c24, 0),
                    query_count_7d = coalesce(w.c7, 0),
                    unique_user_count_24h = coalesce(w.u24, 0),
                    updated_at = now()
                from (
                  select q.normalized_query,
                         count(*) filter (where q.created_at > now() - interval '24 hours') as c24,
                         count(*) filter (where q.created_at > now() - interval '7 days') as c7,
                         count(distinct coalesce(q.ip_hash, q.session_hash, q.id::text))
                           filter (where q.created_at > now() - interval '24 hours') as u24
                  from search_queries q
                  where q.created_at > now() - interval '7 days'
                  group by q.normalized_query
                ) w
                where qdc.normalized_query = w.normalized_query
                returning qdc.id
                """
            )
            updated = len(cur.fetchall())
            cur.execute(
                """
                update query_demand_clusters
                set query_count_24h = 0, query_count_7d = 0, unique_user_count_24h = 0, updated_at = now()
                where last_seen_at < now() - interval '7 days'
                  and (query_count_24h <> 0 or query_count_7d <> 0 or unique_user_count_24h <> 0)
                returning id
                """
            )
            return updated + len(cur.fetchall())
