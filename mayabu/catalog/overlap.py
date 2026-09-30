"""Targeted cross-retailer discovery for multi-store overlap.

Finds canonical products with strong model identity on exactly one retailer,
then searches missing primary retailers using brand + model code queries.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from mayabu.db.connection import db_connection
from mayabu.platforms.coverage import discovery_allowed
from mayabu.scheduler.budget_policy import budget_available, ensure_today_budget
from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu_db.tasks import create_task

logger = logging.getLogger(__name__)

PRIMARY_OVERLAP_PLATFORMS = ("amazon", "flipkart", "croma", "reliancedigital")
SECONDARY_OVERLAP_PLATFORMS = ("vijaysales", "poorvika")
OVERLAP_PRIORITY = 85  # after urgent refresh, before enrich
OVERLAP_COOLDOWN_HOURS = 168  # 7 days
CATEGORY_PRIORITY = (
    "smartphone",
    "television",
    "tws",
    "headphones",
    "refrigerator",
    "washing_machine",
    "laptop",
    "camera",
)


_WEAK_MODEL_TOKENS = frozenset(
    {
        "WIRED",
        "WIRELESS",
        "BLUETOOTH",
        "ANC",
        "USB",
        "HDMI",
        "ANDROID",
        "IOS",
        "SMART",
        "PRO",
        "MAX",
        "PLUS",
        "MINI",
        "LITE",
        "KIT",
        "BODY",
        "ONLY",
    }
)


def build_overlap_query(
    *,
    brand: str | None,
    model_codes: list[str],
    category: str | None,
    specs: dict[str, Any] | None = None,
) -> str | None:
    """Strong-identity search string. Returns None when identity is too weak."""
    specs = specs or {}
    codes = [str(c).strip().upper() for c in model_codes if str(c).strip()]
    # Reject weak series-only / marketing tokens
    strong = [
        c
        for c in codes
        if len(c) >= 4
        and not c.isalpha()
        and c not in _WEAK_MODEL_TOKENS
        and not c.isdigit()
    ]
    if not strong:
        strong = [
            c
            for c in codes
            if len(c) >= 6 and c not in _WEAK_MODEL_TOKENS and any(ch.isdigit() for ch in c)
        ]

    parts: list[str] = []
    if brand and str(brand).strip():
        parts.append(str(brand).strip())

    if strong:
        parts.append(strong[0])
    else:
        # Commercial family fallback (common for Indian phone/TV retail titles).
        family = str(specs.get("family") or "").replace("_", " ").strip()
        if not family or len(family) < 5:
            return None
        # Require variant identity for family-only queries.
        if category == "smartphone" and not (specs.get("storage_gb") or specs.get("ram_gb")):
            return None
        if category == "television" and not specs.get("screen_size_inch"):
            return None
        if category in {"tws", "headphones"} and len(family) < 8:
            # Avoid generic "airpods" / "galaxy buds" without generation.
            return None
        parts.append(family)

    if specs.get("storage_gb"):
        parts.append(f"{specs['storage_gb']}GB")
    if specs.get("ram_gb") and category in {"smartphone", "laptop"}:
        parts.append(f"{specs['ram_gb']}GB")
    if specs.get("screen_size_inch") and category == "television":
        parts.append(f"{specs['screen_size_inch']} inch")
    query = " ".join(parts)
    if len(query) < 8:
        return None
    return query[:120]


def _fingerprint(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()[:32]


def single_store_overlap_candidates(*, limit: int = 40) -> list[dict[str, Any]]:
    """Public matched products with exactly one retailer and strong model identity."""
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with single as (
                  select pl.product_id,
                         min(pl.category) as category,
                         count(distinct pl.platform) as store_count,
                         array_agg(distinct pl.platform) as platforms
                  from platform_listings pl
                  where pl.match_status = 'matched'
                    and pl.product_id is not null
                    and pl.current_price is not null
                  group by pl.product_id
                  having count(distinct pl.platform) = 1
                )
                select s.product_id, s.category, s.platforms[1] as source_platform,
                       pc.brand, pc.canonical_title, pc.specs,
                       pl.current_price
                from single s
                join product_clusters pc on pc.id = s.product_id
                join lateral (
                  select current_price from platform_listings pl
                  where pl.product_id = s.product_id and pl.match_status = 'matched'
                  order by last_successful_refresh_at desc nulls last
                  limit 1
                ) pl on true
                where (
                    (
                      jsonb_typeof(pc.specs->'model_codes') = 'array'
                      and jsonb_array_length(pc.specs->'model_codes') > 0
                    )
                    or (
                      coalesce(pc.specs->>'family','') <> ''
                      and (
                        (s.category = 'smartphone' and (pc.specs ? 'storage_gb' or pc.specs ? 'ram_gb'))
                        or (s.category = 'television' and pc.specs ? 'screen_size_inch')
                        or (s.category not in ('smartphone','television'))
                      )
                    )
                  )
                order by
                  case s.category
                    when 'smartphone' then 0
                    when 'television' then 1
                    when 'tws' then 2
                    when 'headphones' then 3
                    when 'refrigerator' then 4
                    when 'washing_machine' then 5
                    when 'laptop' then 6
                    when 'camera' then 7
                    else 8
                  end,
                  pl.current_price desc nulls last
                limit %s
                """,
                (max(1, min(int(limit), 200)),),
            )
            return [dict(r) for r in cur.fetchall()]


