"""Deterministic needs_review hygiene: auto-reject noise, auto-resolve when evidence allows."""

from __future__ import annotations

import json
import logging
from typing import Any

from mayabu.catalog.title_quality import is_marketing_bullet_title, sanitize_product_title
from mayabu.db.connection import db_connection
from mayabu.domain.identity_quality import has_sufficient_product_identity
from mayabu.domain.matching import assess_product_match
from mayabu.domain.product_type import classify_product_type
from mayabu.search.index_manager import refresh_product_search_documents

logger = logging.getLogger(__name__)


def _is_deterministic_noise(title: str, category: str, specs: dict[str, Any] | None = None) -> str | None:
    """Return reject reason when the listing is clearly not attachable identity."""
    text = (title or "").strip()
    if not text:
        return "empty_title"
    if is_marketing_bullet_title(text):
        return "marketing_or_brand_only_title"
    if not has_sufficient_product_identity(text, category, specs=specs):
        return "insufficient_identity"
    ptype = classify_product_type(text, category=category)
    if ptype.endswith("_accessory") or ptype == "accessory":
        return "accessory_product_type"
    return None


def process_review_backlog(*, limit: int = 80) -> dict[str, int]:
    """Auto-reject deterministic noise; rematch rows that now have enough identity."""
    rejected = 0
    resolved_exact = 0
    resolved_conflict = 0
    retained = 0
    affected: set[str] = set()

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, product_id, platform, title, title_norm, category, specs,
                       listing_id, listing_url
                from platform_listings
                where match_status = 'needs_review'
                order by updated_at desc nulls last
                limit %s
                """,
                (max(1, min(int(limit), 500)),),
            )
            rows = [dict(r) for r in cur.fetchall()]

        for row in rows:
            title = row.get("title") or ""
            category = str(row.get("category") or "unknown")
            specs = row.get("specs") if isinstance(row.get("specs"), dict) else {}
            noise = _is_deterministic_noise(title, category, specs)
            if noise:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        update platform_listings
                        set match_status = 'rejected',
                            match_method = 'review_auto_reject',
                            match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                            product_id = null,
                            updated_at = now()
                        where id = %s::uuid and match_status = 'needs_review'
                        """,
                        (json.dumps({"auto_reject": noise}), str(row["id"])),
                    )
                    if cur.rowcount:
                        rejected += 1
                continue

            # Rematch against brand/family candidates when identity is strong enough.
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select id, category, brand, canonical_title, title_norm, specs
                    from product_clusters
                    where category = %s
                      and (
                        coalesce(brand,'') = coalesce(%s,'')
                        or coalesce(specs->>'family','') = coalesce(%s,'')
                      )
                    order by updated_at desc nulls last
                    limit 40
                    """,
                    (
                        category,
                        specs.get("brand"),
                        specs.get("family"),
                    ),
                )
                candidates = [dict(r) for r in cur.fetchall()]

            listing_payload = {
                "title": title,
                "title_norm": row.get("title_norm"),
                "category": category,
                "specs": specs,
            }
            best_exact = None
            saw_conflict = False
            for cand in candidates:
                product = {
                    "product_id": str(cand["id"]),
                    "id": str(cand["id"]),
                    "category": cand.get("category"),
                    "canonical_title": cand.get("canonical_title"),
                    "title_norm": cand.get("title_norm"),
                    "brand": cand.get("brand"),
                    "specs": cand.get("specs") if isinstance(cand.get("specs"), dict) else {},
                }
                assessment = assess_product_match(listing_payload, product)
                if assessment.merge_allowed:
                    best_exact = (cand, assessment)
                    break
                if assessment.relation in {"conflict", "variant"}:
                    saw_conflict = True

            if best_exact:
                cand, assessment = best_exact
                clean_title = sanitize_product_title(title) or title
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        update platform_listings
                        set product_id = %s::uuid,
                            match_status = 'matched',
                            match_method = 'review_auto_exact',
                            match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                            title = %s,
                            updated_at = now()
                        where id = %s::uuid and match_status = 'needs_review'
                        """,
                        (
                            str(cand["id"]),
                            json.dumps(
                                {
                                    "auto_resolve": "exact",
                                    "relation": assessment.relation,
                                }
                            ),
                            clean_title[:500],
                            str(row["id"]),
                        ),
                    )
                    if cur.rowcount:
                        resolved_exact += 1
                        affected.add(str(cand["id"]))
                continue

            if saw_conflict:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        update platform_listings
                        set match_status = 'rejected',
                            match_method = 'review_auto_conflict',
                            match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                            updated_at = now()
                        where id = %s::uuid and match_status = 'needs_review'
                        """,
                        (
                            json.dumps({"auto_resolve": "conflict"}),
                            str(row["id"]),
                        ),
                    )
                    if cur.rowcount:
                        resolved_conflict += 1
                continue

            retained += 1

        conn.commit()

    if affected:
        try:
            refresh_product_search_documents(list(affected), strict=False)
        except Exception:
            logger.exception("review_hygiene_reindex_failed")

    return {
        "scanned": len(rows),
        "auto_rejected": rejected,
        "auto_exact": resolved_exact,
        "auto_conflict": resolved_conflict,
        "retained_review": retained,
    }


def quarantine_brand_only_matched(*, limit: int = 200) -> dict[str, int]:
    """Detach legacy brand-only matched listings from public catalog."""
    quarantined = 0
    affected: set[str] = set()
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, product_id, title, category, specs
                from platform_listings
                where match_status = 'matched'
                  and product_id is not null
                order by updated_at desc nulls last
                limit %s
                """,
                (max(1, min(int(limit), 1000)),),
            )
            rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            title = row.get("title") or ""
            category = str(row.get("category") or "unknown")
            specs = row.get("specs") if isinstance(row.get("specs"), dict) else {}
            if has_sufficient_product_identity(title, category, specs=specs):
                continue
            if not is_marketing_bullet_title(title) and len(title) >= 20:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update platform_listings
                    set match_status = 'rejected',
                        match_method = 'brand_only_quarantine',
                        match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                        product_id = null,
                        updated_at = now()
                    where id = %s::uuid and match_status = 'matched'
                    """,
                    (
                        json.dumps({"quarantine": "insufficient_identity"}),
                        str(row["id"]),
                    ),
                )
                if cur.rowcount:
                    quarantined += 1
                    if row.get("product_id"):
                        affected.add(str(row["product_id"]))
        conn.commit()
    if affected:
        try:
            refresh_product_search_documents(list(affected), strict=False)
        except Exception:
            logger.exception("brand_only_quarantine_reindex_failed")
    return {"quarantined": quarantined, "products_touched": len(affected)}


__all__ = ["process_review_backlog", "quarantine_brand_only_matched"]
