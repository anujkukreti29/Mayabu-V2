"""Audit + soft-quarantine color-mismatched same-platform duplicates.

Keeps observations; demotes clearly wrong-color attachments to needs_review
when the canonical product has an explicit color and the listing title/url
exposes a different color. Prefer public selection over destructive deletes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg
from psycopg.rows import dict_row

from mayabu.search.public_offers import extract_color_token, product_color_hint, select_public_offers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Demote mismatched listings")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL required", file=sys.stderr)
        return 2

    report = {
        "products_with_same_platform_dups": 0,
        "listing_groups": 0,
        "exact_url_dup_groups": 0,
        "color_mismatches_found": 0,
        "demoted": 0,
        "by_platform": {},
        "samples": [],
    }

    with psycopg.connect(url, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select product_id::text as product_id, platform, count(*)::int as n
            from platform_listings
            where product_id is not null and match_status = 'matched'
            group by 1, 2
            having count(*) > 1
            order by n desc
            limit %s
            """,
            (args.limit,),
        )
        groups = cur.fetchall()
        report["listing_groups"] = len(groups)
        report["products_with_same_platform_dups"] = len({g["product_id"] for g in groups})
        for g in groups:
            plat = g["platform"]
            report["by_platform"][plat] = report["by_platform"].get(plat, 0) + int(g["n"])

        for g in groups:
            pid = g["product_id"]
            platform = g["platform"]
            cur.execute(
                """
                select pc.canonical_title, pc.specs,
                       l.id::text as id, l.platform, l.native_id, l.listing_url, l.title,
                       l.current_price, l.stock_status, l.match_status, l.match_confidence,
                       l.last_seen_at, l.last_verified_at, l.last_successful_refresh_at,
                       l.currency
                from platform_listings l
                join product_clusters pc on pc.id = l.product_id
                where l.product_id = %s::uuid and l.platform = %s and l.match_status = 'matched'
                """,
                (pid, platform),
            )
            rows = cur.fetchall()
            if not rows:
                continue
            title = rows[0]["canonical_title"]
            specs = rows[0]["specs"] if isinstance(rows[0]["specs"], dict) else {}
            category = str(specs.get("category") or "").lower()
            # Color demotion is high-confidence for smartphones; other categories
            # often use color words in non-color contexts (e.g. GPU lines).
            if category and category != "smartphone":
                continue
            preferred = product_color_hint(title=title, specs=specs)
            if not preferred:
                continue
            winners = {
                r["id"]
                for r in select_public_offers(
                    [dict(r) for r in rows],
                    category=(specs.get("category") if isinstance(specs, dict) else None),
                    product_title=title,
                    product_specs=specs,
                )
            }
            for row in rows:
                listing_color = extract_color_token(row.get("title") or "") or extract_color_token(
                    row.get("listing_url") or ""
                )
                if not listing_color or listing_color == preferred:
                    continue
                if row["id"] in winners:
                    continue
                report["color_mismatches_found"] += 1
                if len(report["samples"]) < 12:
                    report["samples"].append(
                        {
                            "product_id": pid,
                            "platform": platform,
                            "listing_id": row["id"],
                            "preferred": preferred,
                            "listing_color": listing_color,
                            "title": (row.get("title") or "")[:80],
                        }
                    )
                if args.apply:
                    cur.execute(
                        """
                        update platform_listings
                        set match_status = 'needs_review',
                            match_evidence = coalesce(match_evidence, '{}'::jsonb)
                              || jsonb_build_object(
                                   'demote_reason', 'color_variant_mismatch',
                                   'preferred_color', %s::text,
                                   'listing_color', %s::text
                                 ),
                            updated_at = now()
                        where id = %s::uuid and match_status = 'matched'
                        """,
                        (preferred, listing_color, row["id"]),
                    )
                    report["demoted"] += cur.rowcount
        if args.apply:
            conn.commit()

    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