def missing_platforms(present: str, category: str) -> list[str]:
    present_l = (present or "").lower()
    out: list[str] = []
    for plat in (*PRIMARY_OVERLAP_PLATFORMS, *SECONDARY_OVERLAP_PLATFORMS):
        if plat == present_l:
            continue
        if not discovery_allowed(plat, category):
            continue
        out.append(plat)
    return out


def materialize_targeted_discovery(*, limit: int = 16) -> int:
    """Enqueue bounded targeted_discovery / discovery_search tasks for overlap."""
    candidates = single_store_overlap_candidates(limit=max(limit * 3, limit))
    created = 0
    with db_connection() as conn:
        for row in candidates:
            if created >= limit:
                break
            category = str(row.get("category") or "")
            specs = row.get("specs") if isinstance(row.get("specs"), dict) else {}
            codes = list(specs.get("model_codes") or [])
            query = build_overlap_query(
                brand=row.get("brand") or specs.get("brand"),
                model_codes=codes,
                category=category,
                specs=specs,
            )
            if not query:
                continue
            fp = _fingerprint(query)
            product_id = str(row["product_id"])
            for target in missing_platforms(str(row.get("source_platform") or ""), category):
                if created >= limit:
                    break
                # Cooldown check
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select last_attempted_at, last_result
                        from overlap_discovery_attempts
                        where product_id = %s::uuid
                          and target_platform = %s
                          and query_fingerprint = %s
                          and last_attempted_at > now() - make_interval(hours => %s)
                        """,
                        (product_id, target, fp, OVERLAP_COOLDOWN_HOURS),
                    )
                    if cur.fetchone():
                        continue
                ensure_today_budget(target)
                if not platform_allows_task(target, "discovery") or not budget_available(target, "discovery"):
                    continue
                create_task(
                    conn,
                    target,
                    "targeted_discovery",
                    query=query,
                    max_pages=1,
                    max_products=12,
                    priority=OVERLAP_PRIORITY,
                    metadata={
                        "source": "overlap_v1",
                        "purpose": "cross_retailer_overlap",
                        "anchor_product_id": product_id,
                        "category": category,
                        "query_fingerprint": fp,
                        "model_codes": codes[:4],
                    },
                    idempotency_key=f"targeted_discovery:{product_id}:{target}:{fp}",
                    created_by="scheduler",
                )
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into overlap_discovery_attempts(
                          product_id, target_platform, query_fingerprint, last_result
                        ) values (%s::uuid, %s, %s, 'enqueued')
                        on conflict (product_id, target_platform, query_fingerprint) do update set
                          last_attempted_at = now(),
                          last_result = 'enqueued'
                        """,
                        (product_id, target, fp),
                    )
                created += 1
    return created


def record_overlap_attempt_result(
    *,
    product_id: str,
    target_platform: str,
    query_fingerprint: str,
    result: str,
    candidates_found: int = 0,
    exact_matches: int = 0,
) -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into overlap_discovery_attempts(
                  product_id, target_platform, query_fingerprint,
                  last_result, candidates_found, exact_matches
                ) values (%s::uuid, %s, %s, %s, %s, %s)
                on conflict (product_id, target_platform, query_fingerprint) do update set
                  last_attempted_at = now(),
                  last_result = excluded.last_result,
                  candidates_found = excluded.candidates_found,
                  exact_matches = excluded.exact_matches
                """,
                (
                    product_id,
                    target_platform,
                    query_fingerprint,
                    result,
                    candidates_found,
                    exact_matches,
                ),
            )


__all__ = [
    "OVERLAP_PRIORITY",
    "PRIMARY_OVERLAP_PLATFORMS",
    "build_overlap_query",
    "materialize_targeted_discovery",
    "record_overlap_attempt_result",
    "single_store_overlap_candidates",
]
