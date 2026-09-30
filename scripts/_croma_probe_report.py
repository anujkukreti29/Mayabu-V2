"""Record the four-query Croma probe and current circuit state."""
import json
from pathlib import Path

from mayabu.scheduler.platform_health_policy import platform_allows_task
from mayabu_db.connection import db_connection

with db_connection() as conn, conn.cursor() as cur:
    cur.execute(
        """
        select query, status, last_error, coalesce((result->>'valid')::int, 0) as valid
        from scrape_tasks
        where platform = 'croma' and created_by = 'catalog_overlap'
        order by created_at
        """
    )
    tasks = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """
        select status, consecutive_failures, circuit_open_until
        from platform_health where platform = 'croma'
        """
    )
    health = dict(cur.fetchone() or {})
report = {
    "queries": tasks,
    "health": {
        "status": health.get("status"),
        "failures": health.get("consecutive_failures"),
        "open_until": str(health.get("circuit_open_until")),
        "allows_discovery": platform_allows_task("croma", "discovery"),
    },
    "stopped_on_challenge": False,
}
for task in tasks:
    blob = f"{task.get('last_error') or ''}".lower()
    if "challenge" in blob or "captcha" in blob:
        report["stopped_on_challenge"] = True
path = Path("artifacts/catalog_overlap_v1/croma_probe.json")
path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
print(json.dumps(report, indent=2, default=str))
