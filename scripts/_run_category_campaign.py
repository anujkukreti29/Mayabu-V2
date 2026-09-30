"""Seed, limit Amazon/Croma, and feed one category until drained."""
from __future__ import annotations

import subprocess
import sys
import time

from scripts.run_catalog_expansion import materialize, pending_discovery, queue_snapshot, resume_incomplete, seed_plans
from mayabu_db.connection import db_connection

CATEGORY = sys.argv[1]


def remaining() -> int:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select count(*)::int n from scheduler_plans
            where coalesce(metadata->>'purpose','')='catalog_expansion_v1'
              and coalesce(metadata->>'category','')=%s
              and coalesce(metadata->>'completion','') not in ('saturated','circuit_blocked','limited_budget_held')
              and last_materialized_at is null
            """,
            (CATEGORY,),
        )
        return int(cur.fetchone()["n"])


def main() -> int:
    seeded = seed_plans(CATEGORY, None)
    resumed = resume_incomplete(CATEGORY)
    print("seeded", seeded, "resumed", resumed, flush=True)
    subprocess.check_call(
        [sys.executable, "scripts/_limit_amazon_croma.py", CATEGORY],
    )
    created = materialize(CATEGORY, limit=12)
    print("materialized", created, flush=True)
    for _ in range(800):
        left = remaining()
        pend = pending_discovery()
        if pend < 6 and left:
            materialize(CATEGORY, limit=min(8, left))
        snap = queue_snapshot()
        print(
            "category",
            CATEGORY,
            "remaining_plans",
            left,
            "pending_active",
            pend,
            "queue",
            snap,
            flush=True,
        )
        if left == 0 and pend == 0 and snap.get("running", 0) == 0 and snap.get("pending", 0) == 0:
            print("CATEGORY_QUEUE_DRAINED", CATEGORY, flush=True)
            return 0
        time.sleep(25)
    print("CATEGORY_LOOP_CAP", CATEGORY, flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
