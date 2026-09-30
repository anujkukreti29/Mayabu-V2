"""Model primary vs alias for residual same-retailer matched groups.

Marks secondary listings with match_evidence:
  listing_role=alias, primary_listing_id=<uuid>
and demotes exact same-SKU URL clones to needs_review when safe.

Does not delete observations. Public select_public_offers still collapses by platform.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg
from psycopg.rows import dict_row

from mayabu.search.public_offers import select_public_offers
from mayabu_common import normalize_url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", default="artifacts/alias_modeling.json")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL required", file=sys.stderr)
        return 2

    report = {
        "groups_inspected": 0,
        "aliases_modeled": 0,
        "secondary_demoted": 0,
        "retained_matched_aliases": 0,
        "ambiguous": 0,
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
            """
        )
        groups = cur.fetchall()
        report["groups_inspected"] = len(groups)

        for g in groups:
            cur.execute(
                """
                select pc.canonical_title, pc.category, pc.specs,
                       l.id::text as id, l.platform, l.native_id, l.listing_url, l.title,
                       l.current_price, l.stock_status, l.match_status, l.match_confidence,
                       l.last_seen_at, l.last_verified_at, l.last_successful_refresh_at,
                       l.currency, l.match_evidence
                from platform_listings l
                join product_clusters pc on pc.id = l.product_id
                where l.product_id = %s::uuid and l.platform = %s and l.match_status = 'matched'
                """,
                (g["product_id"], g["platform"]),
            )
            rows = [dict(r) for r in cur.fetchall()]
            if len(rows) < 2:
                continue
            specs = rows[0]["specs"] if isinstance(rows[0]["specs"], dict) else {}
            category = rows[0].get("category") or specs.get("category")
            primary = select_public_offers(
                rows,
                category=category,
                product_title=rows[0].get("canonical_title"),
                product_specs=specs if isinstance(specs, dict) else {},
            )
            if not primary:
                report["ambiguous"] += 1
                continue
            primary_id = str(primary[0]["id"])
            natives = {str(r.get("native_id") or "").upper() for r in rows} - {""}
            norms = {normalize_url(r.get("listing_url") or "") for r in rows} - {""}
            exact_clone = len(natives) <= 1 and len(norms) <= 1

            for row in rows:
                lid = row["id"]
                if lid == primary_id:
                    if args.apply:
                        cur.execute(
                            """
                            update platform_listings
                            set match_evidence = coalesce(match_evidence, '{}'::jsonb)
                                  || jsonb_build_object('listing_role', 'primary'),
                                updated_at = now()
                            where id = %s::uuid
                            """,
                            (lid,),
                        )
                    continue
                report["aliases_modeled"] += 1
                if exact_clone and args.apply:
                    cur.execute(
                        """
                        update platform_listings
                        set match_status = 'needs_review',
                            match_evidence = coalesce(match_evidence, '{}'::jsonb)
                              || jsonb_build_object(
                                   'listing_role', 'alias',
                                   'primary_listing_id', %s::text,
                                   'demote_reason', 'same_sku_alias_secondary',
                                   'source', 'alias_modeling'
                                 ),
                            updated_at = now()
                        where id = %s::uuid and match_status = 'matched'
                        """,
                        (primary_id, lid),
                    )
                    report["secondary_demoted"] += cur.rowcount
                else:
                    report["retained_matched_aliases"] += 1
                    if args.apply:
                        cur.execute(
                            """
                            update platform_listings
                            set match_evidence = coalesce(match_evidence, '{}'::jsonb)
                                  || jsonb_build_object(
                                       'listing_role', 'alias',
                                       'primary_listing_id', %s::text,
                                       'source', 'alias_modeling'
                                     ),
                                updated_at = now()
                            where id = %s::uuid
                            """,
                            (primary_id, lid),
                        )
                if len(report["samples"]) < 12:
                    report["samples"].append(
                        {
                            "product_id": g["product_id"],
                            "platform": g["platform"],
                            "primary": primary_id,
                            "alias": lid,
                            "exact_clone": exact_clone,
                            "title": (row.get("title") or "")[:80],
                        }
                    )

            if args.apply:
                cur.execute(
                    "select mark_search_document_dirty(%s::uuid, %s)",
                    (g["product_id"], "alias_modeling"),
                )

        if args.apply:
            conn.commit()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
