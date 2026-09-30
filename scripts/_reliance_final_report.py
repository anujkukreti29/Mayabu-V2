"""Write the Reliance depth drain report and fill blank page-40 stop reasons."""
import json
from pathlib import Path

from mayabu.scheduler.discovery_cursor import persist_plan_cursor
from mayabu_db.connection import db_connection

OUT = Path("artifacts/catalog_depth_v2_completion")
OUT.mkdir(parents=True, exist_ok=True)

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select id::text, query
        from scheduler_plans
        where platform = 'reliancedigital'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce((metadata#>>'{cursor,last_page}')::int, 0) >= 40
          and coalesce(metadata#>>'{cursor,stop_reason}','') in ('', 'page_budget', 'product_budget')
        """
    )
    ceiling = list(cur.fetchall())
for row in ceiling:
    persist_plan_cursor(row["id"], last_page=40, listings_found=0, stop_reason="emergency_ceiling")

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select query,
               coalesce(metadata->>'category','') as category,
               coalesce((metadata#>>'{cursor,last_page}')::int, 0) as final_page,
               coalesce(metadata#>>'{cursor,stop_reason}','') as stop_reason,
               coalesce(metadata->>'completion','') as completion,
               metadata#>>'{cursor,new_ids}' as new_ids,
               metadata#>>'{cursor,duplicate_ids}' as duplicate_ids,
               metadata#>>'{cursor,listings_found}' as listings_found
        from scheduler_plans
        where platform = 'reliancedigital'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce((metadata#>>'{cursor,last_page}')::int, 0) > 8
        order by category, query
        """
    )
    beyond = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        select coalesce(metadata->>'completion','open') as completion,
               coalesce(metadata#>>'{cursor,stop_reason}','') as stop_reason,
               count(*)::int n
        from scheduler_plans
        where platform = 'reliancedigital'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
        group by 1, 2
        order by n desc
        """
    )
    mix = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        select status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_depth' and platform = 'reliancedigital'
          and status in ('pending','running','paused')
        group by 1
        """
    )
    inflight = [dict(r) for r in cur.fetchall()]

stops = {}
for row in beyond:
    reason = row["stop_reason"] or "(blank)"
    stops[reason] = stops.get(reason, 0) + 1
report = {
    "drained": not inflight,
    "inflight": inflight,
    "page40_stamped": [row["query"] for row in ceiling],
    "plan_mix": mix,
    "beyond_page_8": beyond,
    "beyond_page_8_count": len(beyond),
    "stop_reasons": stops,
}
(OUT / "reliance_depth_final.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({
    "beyond": len(beyond),
    "stops": stops,
    "stamped": report["page40_stamped"],
    "inflight": inflight,
    "mix": mix,
}, indent=2))
