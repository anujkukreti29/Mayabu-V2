"""Residual same-platform offer integrity audit + safe remediation.

Internal-only. Classifies every matched same-platform group, audits smartphone
Flipkart (and other) color conflicts even when only one listing is attached,
and demotes hard mismatches without deleting observations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row

from mayabu.domain.categories.registry import extract_category_specs, get_adapter
from mayabu.domain.matching import assess_product_match
from mayabu.search.public_offers import (
    extract_color_token,
    product_color_hint,
    select_public_offers,
)
from mayabu_common import normalize_url


CAUSE_A = "A_same_sku_rediscovered"
CAUSE_B = "B_same_variant_url_alias"
CAUSE_C = "C_different_color"
CAUSE_D = "D_different_storage_ram"
CAUSE_E = "E_different_tv_size"
CAUSE_F = "F_different_camera_kit"
CAUSE_G = "G_different_laptop_config"
CAUSE_H = "H_accessory_contamination"
CAUSE_I = "I_seller_offer_duplication"
CAUSE_J = "J_ambiguous"


def _norm_native(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def _path_key(url: str) -> str:
    parts = urlsplit(normalize_url(url) or url or "")
    return f"{parts.netloc}{parts.path}".lower().rstrip("/")


def _listing_specs(row: dict[str, Any], category: str) -> dict[str, Any]:
    existing = row.get("specs") if isinstance(row.get("specs"), dict) else {}
    extracted = extract_category_specs(
        row.get("title") or "",
        category=category,
        url=row.get("listing_url") or "",
    )
    merged = {**extracted, **{k: v for k, v in existing.items() if v not in (None, "", [], {})}}
    # Prefer explicit color tokens from title/url when adapter missed retailer colors.
    if not merged.get("color"):
        token = extract_color_token(row.get("title") or "") or extract_color_token(
            row.get("listing_url") or ""
        )
        if token:
            merged["color"] = token
    return merged


def _product_payload(title: str, category: str, specs: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_title": title,
        "category": category,
        "specs": specs,
        "title": title,
    }


def _listing_payload(row: dict[str, Any], category: str, specs: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": row.get("title") or "",
        "category": category,
        "specs": specs,
        "url": row.get("listing_url") or "",
        "platform": row.get("platform"),
        "native_id": row.get("native_id"),
    }


def classify_group(
    *,
    category: str,
    product_title: str,
    product_specs: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Return (cause, listing_conflict_details)."""
    adapter = get_adapter(category)
    product = _product_payload(product_title, category, product_specs)
    details: list[dict[str, Any]] = []
    hard_reasons: Counter[str] = Counter()
    native_ids = {_norm_native(r.get("native_id")) for r in rows}
    native_ids.discard(None)
    path_keys = {_path_key(r.get("listing_url") or "") for r in rows}
    path_keys.discard("")
    norm_urls = {normalize_url(r.get("listing_url") or "") for r in rows}
    norm_urls.discard("")

    for row in rows:
        specs = _listing_specs(row, category)
        assessment = assess_product_match(_listing_payload(row, category, specs), product)
        conflicts = []
        if adapter:
            conflicts = adapter.hard_conflicts(product_specs, specs)
        for reason in conflicts:
            hard_reasons[reason] += 1
        details.append(
            {
                "listing_id": row["id"],
                "native_id": row.get("native_id"),
                "title": (row.get("title") or "")[:120],
                "url": row.get("listing_url"),
                "normalized_url": normalize_url(row.get("listing_url") or ""),
                "specs": {
                    k: specs.get(k)
                    for k in (
                        "color",
                        "ram_gb",
                        "storage_gb",
                        "screen_inch",
                        "screen_size_inch",
                        "capacity_l",
                        "capacity_kg",
                        "kit_type",
                        "gpu",
                        "cpu_series",
                        "cpu_models",
                        "model_codes",
                    )
                    if specs.get(k) is not None
                },
                "hard_conflicts": conflicts,
                "relation": getattr(assessment, "relation", None),
                "merge_allowed": bool(getattr(assessment, "merge_allowed", False)),
                "_full_specs": specs,
            }
        )

    # Pairwise listing conflicts (product may lack an axis that differs among listings).
    if adapter and len(details) >= 2:
        for i in range(len(details)):
            for j in range(i + 1, len(details)):
                pair = adapter.hard_conflicts(
                    details[i]["_full_specs"], details[j]["_full_specs"]
                )
                for reason in pair:
                    hard_reasons[reason] += 1
                    for idx in (i, j):
                        existing = set(details[idx]["hard_conflicts"])
                        existing.update(pair)
                        details[idx]["hard_conflicts"] = sorted(existing)

    if hard_reasons.get("color"):
        return CAUSE_C, details
    if hard_reasons.get("storage_gb") or hard_reasons.get("ram_gb"):
        return CAUSE_D, details
    if hard_reasons.get("screen_inch") or hard_reasons.get("screen_size_inch"):
        return CAUSE_E, details
    if hard_reasons.get("kit_type") or hard_reasons.get("body_kit"):
        return CAUSE_F, details
    if category == "laptop" and (
        hard_reasons.get("gpu")
        or hard_reasons.get("cpu_series")
        or hard_reasons.get("cpu_models")
        or hard_reasons.get("model_code")
        or hard_reasons.get("storage_gb")
        or hard_reasons.get("ram_gb")
    ):
        return CAUSE_G, details
    if any(d.get("relation") == "conflict" and not d.get("merge_allowed") for d in details):
        # Accessory / identity conflict without specific axis
        titles = " ".join((r.get("title") or "").lower() for r in rows)
        if any(
            tok in titles
            for tok in ("case", "cover", "tempered", "charger", "cable", "stand", "mount", "bag")
        ):
            return CAUSE_H, details
    if len(native_ids) == 1 and len(rows) > 1:
        return CAUSE_A, details
    if len(norm_urls) == 1 and len(rows) > 1:
        return CAUSE_A, details
    if len(path_keys) == 1 and len(rows) > 1:
        return CAUSE_B, details
    # Same variant axes, different URLs/natives → alias
    colors = {str(d["specs"].get("color") or "") for d in details if d["specs"].get("color")}
    storages = {d["specs"].get("storage_gb") for d in details if d["specs"].get("storage_gb") is not None}
    rams = {d["specs"].get("ram_gb") for d in details if d["specs"].get("ram_gb") is not None}
    cpus = {
        str(d["specs"].get("cpu_series") or d["specs"].get("cpu_models") or "")
        for d in details
        if d["specs"].get("cpu_series") or d["specs"].get("cpu_models")
    }
    gpus = {str(d["specs"].get("gpu") or "") for d in details if d["specs"].get("gpu")}
    if category == "laptop" and ((len(cpus) > 1) or (len(gpus) > 1)):
        return CAUSE_G, details
    if len(colors) <= 1 and len(storages) <= 1 and len(rams) <= 1:
        if len(native_ids) > 1 or len(norm_urls) > 1:
            return CAUSE_B, details
        return CAUSE_A, details
    # Soft color-only differences on non-smartphone (headphones/TWS) with matching model:
    # treat as same-variant retailer aliases for public collapse; do not demote.
    if (
        category in {"headphones", "tws", "audio"}
        and len(colors) > 1
        and len(storages) <= 1
        and all(d.get("merge_allowed") for d in details)
    ):
        return CAUSE_B, details
    if any(not d.get("merge_allowed") for d in details):
        return CAUSE_J, details
    return CAUSE_J, details


