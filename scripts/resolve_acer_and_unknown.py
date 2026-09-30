"""Resolve Acer ALG Core5 vs Core7 ambiguity and clean unknown-category products."""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg
from psycopg.rows import dict_row

from mayabu.domain.categories.laptop import LaptopAdapter
from mayabu.domain.categories.registry import extract_category_specs, normalize_category_name
from mayabu.domain.matching import assess_product_match
from mayabu.search.index_manager import refresh_product_search_documents


def resolve_acer(cur, *, apply: bool) -> dict:
    adapter = LaptopAdapter()
    report = {"products": [], "split_demotions": 0, "confirmed_same": 0, "needs_review": 0}
    cur.execute(
        """
        select pc.id::text as product_id, pc.canonical_title, pc.specs, pc.category
        from product_clusters pc
        where pc.status = 'active'
          and pc.category = 'laptop'
          and (
            pc.canonical_title ilike '%ALG%'
            or pc.canonical_title ilike '%Core5%'
            or pc.canonical_title ilike '%Core 5%'
            or pc.canonical_title ilike '%Core7%'
            or pc.canonical_title ilike '%Core 7%'
          )
        """
    )
    products = cur.fetchall()
    for product in products:
        cur.execute(
            """
            select id::text as id, title, listing_url, native_id, match_status,
                   current_price, specs
            from platform_listings
            where product_id = %s::uuid and match_status = 'matched'
            """,
            (product["product_id"],),
        )
        listings = cur.fetchall()
        if len(listings) < 2:
            continue
        product_specs = dict(product["specs"] if isinstance(product["specs"], dict) else {})
        extracted = adapter.extract_specs(product["canonical_title"] or "")
        # Prefer non-empty extracted identity fields over empty/stale cluster specs.
        for key, value in extracted.items():
            existing = product_specs.get(key)
            if existing in (None, "", [], {}):
                product_specs[key] = value
        preferred_cpu = None
        cpu_models = product_specs.get("cpu_models") or []
        if isinstance(cpu_models, list) and cpu_models:
            preferred_cpu = str(cpu_models[0])
        elif product_specs.get("cpu_series"):
            preferred_cpu = str(product_specs["cpu_series"])
        # Persist corrected CPU identity on the cluster when missing.
        if apply and preferred_cpu and not (product["specs"] or {}).get("cpu_models"):
            cur.execute(
                """
                update product_clusters
                set specs = coalesce(specs, '{}'::jsonb)
                      || jsonb_build_object(
                           'cpu_models', %s::jsonb,
                           'cpu_series', %s::text
                         ),
                    updated_at = now()
                where id = %s::uuid
                """,
                (json.dumps([preferred_cpu]), preferred_cpu, product["product_id"]),
            )

        entry = {
            "product_id": product["product_id"],
            "title": product["canonical_title"],
            "preferred_cpu": preferred_cpu,
            "listings": [],
            "resolution": "needs_review",
        }
        conflicts = 0
        for row in listings:
            ls = adapter.extract_specs(row["title"] or "")
            hard = adapter.hard_conflicts(product_specs, ls)
            entry["listings"].append(
                {
                    "id": row["id"],
                    "title": (row["title"] or "")[:100],
                    "cpu_models": ls.get("cpu_models"),
                    "hard_conflicts": hard,
                }
            )
            if "cpu_models" in hard:
                conflicts += 1
        if conflicts:
            entry["resolution"] = "split"
        else:
            # Check pairwise among listings
            pairwise = False
            for i in range(len(listings)):
                for j in range(i + 1, len(listings)):
                    left = adapter.extract_specs(listings[i]["title"] or "")
                    right = adapter.extract_specs(listings[j]["title"] or "")
                    if adapter.hard_conflicts(left, right):
                        pairwise = True
                        break
                if pairwise:
                    break
            if pairwise:
                entry["resolution"] = "split"
            else:
                entry["resolution"] = "confirmed_same"
                report["confirmed_same"] += 1
        # Always demote hard CPU conflicts against preferred product identity.
        if apply and preferred_cpu and entry["resolution"] == "split":
            for row in listings:
                ls = adapter.extract_specs(row["title"] or "")
                if "cpu_models" not in adapter.hard_conflicts(product_specs, ls):
                    continue
                cur.execute(
                    """
                    update platform_listings
                    set match_status = 'needs_review',
                        match_evidence = coalesce(match_evidence, '{}'::jsonb)
                          || jsonb_build_object(
                               'demote_reason', 'laptop_cpu_conflict',
                               'preferred_cpu', %s::text,
                               'listing_cpu', %s::text,
                               'source', 'acer_resolution'
                             ),
                        updated_at = now()
                    where id = %s::uuid and match_status = 'matched'
                    """,
                    (
                        preferred_cpu,
                        ",".join(ls.get("cpu_models") or []) or None,
                        row["id"],
                    ),
                )
                report["split_demotions"] += cur.rowcount
        if entry["resolution"] == "needs_review":
            report["needs_review"] += 1
        report["products"].append(entry)
        if apply:
            cur.execute(
                "select mark_search_document_dirty(%s::uuid, %s)",
                (product["product_id"], "acer_resolution"),
            )
    return report


