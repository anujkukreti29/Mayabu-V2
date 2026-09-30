"""Write the laptop campaign checkpoint and the pre-smartphone integrity gate."""

import json
import os

from mayabu.domain.matching_golden import score_golden
from mayabu_db.connection import db_connection

OUT = os.path.join("artifacts", "catalog_campaign", "laptop.json")

golden = score_golden()
report: dict = {
    "category": "laptop",
    "false_exact_merges": golden["false_exact_merges"],
    "true_exact": golden["true_exact"],
    "sample_count": golden["sample_count"],
}

with db_connection() as conn, conn.cursor() as cur:
    cur.execute("select current_database() db")
    if cur.fetchone()["db"] != "mayabu":
        raise SystemExit("refusing non-mayabu database")
    cur.execute(
        """
        select count(*)::int n
        from product_search_documents
        where category = 'laptop'
          and offer_count is distinct from platform_count
        """
    )
    report["search_offer_count_mismatches"] = cur.fetchone()["n"]
    cur.execute(
        """
        select count(*)::int n from (
          select product_id, platform
          from platform_listings
          where category = 'laptop'
            and match_status = 'matched'
            and product_id is not null
          group by 1, 2
          having count(*) > 1
        ) groups
        """
    )
    report["matched_same_platform_groups"] = cur.fetchone()["n"]
    cur.execute(
        """
        select count(*)::int n
        from product_clusters
        where status = 'active' and category in ('unknown', 'accessory')
        """
    )
    report["public_unknown_or_accessory_products"] = cur.fetchone()["n"]
    cur.execute("select count(*)::int n from search_document_dirty")
    report["dirty_search_documents"] = cur.fetchone()["n"]
    cur.execute(
        """
        select platform, match_status, count(*)::int n
        from platform_listings
        where category = 'laptop'
        group by 1, 2
        order by 1, 2
        """
    )
    report["listings"] = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select count(*)::int products
        from product_clusters
        where status = 'active' and category = 'laptop'
        """
    )
    report["active_products"] = cur.fetchone()["products"]
    cur.execute(
        """
        select platform, status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_expansion'
          and coalesce(metadata->>'category','') = 'laptop'
        group by 1, 2
        order by 1, 2
        """
    )
    report["tasks"] = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select
          count(*) filter (where metadata->>'completion' = 'circuit_blocked')::int blocked,
          count(*) filter (where last_materialized_at is null)::int waiting,
          count(*)::int plans
        from scheduler_plans
        where coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'category','') = 'laptop'
        """
    )
    report["plans"] = dict(cur.fetchone())

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2)
print(json.dumps(report, indent=2))
if report["false_exact_merges"] != 0:
    raise SystemExit("stop: false exact merges")
if report["search_offer_count_mismatches"] != 0:
    raise SystemExit("stop: public offer count mismatch")
if report["public_unknown_or_accessory_products"] != 0:
    raise SystemExit("stop: public unknown/accessory products")