def demote_listing(cur, listing_id: str, reason: str, evidence: dict[str, Any]) -> int:
    payload = {"demote_reason": reason, **evidence}
    cur.execute(
        """
        update platform_listings
        set match_status = 'needs_review',
            match_evidence = coalesce(match_evidence, '{}'::jsonb)
              || %s::jsonb,
            updated_at = now()
        where id = %s::uuid and match_status = 'matched'
        """,
        (json.dumps(payload), listing_id),
    )
    return cur.rowcount


def choose_authoritative(rows: list[dict[str, Any]], *, category: str, title: str, specs: dict) -> str | None:
    selected = select_public_offers(
        [dict(r) for r in rows],
        category=category,
        product_title=title,
        product_specs=specs,
    )
    if not selected:
        return None
    return str(selected[0].get("id") or "")


def audit_flipkart_colors(cur, *, apply: bool) -> dict[str, Any]:
    """Demote any matched smartphone Flipkart listing with known conflicting color."""
    report = {
        "scanned": 0,
        "confirmed": 0,
        "demoted": 0,
        "ambiguous": 0,
        "unchanged": 0,
        "by_platform": Counter(),
        "samples": [],
    }
    cur.execute(
        """
        select pc.id::text as product_id, pc.canonical_title, pc.category, pc.specs,
               l.id::text as listing_id, l.platform, l.title, l.listing_url, l.native_id,
               l.specs as listing_specs, l.current_price, l.stock_status
        from platform_listings l
        join product_clusters pc on pc.id = l.product_id
        where l.match_status = 'matched'
          and pc.status = 'active'
          and pc.category = 'smartphone'
          and l.platform = any(%s)
        order by pc.id, l.platform
        """,
        (["flipkart", "amazon", "croma", "reliancedigital", "vijaysales", "poorvika"],),
    )
    rows = cur.fetchall()
    color_coverage: dict[str, Counter] = {}
    for row in rows:
        platform = row["platform"]
        cov = color_coverage.setdefault(platform, Counter())
        listing_specs = _listing_specs(row, "smartphone")
        if listing_specs.get("color"):
            cov["with_color"] += 1
        else:
            cov["without_color"] += 1

        preferred = product_color_hint(
            title=row["canonical_title"],
            specs=row["specs"] if isinstance(row["specs"], dict) else {},
        )
        listing_color = listing_specs.get("color")
        report["scanned"] += 1
        report["by_platform"][platform] += 1
        if not preferred or not listing_color:
            report["ambiguous"] += 1
            continue
        if preferred == listing_color:
            report["confirmed"] += 1
            report["unchanged"] += 1
            continue
        # Hard conflict: demote even if sole Flipkart offer.
        if apply:
            demoted = demote_listing(
                cur,
                row["listing_id"],
                "color_variant_mismatch",
                {
                    "preferred_color": preferred,
                    "listing_color": listing_color,
                    "source": "residual_offer_integrity_color_audit",
                },
            )
            report["demoted"] += demoted
        else:
            report["demoted"] += 1
        if len(report["samples"]) < 20:
            report["samples"].append(
                {
                    "product_id": row["product_id"],
                    "platform": platform,
                    "preferred": preferred,
                    "listing_color": listing_color,
                    "title": (row.get("title") or "")[:90],
                }
            )
    report["color_coverage"] = {k: dict(v) for k, v in color_coverage.items()}
    report["by_platform"] = dict(report["by_platform"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", default="artifacts/residual_offer_integrity.json")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL required", file=sys.stderr)
        return 2

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    report: dict[str, Any] = {
        "groups": [],
        "cause_counts": Counter(),
        "by_retailer": Counter(),
        "demoted": 0,
        "true_duplicates": 0,
        "variant_conflicts": 0,
        "ambiguous": 0,
        "flipkart_color_audit": {},
        "authoritative_kept": 0,
    }

    with psycopg.connect(url, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select product_id::text as product_id, platform, count(*)::int as n
            from platform_listings
            where product_id is not null and match_status = 'matched'
            group by 1, 2
            having count(*) > 1
            order by n desc, product_id, platform
            """
        )
        groups = cur.fetchall()

        for g in groups:
            pid = g["product_id"]
            platform = g["platform"]
            report["by_retailer"][platform] += 1
            cur.execute(
                """
                select pc.canonical_title, pc.category, pc.specs as product_specs,
                       l.id::text as id, l.platform, l.native_id, l.listing_id as public_listing_id,
                       l.listing_url, l.listing_url_hash, l.title, l.specs,
                       l.current_price, l.stock_status, l.match_status, l.match_confidence,
                       l.match_method, l.match_evidence, l.last_seen_at, l.last_verified_at,
                       l.last_successful_refresh_at, l.currency
                from platform_listings l
                join product_clusters pc on pc.id = l.product_id
                where l.product_id = %s::uuid and l.platform = %s and l.match_status = 'matched'
                order by l.last_seen_at desc nulls last, l.id
                """,
                (pid, platform),
            )
            rows = [dict(r) for r in cur.fetchall()]
            if len(rows) < 2:
                continue
            title = rows[0]["canonical_title"] or ""
            category = (rows[0].get("category") or "unknown").lower()
            product_specs = rows[0]["product_specs"] if isinstance(rows[0]["product_specs"], dict) else {}
            if not product_specs.get("category"):
                product_specs = {**product_specs, "category": category}
            # Enrich product color from title when missing.
            if not product_specs.get("color"):
                hint = product_color_hint(title=title, specs=product_specs)
                if hint:
                    product_specs = {**product_specs, "color": hint}

            cause, details = classify_group(
                category=category,
                product_title=title,
                product_specs=product_specs,
                rows=rows,
            )
            report["cause_counts"][cause] += 1
            primary = choose_authoritative(rows, category=category, title=title, specs=product_specs)
            for d in details:
                d.pop("_full_specs", None)
            group_rec = {
                "product_id": pid,
                "canonical_title": title,
                "category": category,
                "platform": platform,
                "matched_listings": len(rows),
                "cause": cause,
                "authoritative_listing_id": primary,
                "listings": details,
                "native_ids": sorted({_norm_native(r.get("native_id")) for r in rows} - {None}),
                "normalized_urls": sorted(
                    {normalize_url(r.get("listing_url") or "") for r in rows} - {""}
                ),
            }
            report["groups"].append(group_rec)

            conflict_causes = {CAUSE_C, CAUSE_D, CAUSE_E, CAUSE_F, CAUSE_G, CAUSE_H}
            if cause in conflict_causes:
                report["variant_conflicts"] += 1
                if args.apply and primary:
                    for row in rows:
                        if row["id"] == primary:
                            report["authoritative_kept"] += 1
                            continue
                        # Only demote listings that actually conflict with the product.
                        detail = next((d for d in details if d["listing_id"] == row["id"]), None)
                        if detail and (
                            detail.get("hard_conflicts") or not detail.get("merge_allowed")
                        ):
                            report["demoted"] += demote_listing(
                                cur,
                                row["id"],
                                f"residual_{cause}",
                                {
                                    "preferred_listing_id": primary,
                                    "hard_conflicts": detail.get("hard_conflicts") or [],
                                    "source": "residual_offer_integrity",
                                },
                            )
            elif cause in {CAUSE_A, CAUSE_B, CAUSE_I}:
                report["true_duplicates"] += 1
                # Keep all matched for evidence; public layer selects one.
                # Optionally demote non-authoritative exact URL clones only when
                # native_id + normalized URL are identical.
                if args.apply and primary and cause == CAUSE_A:
                    natives = {_norm_native(r.get("native_id")) for r in rows} - {None}
                    norms = {normalize_url(r.get("listing_url") or "") for r in rows} - {""}
                    if len(natives) <= 1 and len(norms) <= 1:
                        for row in rows:
                            if row["id"] == primary:
                                report["authoritative_kept"] += 1
                                continue
                            report["demoted"] += demote_listing(
                                cur,
                                row["id"],
                                "same_sku_duplicate_secondary",
                                {
                                    "preferred_listing_id": primary,
                                    "source": "residual_offer_integrity",
                                },
                            )
            else:
                report["ambiguous"] += 1

        color_report = audit_flipkart_colors(cur, apply=args.apply)
        report["flipkart_color_audit"] = color_report
        # Color audit demotions are separate from group demotions.
        if args.apply:
            report["demoted"] += int(color_report.get("demoted") or 0)
            # Mark affected products dirty for search rebuild.
            cur.execute(
                """
                select mark_search_document_dirty(product_id, 'residual_offer_integrity')
                from (
                  select distinct product_id
                  from platform_listings
                  where match_evidence->>'source' in (
                    'residual_offer_integrity',
                    'residual_offer_integrity_color_audit'
                  )
                  or match_evidence->>'demote_reason' like 'residual_%'
                  or match_evidence->>'demote_reason' = 'color_variant_mismatch'
                  or match_evidence->>'demote_reason' = 'same_sku_duplicate_secondary'
                ) t
                """
            )
            conn.commit()

    report["cause_counts"] = dict(report["cause_counts"])
    report["by_retailer"] = dict(report["by_retailer"])
    report["group_count"] = len(report["groups"])
    report["product_count"] = len({g["product_id"] for g in report["groups"]})

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    summary = {
        k: report[k]
        for k in (
            "group_count",
            "product_count",
            "cause_counts",
            "by_retailer",
            "true_duplicates",
            "variant_conflicts",
            "ambiguous",
            "demoted",
            "authoritative_kept",
        )
    }
    summary["flipkart_color_audit"] = {
        k: report["flipkart_color_audit"].get(k)
        for k in ("scanned", "confirmed", "demoted", "ambiguous", "unchanged", "color_coverage")
    }
    print(json.dumps(summary, indent=2, default=str))
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
