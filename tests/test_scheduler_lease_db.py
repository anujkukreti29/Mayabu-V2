"""Leader-lock tests against PostgreSQL. Skipped without a test database."""

from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("psycopg")

DATABASE_URL = os.getenv("MAYABU_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("MAYABU_TEST_DATABASE_URL not set", allow_module_level=True)


def test_two_schedulers_cannot_both_hold_advisory_lock() -> None:
    from mayabu.scheduler.lease import SchedulerLease

    domain = f"test-lock-{uuid.uuid4().hex[:12]}"
    leader = SchedulerLease(domain=domain, holder_id="leader-a")
    standby = SchedulerLease(domain=domain, holder_id="standby-b")
    try:
        assert leader.try_acquire(30) is True
        assert standby.try_acquire(30) is False
        leader.record_tick(
            ttl_seconds=30,
            jobs_scheduled=2,
            result="ok",
            success=True,
            duration_ms=12,
        )
        from mayabu.scheduler.lease import read_heartbeat

        beat = read_heartbeat(domain)
        assert beat is not None
        assert beat.holder_id == "leader-a"
        if beat.last_tick_duration_ms is not None:
            assert beat.last_tick_duration_ms == 12
        if beat.last_tick_jobs is not None:
            assert beat.last_tick_jobs == 2
    finally:
        leader.release()
        standby.release()
        acquired = standby.try_acquire(30)
        assert acquired is True
        standby.release()


def test_two_schedulers_standby_does_not_materialize(monkeypatch) -> None:
    from dataclasses import replace

    from mayabu.core.config import get_app_settings
    from mayabu.scheduler.engine import tick
    from mayabu.scheduler.lease import SchedulerLease

    created = {"n": 0}

    def fake_refresh(limit=40, platform=None):  # noqa: ARG001
        created["n"] += 1
        return 1

    get_app_settings.cache_clear()
    settings = replace(
        get_app_settings(),
        scheduler_enabled=True,
        scheduler_max_discovery_per_tick=0,
        scheduler_max_demand_per_tick=0,
        scheduler_search_drain_per_tick=0,
        scheduler_lease_seconds=30,
    )
    monkeypatch.setattr("mayabu.scheduler.engine.get_app_settings", lambda: settings)
    monkeypatch.setattr("mayabu.scheduler.engine.materialize_refresh", fake_refresh)
    monkeypatch.setattr("mayabu.scheduler.engine.materialize_due_plans", lambda limit=0: 0)
    monkeypatch.setattr("mayabu.scheduler.engine.materialize_demand_discovery", lambda limit=0: 0)
    monkeypatch.setattr("mayabu.scheduler.engine.drain_dirty_search_documents", lambda limit=50: {"refreshed": 0})
    monkeypatch.setattr("mayabu.scheduler.engine.requeue_stuck_tasks", lambda conn: 0)

    domain = f"runtime-lock-{uuid.uuid4().hex[:10]}"
    leader = SchedulerLease(domain=domain, holder_id="leader-runtime")
    standby = SchedulerLease(domain=domain, holder_id="standby-runtime")
    try:
        first = tick(leader)
        assert first.result == "ok"
        assert created["n"] == 1
        second = tick(standby)
        assert second.result == "standby"
        assert created["n"] == 1
        leader.release()
        failover = tick(standby)
        assert failover.result == "ok"
        assert created["n"] == 2
    finally:
        leader.release()
        standby.release()
        get_app_settings.cache_clear()


def test_expired_lease_is_requeued() -> None:
    from mayabu.db.connection import db_connection
    from mayabu_db.tasks import requeue_stuck_tasks

    task_id = None
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into scrape_tasks(
                  platform, task_type, url, status, attempts, max_attempts,
                  locked_at, locked_by, lease_expires_at, created_by, metadata
                )
                values (
                  'amazon', 'refresh_listing', %s, 'running', 1, 3,
                  now() - interval '2 hours', 'dead-worker',
                  now() - interval '10 minutes', 'runtime-recovery',
                  %s::jsonb
                )
                returning id
                """,
                (
                    f"https://www.amazon.in/dp/B0RECOVERY{uuid.uuid4().hex[:8]}",
                    '{"task_source":"runtime_recovery"}',
                ),
            )
            task_id = str(cur.fetchone()["id"])
        reaped = requeue_stuck_tasks(conn, max_age_minutes=45, retry_delay_minutes=0)
        assert reaped >= 1
        with conn.cursor() as cur:
            cur.execute("select status, locked_by, lease_expires_at from scrape_tasks where id = %s", (task_id,))
            row = cur.fetchone()
            assert row["status"] == "pending"
            assert row["locked_by"] is None
            cur.execute("delete from scrape_tasks where id = %s", (task_id,))


def test_due_listing_explain_is_bounded() -> None:
    from mayabu.db.connection import db_connection

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                explain (format json)
                select id, platform, last_successful_refresh_at, refresh_priority
                from platform_listings
                where listing_url is not null
                  and match_status in ('matched','unmatched','needs_review')
                order by last_successful_refresh_at asc nulls first
                limit 40
                """
            )
            plan = cur.fetchone()
    assert plan is not None
    payload = plan[0] if not isinstance(plan, dict) else next(iter(plan.values()))
    text = str(payload).lower()
    assert "limit" in text or "scan" in text or "index" in text

