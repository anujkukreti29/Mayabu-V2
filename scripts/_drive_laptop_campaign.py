import sys
import time
from scripts.run_catalog_expansion import materialize, pending_discovery, queue_snapshot
from mayabu_db.connection import db_connection

CATEGORY = sys.argv[1] if len(sys.argv) > 1 else "laptop"

def remaining():
    with db_connection() as c, c.cursor() as cur:
        cur.execute("""
          select count(*)::int n from scheduler_plans
          where coalesce(metadata->>'purpose','')='catalog_expansion_v1'
            and coalesce(metadata->>'category','')=%s
            and coalesce(metadata->>'completion','') not in ('saturated','circuit_blocked','limited_budget_held')
            and last_materialized_at is null
        """, (CATEGORY,))
        return int(cur.fetchone()["n"])

for _ in range(500):
    left = remaining()
    pend = pending_discovery()
    if pend < 6 and left:
        materialize(CATEGORY, limit=min(8, left))
    snap = queue_snapshot()
    print("category", CATEGORY, "remaining_plans", left, "pending_active", pend, "queue", snap, flush=True)
    if left == 0 and pend == 0 and snap.get("running", 0) == 0 and snap.get("pending", 0) == 0:
        print("CATEGORY_QUEUE_DRAINED", CATEGORY, flush=True)
        break
    time.sleep(25)