def clean_unknown(cur, *, apply: bool) -> dict:
    report = {
        "scanned": 0,
        "reclassified": [],
        "quarantined": [],
        "unchanged": [],
    }
    cur.execute(
        """
        select id::text as id, canonical_title, brand, specs, status
        from product_clusters
        where category = 'unknown' or category is null
        order by updated_at desc nulls last
        """
    )
    rows = cur.fetchall()
    report["scanned"] = len(rows)
    public = {
        "laptop",
        "smartphone",
        "television",
        "refrigerator",
        "washing_machine",
        "tws",
        "headphones",
        "camera",
    }
    for row in rows:
        title = row["canonical_title"] or ""
        # Try each public category extraction for strong signals
        assigned = None
        confidence = "low"
        for cat in public:
            specs = extract_category_specs(title, category=cat)
            # Deterministic: title/category keywords + model/spec presence
            from mayabu.domain.product_type import classify_product_type

            ptype = classify_product_type(title, category=cat)
            if ptype == "accessory":
                assigned = None
                confidence = "accessory"
                break
            if cat == "smartphone" and specs.get("storage_gb") and (
                "iphone" in title.lower() or "galaxy" in title.lower() or specs.get("family")
            ):
                assigned = "smartphone"
                confidence = "high"
                break
            if cat == "laptop" and (specs.get("ram_gb") or specs.get("cpu_series")) and (
                "laptop" in title.lower() or "notebook" in title.lower() or specs.get("model_codes")
            ):
                assigned = "laptop"
                confidence = "high"
                break
            if cat == "television" and (
                "tv" in title.lower() or "television" in title.lower() or specs.get("screen_inch")
            ):
                if specs.get("screen_inch") or "smart tv" in title.lower():
                    assigned = "television"
                    confidence = "medium"
                    break
            if cat == "headphones" and any(
                t in title.lower() for t in ("headphone", "headset", "wh-", "over-ear", "on-ear")
            ):
                assigned = "headphones"
                confidence = "medium"
                break
            if cat == "tws" and any(t in title.lower() for t in ("earbuds", "airpods", "galaxy buds", "tws")):
                assigned = "tws"
                confidence = "medium"
                break
            if cat == "camera" and any(
                t in title.lower() for t in ("mirrorless", "dslr", "camera", "eos", "alpha")
            ):
                assigned = "camera"
                confidence = "medium"
                break
            if cat == "refrigerator" and any(t in title.lower() for t in ("refrigerator", "fridge")):
                assigned = "refrigerator"
                confidence = "medium"
                break
            if cat == "washing_machine" and "washing" in title.lower():
                assigned = "washing_machine"
                confidence = "medium"
                break

        item = {
            "id": row["id"],
            "title": title[:120],
            "assigned": assigned,
            "confidence": confidence,
        }
        if assigned and confidence in {"high", "medium"}:
            report["reclassified"].append(item)
            if apply:
                cur.execute(
                    """
                    update product_clusters
                    set category = %s,
                        specs = coalesce(specs, '{}'::jsonb) || jsonb_build_object('category', %s::text),
                        updated_at = now()
                    where id = %s::uuid
                    """,
                    (assigned, assigned, row["id"]),
                )
                cur.execute(
                    "select mark_search_document_dirty(%s::uuid, %s)",
                    (row["id"], "unknown_reclassify"),
                )
        elif confidence == "accessory" or not assigned:
            report["quarantined"].append(item)
            if apply:
                # Soft quarantine: archived so public surfaces drop it
                cur.execute(
                    """
                    update product_clusters
                    set status = 'archived',
                        specs = coalesce(specs, '{}'::jsonb)
                          || jsonb_build_object('quarantine_reason', 'unknown_category'),
                        updated_at = now()
                    where id = %s::uuid and status = 'active'
                    """,
                    (row["id"],),
                )
                cur.execute(
                    "select mark_search_document_dirty(%s::uuid, %s)",
                    (row["id"], "unknown_quarantine"),
                )
        else:
            report["unchanged"].append(item)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", default="artifacts/acer_unknown_cleanup.json")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL required", file=sys.stderr)
        return 2

    with psycopg.connect(url, row_factory=dict_row) as conn, conn.cursor() as cur:
        acer = resolve_acer(cur, apply=args.apply)
        unknown = clean_unknown(cur, apply=args.apply)
        if args.apply:
            conn.commit()

    report = {"acer": acer, "unknown": unknown}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(
        json.dumps(
            {
                "acer_products": len(acer["products"]),
                "acer_split_demotions": acer["split_demotions"],
                "acer_resolutions": [p["resolution"] for p in acer["products"]],
                "unknown_scanned": unknown["scanned"],
                "unknown_reclassified": len(unknown["reclassified"]),
                "unknown_quarantined": len(unknown["quarantined"]),
            },
            indent=2,
        )
    )
    if args.apply:
        ids = [p["product_id"] for p in acer["products"]]
        ids += [u["id"] for u in unknown["reclassified"] + unknown["quarantined"]]
        print("refresh", refresh_product_search_documents(ids, strict=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
