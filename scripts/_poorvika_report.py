"""Refresh the Poorvika checkpoint after the laptop exact-model pass."""
import json
from pathlib import Path

from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select metadata->>'category' as category, status, count(*)::int n
        from scrape_tasks
        where created_by = 'catalog_overlap' and platform = 'poorvika'
        group by 1, 2
        order by 1, 2
        """
    )
    tasks = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select query, status, last_error, coalesce((result->>'valid')::int, 0) as valid
        from scrape_tasks
        where created_by = 'catalog_overlap' and platform = 'amazon'
        order by created_at
        """
    )
    amazon = [dict(row) for row in cur.fetchall()]
report = {
    "platform": "poorvika",
    "categories": ["laptop", "smartphone"],
    "tasks": tasks,
    "note": "Exact model tokens only. Family sentences were cancelled. No broad Poorvika discovery.",
}
Path("artifacts/catalog_overlap_v1/poorvika.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps({"poorvika": report, "amazon": amazon}, indent=2, default=str))
