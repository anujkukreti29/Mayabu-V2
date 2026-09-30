"""Wait out the Flipkart cooldown, then one page-1 search to clear the circuit.

Empty deep pages were counted as outages. This does not clear the circuit by SQL.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from mayabu.scheduler.platform_health_policy import get_platform_status
from mayabu_db.connection import db_connection
from mayabu_db.tasks import create_task


def main() -> None:
    with db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            update scrape_tasks
            set status = 'dead',
                last_error = 'superseded_after_circuit',
                locked_at = null,
                locked_by = null,
                lease_expires_at = null,
                updated_at = now()
            where created_by = 'catalog_depth'
              and platform = 'flipkart'
              and status = 'paused'
            returning query
            """
        )
        print("retired", [r["query"] for r in cur.fetchall()], flush=True)

    status = get_platform_status("flipkart")
    until = status.get("circuit_open_until")
    if until is not None:
        target = until.astimezone(timezone.utc) + timedelta(seconds=20)
        wait = (target - datetime.now(timezone.utc)).total_seconds()
        if wait > 0:
            print(f"waiting {int(wait)}s for flipkart circuit", flush=True)
            time.sleep(wait)

    with db_connection() as conn:
        task_id = create_task(
            conn,
            "flipkart",
            "discovery",
            query="samsung galaxy s24",
            priority=50,
            max_pages=1,
            max_products=24,
            metadata={
                "purpose": "catalog_health_probe",
                "category": "smartphone",
                "start_page": 1,
                "page_cursor": True,
            },
            idempotency_key="flipkart-health-probe-s24",
            created_by="catalog_health_probe",
        )
    print("probe", task_id, flush=True)
    deadline = time.time() + 240
    while time.time() < deadline:
        with db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select status, left(coalesce(last_error,''), 120) err from scrape_tasks where id = %s",
                (task_id,),
            )
            row = dict(cur.fetchone() or {})
        print(row, get_platform_status("flipkart")["status"], flush=True)
        if row.get("status") in {"completed", "dead", "failed"}:
            break
        time.sleep(8)
    print("final", get_platform_status("flipkart"), flush=True)


if __name__ == "__main__":
    main()
