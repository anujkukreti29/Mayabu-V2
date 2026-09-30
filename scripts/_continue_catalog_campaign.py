"""Continue the catalog campaign after the smartphone feeder exits.

Seeds and materializes one category at a time. Stops if the golden
false-exact count is no longer zero. Does not clear retailer circuits.
"""

from __future__ import annotations

import json
import os
import time

from mayabu.domain.matching_golden import score_golden
from mayabu.search.index_manager import drain_dirty_search_documents
from mayabu_db.connection import db_connection
from scripts.run_catalog_expansion import materialize, pending_discovery, queue_snapshot, seed_plans

NEXT = (
    "smartphone",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
    "camera",
)
REPORT_DIR = "artifacts/catalog_campaign"


def remaining(category: str) -> int:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select count(*)::int n from scheduler_plans
            where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
              and coalesce(metadata->>'category','') = %s
              and last_materialized_at is null
            """,
            (category,),
        )
        return int(cur.fetchone()["n"])


def gate(category: str) -> dict:
    golden = score_golden()
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select count(*)::int n
            from product_search_documents
            where category = %s
              and offer_count is distinct from platform_count
            """,
            (category,),
        )
        mismatches = int(cur.fetchone()["n"])
        cur.execute(
            """
            select count(*)::int n from product_clusters
            where status = 'active' and category in ('unknown', 'accessory')
            """
        )
        unknown = int(cur.fetchone()["n"])
        cur.execute(
            """
            select platform, match_status, count(*)::int n
            from platform_listings
            where category = %s
            group by 1, 2
            order by 1, 2
            """,
            (category,),
        )
        listings = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select count(*)::int n from product_clusters
            where status = 'active' and category = %s
            """,
            (category,),
        )
        products = int(cur.fetchone()["n"])
    drained = drain_dirty_search_documents(limit=5000, strict=False)
    report = {
        "category": category,
        "false_exact_merges": golden["false_exact_merges"],
        "true_exact": golden["true_exact"],
        "search_offer_count_mismatches": mismatches,
        "public_unknown_or_accessory_products": unknown,
        "active_products": products,
        "listings": listings,
        "queue": queue_snapshot(),
        "search_drain": drained,
    }
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, f"{category}.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print("GATE", json.dumps({k: report[k] for k in report if k != "listings"}), flush=True)
    if report["false_exact_merges"] != 0:
        raise SystemExit(f"stop: false exact merges after {category}")
    if mismatches or unknown:
        raise SystemExit(f"stop: public integrity after {category}")
    return report


def feed(category: str) -> None:
    seed_plans(category, None)
    for _ in range(800):
        left = remaining(category)
        pend = pending_discovery()
        if pend < 6 and left:
            materialize(category, limit=min(8, left))
        snap = queue_snapshot()
        print("category", category, "remaining_plans", left, "queue", snap, flush=True)
        if left == 0 and pend == 0 and snap.get("running", 0) == 0 and snap.get("pending", 0) == 0:
            print("CATEGORY_QUEUE_DRAINED", category, flush=True)
            return
        time.sleep(20)
    raise SystemExit(f"stop: {category} did not drain")


def main() -> None:
    # Let the already-running smartphone feeder own the queue.
    while True:
        left = remaining("smartphone")
        snap = queue_snapshot()
        active = snap.get("pending", 0) + snap.get("running", 0)
        print("wait_smartphone", left, snap, flush=True)
        if left == 0 and active == 0:
            break
        time.sleep(30)
    gate("smartphone")
    for category in NEXT:
        if category == "smartphone":
            continue
        if remaining(category) == 0:
            # Plans may not exist yet.
            seeded = seed_plans(category, None)
            print("seeded", seeded, flush=True)
            if remaining(category) == 0 and queue_snapshot().get("pending", 0) == 0:
                # Every plan was stamped blocked (circuit) or already run.
                if seeded.get("plans"):
                    gate(category)
                    continue
        feed(category)
        gate(category)
    print("CAMPAIGN_CATEGORIES_DONE", flush=True)


if __name__ == "__main__":
    main()
