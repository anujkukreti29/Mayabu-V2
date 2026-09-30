"""Operational retailer×category readiness evidence (distinct from CONFIGURED)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from mayabu.db.connection import db_connection
from mayabu.platforms.coverage import (
    ALL_TRACKED_PLATFORMS,
    CATALOG_CATEGORIES,
    get_coverage,
    normalize_readiness,
)

OperationalState = Literal[
    "READY",
    "LIMITED",
    "EXPERIMENTAL",
    "DISABLED",
    "BLOCKED",
]


@dataclass(frozen=True, slots=True)
class OperationalEvidence:
    platform: str
    category: str
    configured: bool
    operational_state: OperationalState
    public_eligible: bool
    reason: str
    evidence: dict[str, Any]


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            create table if not exists retailer_category_ops_evidence (
              platform text not null,
              category text not null,
              operational_state text not null,
              public_eligible boolean not null default false,
              reason text not null default '',
              evidence jsonb not null default '{}'::jsonb,
              updated_at timestamptz not null default now(),
              primary key (platform, category)
            )
            """
        )


def record_ops_evidence(
    *,
    platform: str,
    category: str,
    operational_state: OperationalState,
    public_eligible: bool,
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    with db_connection() as conn:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into retailer_category_ops_evidence(
                  platform, category, operational_state, public_eligible, reason, evidence, updated_at
                ) values (%s,%s,%s,%s,%s,%s::jsonb, now())
                on conflict (platform, category) do update set
                  operational_state = excluded.operational_state,
                  public_eligible = excluded.public_eligible,
                  reason = excluded.reason,
                  evidence = retailer_category_ops_evidence.evidence || excluded.evidence,
                  updated_at = now()
                """,
                (
                    platform,
                    category,
                    operational_state,
                    public_eligible,
                    reason,
                    json.dumps(evidence or {}),
                ),
            )
        conn.commit()


def refresh_ops_matrix_from_catalog() -> list[OperationalEvidence]:
    """Derive honest operational states from live catalog + configured coverage."""
    out: list[OperationalEvidence] = []
    with db_connection() as conn:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                select platform, category,
                       count(*) filter (where match_status='matched')::int as matched,
                       count(*) filter (
                         where match_status='matched' and current_price is not null
                       )::int as priced,
                       count(*) filter (
                         where match_status='matched'
                           and last_successful_refresh_at > now() - interval '7 days'
                       )::int as freshish,
                       count(*) filter (where match_status='needs_review')::int as review_n
                from platform_listings
                where category = any(%s)
                group by 1, 2
                """,
                (list(CATALOG_CATEGORIES),),
            )
            stats = {(r["platform"], r["category"]): dict(r) for r in cur.fetchall()}

            # Multi-store contribution by platform/category
            cur.execute(
                """
                with multi as (
                  select product_id, category
                  from platform_listings
                  where match_status='matched' and product_id is not null
                  group by product_id, category
                  having count(distinct platform) >= 2
                )
                select pl.platform, pl.category, count(distinct pl.product_id)::int as multi_n
                from platform_listings pl
                join multi m on m.product_id = pl.product_id and m.category = pl.category
                where pl.match_status='matched'
                group by 1, 2
                """
            )
            multi = {(r["platform"], r["category"]): int(r["multi_n"]) for r in cur.fetchall()}

        for platform in ALL_TRACKED_PLATFORMS:
            for category in CATALOG_CATEGORIES:
                cell = get_coverage(platform, category)
                configured = bool(cell.ingestion_enabled) or cell.readiness in {
                    "production",
                    "experimental",
                }
                row = stats.get((platform, category), {})
                matched = int(row.get("matched") or 0)
                priced = int(row.get("priced") or 0)
                freshish = int(row.get("freshish") or 0)
                review_n = int(row.get("review_n") or 0)
                multi_n = int(multi.get((platform, category), 0))
                readiness = normalize_readiness(cell.status)

                if readiness in {"disabled", "blocked", "unsupported"}:
                    state: OperationalState = "BLOCKED" if readiness == "blocked" else "DISABLED"
                    public = False
                    reason = cell.notes or readiness
                elif readiness == "experimental":
                    state = "EXPERIMENTAL"
                    public = matched >= 3 and priced >= 2
                    reason = cell.notes or "Experimental retailer — limited public contribution"
                elif category == "camera":
                    state = "LIMITED"
                    public = matched >= 5 and priced >= 3
                    reason = "Camera operational density/gallery/challenge still LIMITED"
                elif matched < 3 or priced < 2:
                    state = "LIMITED"
                    public = False
                    reason = f"Insufficient matched/priced evidence (matched={matched}, priced={priced})"
                elif multi_n == 0 and category in {"tws", "television"} and platform == "amazon":
                    state = "LIMITED"
                    public = priced >= 2
                    reason = "Amazon overlap contribution weak for this category"
                else:
                    state = "READY"
                    public = True
                    reason = "Configured and catalog evidence passes operational gate"

                evidence = {
                    "matched": matched,
                    "priced": priced,
                    "fresh_7d": freshish,
                    "needs_review": review_n,
                    "multi_store_products": multi_n,
                    "configured_readiness": readiness,
                    "as_of": datetime.now(timezone.utc).isoformat(),
                }
                item = OperationalEvidence(
                    platform=platform,
                    category=category,
                    configured=configured,
                    operational_state=state,
                    public_eligible=public,
                    reason=reason,
                    evidence=evidence,
                )
                out.append(item)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into retailer_category_ops_evidence(
                          platform, category, operational_state, public_eligible, reason, evidence, updated_at
                        ) values (%s,%s,%s,%s,%s,%s::jsonb, now())
                        on conflict (platform, category) do update set
                          operational_state = excluded.operational_state,
                          public_eligible = excluded.public_eligible,
                          reason = excluded.reason,
                          evidence = excluded.evidence,
                          updated_at = now()
                        """,
                        (
                            platform,
                            category,
                            state,
                            public,
                            reason,
                            json.dumps(evidence),
                        ),
                    )
        conn.commit()
    return out


def ops_matrix_report() -> list[dict[str, Any]]:
    rows = refresh_ops_matrix_from_catalog()
    return [
        {
            "platform": r.platform,
            "category": r.category,
            "configured": r.configured,
            "operational_state": r.operational_state,
            "public_eligible": r.public_eligible,
            "reason": r.reason,
            "evidence": r.evidence,
        }
        for r in rows
    ]


__all__ = [
    "OperationalEvidence",
    "OperationalState",
    "ops_matrix_report",
    "record_ops_evidence",
    "refresh_ops_matrix_from_catalog",
]
