"""Report listing_url_hash duplicate groups. Does not delete or merge."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mayabu.db.connection import db_connection


QUERY = """
select
  l.platform,
  l.listing_url_hash,
  count(*)::int as row_count,
  array_agg(l.id::text order by l.updated_at desc) as listing_uuids,
  array_agg(l.match_status order by l.updated_at desc) as match_statuses,
  array_agg(l.product_id::text order by l.updated_at desc) as product_ids,
  bool_or(l.match_status = 'matched' and l.current_price is not null) as any_public_priced,
  max(l.last_successful_refresh_at) as latest_refresh
from platform_listings l
where l.listing_url_hash is not null
  and l.listing_url_hash <> ''
group by l.platform, l.listing_url_hash
having count(*) > 1
order by count(*) desc, l.platform
"""


def audit_duplicates() -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(QUERY)
            rows = [dict(row) for row in cur.fetchall()]
            cur.execute("select count(*) as n from platform_listings")
            total_listings = int(cur.fetchone()["n"])
    by_platform: dict[str, int] = defaultdict(int)
    public_groups = 0
    affected_rows = 0
    for row in rows:
        by_platform[str(row["platform"])] += 1
        affected_rows += int(row["row_count"])
        if row.get("any_public_priced"):
            public_groups += 1
    return {
        "total_listings": total_listings,
        "duplicate_groups": len(rows),
        "affected_rows": affected_rows,
        "groups_with_public_priced_member": public_groups,
        "groups_by_platform": dict(by_platform),
        "unique_constraint": "deferred",
        "index": "idx_platform_listings_platform_urlhash_active (non-unique)",
        "groups": rows[:200],
        "truncated": len(rows) > 200,
    }


def survivor_plan(group: dict[str, Any]) -> dict[str, Any]:
    """Recommend a survivor. Never auto-deletes ambiguous groups."""
    statuses = list(group.get("match_statuses") or [])
    uuids = list(group.get("listing_uuids") or [])
    products = list(group.get("product_ids") or [])
    matched_ids = [uuids[i] for i, status in enumerate(statuses) if status == "matched"]
    unique_products = {pid for pid in products if pid and pid != "None"}
    if len(matched_ids) == 1 and len(unique_products) <= 1:
        return {"action": "safe_keep", "survivor": matched_ids[0], "reason": "single_matched_member"}
    if len(matched_ids) > 1 or len(unique_products) > 1:
        return {"action": "defer", "reason": "ambiguous_match_or_product"}
    return {"action": "defer", "reason": "no_single_matched_survivor", "keep_newest": uuids[0] if uuids else None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit platform listing URL-hash duplicates.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit_duplicates()
    report["cleanup"] = [survivor_plan(group) for group in report["groups"]]
    safe = sum(1 for item in report["cleanup"] if item["action"] == "safe_keep")
    deferred = sum(1 for item in report["cleanup"] if item["action"] == "defer")
    report["safe_keep_groups"] = safe
    report["deferred_groups"] = deferred
    report["destructive_cleanup"] = False
    if args.json:
        print(json.dumps(report, default=str, indent=2))
    else:
        print(
            f"duplicate_groups={report['duplicate_groups']} "
            f"affected_rows={report['affected_rows']} "
            f"platforms={report['groups_by_platform']} "
            f"public_priced_groups={report['groups_with_public_priced_member']} "
            f"safe_keep={safe} deferred={deferred} (no deletes)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
