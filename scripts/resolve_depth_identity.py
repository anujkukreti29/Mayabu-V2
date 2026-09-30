"""Classify needs-review and unknown listings. Apply only deterministic cases.

Laptop config splits stay off generic Core-i5 products. A specific CPU plus a
model code may form its own canonical product. Known hard conflicts are
rejected. Ambiguous rows stay in review.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter

from psycopg.types.json import Jsonb

from mayabu.domain.categories.laptop import LaptopAdapter
from mayabu.domain.phone_recovery import phone_recovery_verdict
from mayabu.domain.categories.registry import detect_category_result
from mayabu.domain.product_type import classify_product_type
from mayabu.search.index_manager import refresh_product_search_documents
from mayabu_db.connection import db_connection
from mayabu_db.repository import create_product
from mayabu_db.variant import build_variant_key

PUBLIC = {
    "laptop", "smartphone", "television", "refrigerator",
    "washing_machine", "tws", "headphones", "camera",
}
HARD_REJECT = {
    "color_variant_mismatch",
    "residual_C_different_color",
    "laptop_cpu_conflict",
}
_PHONE_BRAND = re.compile(
    r"\b(apple|iphone|samsung|galaxy|oneplus|google|pixel|xiaomi|redmi|poco|realme|"
    r"motorola|moto|nothing|vivo|oppo|iqoo|infinix|tecno|lava|nokia)\b",
    re.I,
)
_PHONE_SHAPE = re.compile(r"\b(\d+\s*gb|5g)\b", re.I)
_SPEC_FRAGMENT = re.compile(
    r"^(response time|exposure mode|refresh rate|display type|battery capacity|"
    r"\d+(\.\d+)?\s*cm\s*\()",
    re.I,
)
_UNSUPPORTED = re.compile(
    r"\b(monitor|smart\s*watch|galaxy\s*watch|action\s+camera|osmo|instax|"
    r"tablet|printer|soundbar|speaker|trimmer|kettle|mixer|air\s*fryer|"
    r"all[-\s]*in[-\s]*one)\b",
    re.I,
)
_ADAPTER = LaptopAdapter()


def _cpu_specific(specs: dict) -> bool:
    models = specs.get("cpu_models") or []
    if isinstance(models, str):
        models = [models]
    return any(len(str(item).split(":")) >= 3 for item in models)


def _model_code(specs: dict) -> str:
    raw = specs.get("model_codes") or specs.get("model_code") or []
    if isinstance(raw, str):
        raw = [raw]
    return str(raw[0]).upper() if raw else ""


def classify_unknown(title: str) -> str:
    text = title or ""
    if _SPEC_FRAGMENT.search(text.strip()):
        return "ambiguous"
    kind = classify_product_type(text, category="unknown")
    if str(kind).endswith("accessory") or kind in {"camera_lens", "accessory"}:
        return "accessory"
    if _UNSUPPORTED.search(text):
        return "unsupported"
    detected = detect_category_result(title=text, query=text)
    if detected.category == "accessory":
        return "accessory"
    if detected.category in PUBLIC and detected.confidence in {"high", "medium"}:
        if detected.category == "smartphone" or (
            _PHONE_BRAND.search(text) and _PHONE_SHAPE.search(text) and "laptop" not in text.lower()
        ):
            if _PHONE_BRAND.search(text) and _PHONE_SHAPE.search(text) and detected.category in {"unknown", "smartphone"}:
                return "smartphone"
        if detected.category != "unknown":
            return detected.category
    if phone_recovery_verdict(text) == "correct_smartphone" and not _UNSUPPORTED.search(text):
        return "smartphone"
    return "ambiguous"


def _cluster_key(specs: dict) -> tuple:
    gpu = str(specs.get("gpu") or specs.get("gpu_models") or "")
    return (
        _model_code(specs),
        str(specs.get("cpu_series") or ""),
        specs.get("ram_gb"),
        specs.get("storage_gb"),
        gpu,
    )


def resolve_reviews(apply: bool) -> dict:
    counts: Counter = Counter()
    created = attached = rejected = left = 0
    affected: set[str] = set()
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, title, listing_url, category, match_evidence, product_id
            from platform_listings
            where match_status = 'needs_review'
              and category = any(%s)
            """,
            (list(PUBLIC),),
        )
        rows = list(cur.fetchall())
    groups: dict[tuple, list] = {}
    for row in rows:
        reason = str((row.get("match_evidence") or {}).get("demote_reason") or "")
        if reason in HARD_REJECT:
            counts[f"reject:{reason}"] += 1
            if apply:
                with db_connection() as conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        update platform_listings
                        set match_status = 'rejected',
                            product_id = null,
                            match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                            updated_at = now()
                        where id = %s and match_status = 'needs_review'
                        """,
                        (Jsonb({"auto_resolution": "hard_conflict_reject", "demote_reason": reason}), row["id"]),
                    )
            rejected += 1
            continue
        if reason != "laptop_config_hard_conflict":
            counts["still_review:unclassified"] += 1
            left += 1
            continue
        if row.get("product_id"):
            counts["still_review:already_linked"] += 1
            left += 1
            continue
        specs = _ADAPTER.extract_specs(row["title"] or "", url=row.get("listing_url") or "")
        specs["category"] = "laptop"
        if not _cpu_specific(specs) or not _model_code(specs):
            counts["still_review:laptop_identity_incomplete"] += 1
            left += 1
            continue
        groups.setdefault(_cluster_key(specs), []).append((row, specs))
        counts["laptop_specific_cluster"] += 1

    for key, members in groups.items():
        model = key[0]
        sample = members[0][1]
        product_id = None
        with db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, specs
                from product_clusters
                where status = 'active' and category = 'laptop'
                  and (
                    upper(coalesce(specs->>'model_code','')) = %s
                    or upper(coalesce(specs->>'model_codes_text','')) like %s
                    or canonical_title ilike %s
                  )
                limit 20
                """,
                (model, f"%{model}%", f"%{model}%"),
            )
            candidates = list(cur.fetchall())
        safe = []
        for candidate in candidates:
            product_specs = candidate.get("specs") if isinstance(candidate.get("specs"), dict) else {}
            if not _cpu_specific(product_specs):
                continue
            if _ADAPTER.hard_conflicts(product_specs, sample):
                continue
            safe.append(str(candidate["id"]))
        if len(safe) == 1:
            product_id = safe[0]
            attached += len(members)
            counts["auto_promoted_existing"] += len(members)
        elif apply:
            listing = {
                "title": members[0][0]["title"],
                "title_norm": members[0][0]["title"],
                "category": "laptop",
                "specs": sample,
                "brand": sample.get("brand"),
            }
            with db_connection() as conn:
                product_id = create_product(conn, listing, build_variant_key(sample, listing["title"]))
            created += 1
            attached += len(members)
            counts["new_canonical"] += 1
        else:
            counts["would_create"] += 1
            attached += len(members)
        if apply and product_id:
            affected.add(product_id)
            with db_connection() as conn, conn.cursor() as cur:
                for row, specs in members:
                    cur.execute(
                        """
                        update platform_listings
                        set product_id = %s::uuid,
                            match_status = 'matched',
                            category = 'laptop',
                            specs = %s::jsonb,
                            match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                            updated_at = now()
                        where id = %s and product_id is null and match_status = 'needs_review'
                        """,
                        (
                            product_id,
                            Jsonb(specs),
                            Jsonb({"auto_resolution": "laptop_config_recluster", "model_code": model}),
                            row["id"],
                        ),
                    )
    if apply and affected:
        refresh_product_search_documents(list(affected), strict=False)
    return {
        "rows": len(rows),
        "rejected": rejected,
        "attached_listings": attached,
        "new_products": created,
        "left_in_review": left,
        "detail": dict(counts),
    }


