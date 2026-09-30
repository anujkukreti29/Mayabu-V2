import json
from pathlib import Path

from mayabu_db.connection import db_connection

out = Path("artifacts/catalog_depth_v2_completion")
out.mkdir(parents=True, exist_ok=True)
with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select query,
               coalesce(metadata->>'category','') as category,
               coalesce((metadata#>>'{cursor,last_page}')::int, 0) as final_page,
               coalesce(metadata#>>'{cursor,stop_reason}','') as stop_reason,
               coalesce(metadata->>'completion','') as completion,
               metadata#>>'{cursor,new_ids}' as new_ids,
               metadata#>>'{cursor,duplicate_ids}' as duplicate_ids
        from scheduler_plans
        where platform = 'flipkart'
          and coalesce(metadata->>'purpose','') = 'catalog_expansion_v1'
          and coalesce((metadata#>>'{cursor,last_page}')::int, 0) > 8
        order by category, query
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
(out / "flipkart_depth_progress.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
print("plans_past_8", len(rows))
print("stop", {r["stop_reason"] or "(blank)": sum(1 for x in rows if x["stop_reason"] == r["stop_reason"]) for r in rows})
