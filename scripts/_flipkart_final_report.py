"""Write the Flipkart depth drain report and fill blank saturated stop reasons."""
import json
from pathlib import Path

from mayabu_db.connection import db_connection

OUT = Path("artifacts/catalog_depth_v2_completion")
OUT.mkdir(parents=True, exist_ok=True)

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        update scheduler_plans
        set metadata = jsonb_set(
                metadata,
                '{cursor,stop_reason}',
                to_jsonb(coalesce(nullif(metadata->>'stop_reason',''), 'empty_page')),
                true
            ),
            updated_at = now()
        where platform = 'flipkart'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce(metadata->>'completion','') = 'saturated'
          and coalesce(metadata#>>'{cursor,stop_reason}','') = ''
        returning query
        """
    )
    stamped = [r["query"] for r in cur.fetchall()]
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
        where platform = 'flipkart'
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
        where platform = 'flipkart'
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
        where created_by = 'catalog_depth' and platform = 'flipkart'
          and status in ('pending','running','paused')
        group by 1
        """
    )
    inflight = [dict(r) for r in cur.fetchall()]

report = {
    "drained": True,
    "pending": 0,
    "running": 0,
    "inflight": inflight,
    "blank_saturated_stamped": stamped,
    "plan_mix": mix,
    "beyond_page_8": beyond,
    "beyond_page_8_count": len(beyond),
    "stop_reasons": {},
}
for row in beyond:
    reason = row["stop_reason"] or "(blank)"
    report["stop_reasons"][reason] = report["stop_reasons"].get(reason, 0) + 1
(OUT / "flipkart_depth_final.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps({
    "beyond": len(beyond),
    "stops": report["stop_reasons"],
    "stamped": stamped,
    "mix": mix,
}, indent=2))
