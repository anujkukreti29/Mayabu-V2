"""Demote laptop listings that hard-conflict with their product after SKU extraction.

Keeps one authoritative matched listing per conflicting product. Does not delete
price history. Dev catalog `mayabu` only.
"""

from __future__ import annotations

import json

from psycopg.types.json import Jsonb

from mayabu.domain.categories.laptop import LaptopAdapter
from mayabu_db.connection import db_connection

ADAPTER = LaptopAdapter()
SPEC_KEYS = (
    "cpu_series",
    "cpu_models",
    "family",
    "gpu",
    "gpu_memory_gb",
    "model_codes",
    "ram_gb",
    "storage_gb",
)


def _fresh(title: str) -> dict:
    return ADAPTER.extract_specs(title or "")


def main() -> None:
    demoted = 0
    products = 0
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute("select current_database() db")
        if cur.fetchone()["db"] != "mayabu":
            raise SystemExit("refusing non-mayabu database")
        cur.execute(
            """
            select pc.id::text as product_id, pc.canonical_title, pc.specs,
                   l.id::text as listing_id, l.title
            from product_clusters pc
            join platform_listings l on l.product_id = pc.id
            where pc.category = 'laptop'
              and l.match_status = 'matched'
            order by pc.id, l.last_seen_at desc nulls last
            """
        )
        rows = cur.fetchall()
        grouped: dict[str, dict] = {}
        for row in rows:
            bucket = grouped.setdefault(
                row["product_id"],
                {
                    "title": row["canonical_title"] or "",
                    "specs": row["specs"] if isinstance(row["specs"], dict) else {},
                    "listings": [],
                },
            )
            bucket["listings"].append(row)

        dirty_ids: list[str] = []
        for product_id, bucket in grouped.items():
            extracted = [(row, _fresh(row["title"] or "")) for row in bucket["listings"]]
            conflict_ids: set[str] = set()
            for i in range(len(extracted)):
                for j in range(i + 1, len(extracted)):
                    reasons = ADAPTER.hard_conflicts(extracted[i][1], extracted[j][1])
                    if reasons:
                        conflict_ids.add(extracted[i][0]["listing_id"])
                        conflict_ids.add(extracted[j][0]["listing_id"])
            if not conflict_ids:
                continue
            products += 1
            canonical = _fresh(bucket["title"])
            ranked = sorted(
                extracted,
                key=lambda item: (
                    0 if item[0]["listing_id"] not in conflict_ids else 1,
                    0 if not ADAPTER.hard_conflicts(canonical, item[1]) else 1,
                    0 if (item[0]["title"] or "")[:40].lower() == bucket["title"][:40].lower() else 1,
                ),
            )
            keep = ranked[0][0]["listing_id"]
            keep_specs = ranked[0][1]
            for row, _specs in extracted:
                if row["listing_id"] == keep or row["listing_id"] not in conflict_ids:
                    continue
                cur.execute(
                    """
                    update platform_listings
                    set match_status = 'needs_review',
                        product_id = null,
                        match_evidence = coalesce(match_evidence, '{}'::jsonb) || %s::jsonb,
                        updated_at = now()
                    where id = %s::uuid and match_status = 'matched'
                    """,
                    (
                        Jsonb(
                            {
                                "demote_reason": "laptop_config_hard_conflict",
                                "kept_listing_id": keep,
                            }
                        ),
                        row["listing_id"],
                    ),
                )
                demoted += cur.rowcount
            overlay = {key: keep_specs.get(key) for key in SPEC_KEYS if keep_specs.get(key) not in (None, "", [])}
            if overlay:
                cur.execute(
                    """
                    update product_clusters
                    set specs = coalesce(specs, '{}'::jsonb) || %s::jsonb,
                        updated_at = now()
                    where id = %s::uuid
                    """,
                    (Jsonb(overlay), product_id),
                )
            dirty_ids.append(product_id)
        if dirty_ids:
            cur.execute(
                """
                insert into search_document_dirty(product_id, reason, dirty_at, attempts, last_error)
                select id::uuid, 'laptop_config_split', now(), 0, null
                from unnest(%s::text[]) as id
                on conflict (product_id) do update set
                  reason = excluded.reason,
                  dirty_at = now(),
                  claimed_at = null,
                  claimed_by = null,
                  last_error = null
                """,
                (dirty_ids,),
            )
    print(json.dumps({"products_split": products, "listings_demoted": demoted}))


if __name__ == "__main__":
    main()
