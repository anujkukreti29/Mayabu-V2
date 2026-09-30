"""Bounded price-engine smoke.

Default: refuse.
--local: fake-adapter scheduler→worker chain (test database only).
--live --confirm MAYABU_LIVE_SMOKE=1: tiny real-retailer proof.

Never mass-crawls. Never enables the full catalog scheduler.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

LIVE_CONFIRM = "MAYABU_LIVE_SMOKE=1"


def _require_test_database() -> str:
    url = os.getenv("MAYABU_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("Refusing: set MAYABU_TEST_DATABASE_URL (or DATABASE_URL) for --local.")
    name = urlparse(url).path.lstrip("/").lower()
    if "test" not in name and not os.getenv("MAYABU_TEST_DATABASE_URL"):
        raise SystemExit("Refusing --local against a non-test DATABASE_URL.")
    os.environ["DATABASE_URL"] = url
    return url


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=str))


def run_local() -> int:
    import subprocess
    import sys

    _require_test_database()
    return subprocess.call(
        [sys.executable, "-m", "pytest", "tests/test_automation_runtime_e2e.py", "-q"],
    )


def run_live(limit: int, discovery: bool) -> int:
    from mayabu.core.config import get_app_settings
    import time as _time

    from mayabu.db.connection import db_connection
    from mayabu.jobs.worker import run_once_async
    from mayabu.scheduler.engine import tick
    from mayabu.scheduler.lease import SchedulerLease
    from mayabu.scheduler.runtime_proof import (
        find_scheduler_refresh_task,
        json_safe,
        select_live_discovery_plan,
        select_live_refresh_listings,
        snapshot_listing,
        snapshot_task,
    )
    from mayabu.scheduler.task_materializer import materialize_refresh

    settings = get_app_settings()
    if settings.scheduler_enabled:
        print("NOTE: MAYABU_SCHEDULER_ENABLED is already true in this process.")
    get_app_settings.cache_clear()
    bounded = replace(
        get_app_settings(),
        scheduler_enabled=True,
        scheduler_max_refresh_per_tick=max(1, min(limit, 4)),
        scheduler_max_discovery_per_tick=1 if discovery else 0,
        scheduler_max_demand_per_tick=0,
        scheduler_search_drain_per_tick=20,
        scraper_max_pages=1,
        scraper_max_products=8,
    )
    import mayabu.scheduler.engine as engine
    import mayabu.scheduler.task_materializer as materializer

    engine.get_app_settings = lambda: bounded  # type: ignore[method-assign]
    materializer.get_app_settings = lambda: bounded  # type: ignore[attr-defined]
    import mayabu.jobs.worker as worker_mod

    worker_mod.get_app_settings = lambda: bounded  # type: ignore[method-assign]

    listings = select_live_refresh_listings(limit=limit)
    if not listings:
        _print({
            "ok": False,
            "error": "no_due_production_listings",
            "detail": "No matched production-enabled listings were available.",
        })
        return 1

    before = []
    listing_ids = []
    for row in listings:
        listing_uuid = str(row["id"])
        listing_ids.append(listing_uuid)
        before.append(snapshot_listing(listing_uuid))

    listing_set = set(listing_ids)
    discovery_plan = select_live_discovery_plan() if discovery else None
    cursor_before = None
    if discovery_plan:
        cursor_before = (discovery_plan.get("metadata") or {}).get("cursor")
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update scheduler_plans
                    set last_materialized_at = now()
                        - make_interval(mins => greatest(cadence_minutes, 1))
                        - interval '1 minute'
                    where id = %s
                    """,
                    (discovery_plan["id"],),
                )

    if discovery_plan:
        from mayabu.scheduler.discovery_cursor import start_page_from_metadata, supports_page_cursor
        from mayabu_db.tasks import create_task

        def _one_discovery_plan(limit: int | None = None) -> int:  # noqa: ARG001
            with db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("select * from scheduler_plans where id = %s", (discovery_plan["id"],))
                    plan = cur.fetchone()
                if not plan:
                    return 0
                metadata = plan.get("metadata") or {}
                start_page = (
                    start_page_from_metadata(metadata)
                    if supports_page_cursor(plan["platform"])
                    else 1
                )
                create_task(
                    conn,
                    plan["platform"],
                    "discovery",
                    query=plan.get("query"),
                    priority=plan.get("priority") or 100,
                    max_pages=1,
                    max_products=8,
                    metadata={
                        "scheduler_plan_id": str(plan["id"]),
                        "scheduler_plan_name": plan.get("name"),
                        "category": metadata.get("category") if isinstance(metadata, dict) else None,
                        "source": "scheduler_plan",
                        "task_source": "scheduler_discovery",
                        "start_page": start_page,
                        "page_cursor": supports_page_cursor(plan["platform"]),
                    },
                    idempotency_key=f"discovery:{plan['id']}",
                    created_by="scheduler",
                )
                with conn.cursor() as cur:
                    cur.execute(
                        "update scheduler_plans set last_materialized_at = now() where id = %s",
                        (plan["id"],),
                    )
            return 1

        engine.materialize_due_plans = _one_discovery_plan  # type: ignore[method-assign]

    def _only_sample(limit: int = 100, platform: str | None = None):  # noqa: ARG001
        return [row for row in listings if platform is None or row.get("platform") == platform][:limit]

    import mayabu.scheduler.refresh_policy as refresh_policy

    refresh_policy.due_refresh_candidates = _only_sample  # type: ignore[method-assign]
    materializer.due_refresh_candidates = _only_sample  # type: ignore[attr-defined]

    lease = SchedulerLease(holder_id="live-smoke")
    tick_result = tick(lease)
    created_tasks = []
    after = []
    timings = []
    try:
        for listing_uuid, before_row in zip(listing_ids, before):
            task_row = find_scheduler_refresh_task(listing_uuid)
            if not task_row:
                after.append({
                    "listing_id": listing_uuid,
                    "error": "scheduler_did_not_create_task",
                })
                continue
            task_id = str(task_row["id"])
            created_tasks.append(snapshot_task(task_id))
            started = _time.perf_counter()
            processed = asyncio.run(run_once_async(f"live-smoke-{task_id[:8]}", task_id=task_id))
            elapsed = _time.perf_counter() - started
            after.append({
                "listing": snapshot_listing(listing_uuid),
                "task": snapshot_task(task_id),
                "worker_claimed": processed,
            })
            timings.append({
                "listing_id": listing_uuid,
                "elapsed_seconds": round(elapsed, 3),
                "task_source": (task_row.get("metadata") or {}).get("task_source"),
                "created_by": task_row.get("created_by"),
            })
    finally:
        lease.release()
        get_app_settings.cache_clear()

    discovery_report = None
    if discovery:
        plan = discovery_plan
        if not plan:
            discovery_report = {"ok": False, "error": "no_enabled_production_discovery_plan"}
        else:
            discovery_task = None
            with db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select id, status, metadata, created_by, attempts
                        from scrape_tasks
                        where task_type = 'discovery'
                          and created_by = 'scheduler'
                          and metadata->>'scheduler_plan_id' = %s
                        order by created_at desc
                        limit 1
                        """,
                        (str(plan["id"]),),
                    )
                    discovery_task = cur.fetchone()
            worker_claimed = False
            elapsed = None
            if discovery_task:
                started = _time.perf_counter()
                worker_claimed = asyncio.run(
                    run_once_async(
                        f"live-smoke-disc-{str(discovery_task['id'])[:8]}",
                        task_id=str(discovery_task["id"]),
                    )
                )
                elapsed = round(_time.perf_counter() - started, 3)
            cursor_after = None
            with db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "select metadata from scheduler_plans where id = %s",
                        (plan["id"],),
                    )
                    row = cur.fetchone()
                    cursor_after = ((row or {}).get("metadata") or {}).get("cursor")
                    if discovery_task:
                        cur.execute(
                            "select status, last_error, result from scrape_tasks where id = %s",
                            (discovery_task["id"],),
                        )
                        discovery_task = dict(cur.fetchone() or {})
            discovery_report = {
                "ok": bool(worker_claimed),
                "plan_id": plan["id"],
                "platform": plan.get("platform"),
                "query": plan.get("query"),
                "cursor_before": cursor_before,
                "cursor_after": cursor_after,
                "task": json_safe(dict(discovery_task) if discovery_task else None),
                "worker_claimed": worker_claimed,
                "elapsed_seconds": elapsed,
                "tick_discovery_created": tick_result.discovery_created,
            }

    ok = bool(created_tasks) and all(
        item.get("worker_claimed") for item in after if "worker_claimed" in item
    )
    _print({
        "ok": ok,
        "mode": "live",
        "tick": {
            "result": tick_result.result,
            "refresh_created": tick_result.refresh_created,
            "discovery_created": tick_result.discovery_created,
        },
        "before": before,
        "tasks": created_tasks,
        "after": after,
        "timings": timings,
        "discovery": discovery_report,
        "materialize_refresh_used": materialize_refresh.__name__,
        "sample_listing_set": list(listing_set),
    })
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bounded Mayabu price-engine smoke. Refuses unless --local or --live."
    )
    parser.add_argument("--live", action="store_true", help="Hit real retailer pages for 2-4 due listings.")
    parser.add_argument("--local", action="store_true", help="Fake-adapter proof against a test database.")
    parser.add_argument("--confirm", default="", help=f"Must equal {LIVE_CONFIRM} with --live.")
    parser.add_argument("--limit", type=int, default=2, help="Max live listings (cap 4).")
    parser.add_argument("--discovery", action="store_true", help="Also attempt one bounded discovery plan.")
    args = parser.parse_args()
    if args.local and args.live:
        print("Refusing: choose either --local or --live.")
        return 2
    if args.local:
        return run_local()
    if not args.live:
        print("Refusing: pass --local, or --live --confirm MAYABU_LIVE_SMOKE=1.")
        print("This is intentionally excluded from CI and does not enable the catalog scheduler.")
        return 2
    if args.confirm != LIVE_CONFIRM:
        print(f"Refusing live traffic: pass --confirm {LIVE_CONFIRM}")
        return 2
    return run_live(limit=args.limit, discovery=args.discovery)


if __name__ == "__main__":
    raise SystemExit(main())