def resolve_unknown(apply: bool) -> dict:
    counts: Counter = Counter()
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select id, title
            from platform_listings
            where category = 'unknown'
            """
        )
        rows = list(cur.fetchall())
    recovered: dict[str, list] = {cat: [] for cat in PUBLIC}
    for row in rows:
        label = classify_unknown(row["title"] or "")
        counts[label] += 1
        if label in PUBLIC:
            recovered[label].append(row["id"])
        elif apply and label == "accessory":
            with db_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    update platform_listings
                    set category = 'accessory',
                        match_status = 'rejected',
                        match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                        updated_at = now()
                    where id = %s and category = 'unknown'
                    """,
                    (Jsonb({"auto_resolution": "accessory"}), row["id"]),
                )
        elif apply and label == "unsupported":
            with db_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    update platform_listings
                    set match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                        updated_at = now()
                    where id = %s and category = 'unknown'
                    """,
                    (Jsonb({"classification": "unsupported_outside_eight"}), row["id"]),
                )
    if apply:
        for category, ids in recovered.items():
            if not ids:
                continue
            with db_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    update platform_listings
                    set category = %s,
                        match_status = 'unmatched',
                        match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                        updated_at = now()
                    where id = any(%s::uuid[])
                      and category = 'unknown'
                    """,
                    (category, Jsonb({"auto_resolution": "unknown_recovered", "category": category}), ids),
                )
    return {"rows": len(rows), "detail": dict(counts)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reviews", action="store_true")
    parser.add_argument("--unknowns", action="store_true")
    args = parser.parse_args()
    report = {}
    if args.reviews:
        report["reviews"] = resolve_reviews(args.apply)
    if args.unknowns:
        report["unknowns"] = resolve_unknown(args.apply)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
