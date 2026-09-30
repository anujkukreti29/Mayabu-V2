from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from mayabu_common import canonical_platform


def create_task(
    conn: Connection,
    platform: str,
    task_type: str,
    query: str | None = None,
    url: str | None = None,
    native_id: str | None = None,
    priority: int = 100,
    max_pages: int | None = None,
    max_products: int | None = None,
    metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    created_by: str = "system",
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into scrape_tasks(platform, task_type, query, url, native_id, priority,
                                     max_pages, max_products, metadata, idempotency_key, created_by)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (idempotency_key)
              where idempotency_key is not null and status in ('pending','running','paused')
            do nothing
            returning id
            """,
            (canonical_platform(platform), task_type, query, url, native_id, priority,
             max_pages, max_products, Jsonb(metadata or {}), idempotency_key, created_by),
        )
        row = cur.fetchone()
        if row:
            return str(row["id"])
        if not idempotency_key:
            raise RuntimeError("Task insert did not return a row")
        cur.execute(
            """
            select id from scrape_tasks
            where idempotency_key = %s and status in ('pending','running','paused')
            order by created_at desc limit 1
            """,
            (idempotency_key,),
        )
        existing = cur.fetchone()
        if not existing:
            raise RuntimeError("Idempotent task insert conflicted but active task was not found")
        return str(existing["id"])


def requeue_stuck_tasks(conn: Connection, max_age_minutes: int = 45, retry_delay_minutes: int = 5) -> int:
    """Reap expired leases without touching healthy running tasks."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update scrape_tasks
            set status = case when attempts >= max_attempts then 'dead' else 'pending' end,
                locked_at = null,
                locked_by = null,
                lease_expires_at = null,
                scheduled_at = case when attempts >= max_attempts then scheduled_at
                                    else now() + make_interval(mins => %s) end,
                last_error = coalesce(last_error, 'worker lease expired'),
                updated_at = now()
            where status = 'running'
              and (
                (lease_expires_at is not null and lease_expires_at < now())
                or (lease_expires_at is null and locked_at < now() - make_interval(mins => %s))
              )
            returning id
            """,
            (retry_delay_minutes, max_age_minutes),
        )
        return int(cur.rowcount or 0)


def cleanup_raw_scrape_items(conn: Connection, retention_days: int = 30) -> int:
    with conn.cursor() as cur:
        cur.execute("delete from raw_scrape_items where scraped_at < now() - make_interval(days => %s)", (retention_days,))
        return int(cur.rowcount or 0)


def claim_next_task(
    conn: Connection,
    worker_id: str,
    lease_minutes: int = 20,
    *,
    created_by: str | None = None,
) -> dict[str, Any] | None:
    """Claim the next pending task with FOR UPDATE SKIP LOCKED.

    Optional ``created_by`` scopes the claim so concurrency tests cannot pick up
    unrelated pending queue work from a shared database. Production workers leave
    it unset and claim from the global queue.
    """
    with conn.cursor() as cur:
        if created_by:
            cur.execute(
                """
                with candidate as (
                  select id from scrape_tasks
                  where status = 'pending' and scheduled_at <= now()
                    and created_by = %s
                  order by priority asc, scheduled_at asc, created_at asc
                  limit 1 for update skip locked
                )
                update scrape_tasks t
                set status = 'running', attempts = attempts + 1,
                    locked_at = now(), locked_by = %s,
                    lease_expires_at = now() + make_interval(mins => %s),
                    updated_at = now()
                from candidate where t.id = candidate.id
                returning t.*
                """,
                (created_by, worker_id, max(1, lease_minutes)),
            )
        else:
            cur.execute(
                """
                with candidate as (
                  select id from scrape_tasks
                  where status = 'pending' and scheduled_at <= now()
                  order by priority asc, scheduled_at asc, created_at asc
                  limit 1 for update skip locked
                )
                update scrape_tasks t
                set status = 'running', attempts = attempts + 1,
                    locked_at = now(), locked_by = %s,
                    lease_expires_at = now() + make_interval(mins => %s),
                    updated_at = now()
                from candidate where t.id = candidate.id
                returning t.*
                """,
                (worker_id, max(1, lease_minutes)),
            )
        return cur.fetchone()


def claim_task_by_id(
    conn: Connection,
    task_id: str,
    worker_id: str,
    lease_minutes: int = 20,
) -> dict[str, Any] | None:
    """Lease one known pending task. Used by bounded smoke, not the production poller."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update scrape_tasks
            set status = 'running', attempts = attempts + 1,
                locked_at = now(), locked_by = %s,
                lease_expires_at = now() + make_interval(mins => %s),
                updated_at = now()
            where id = %s::uuid
              and status = 'pending'
              and scheduled_at <= now()
            returning *
            """,
            (worker_id, max(1, lease_minutes), task_id),
        )
        return cur.fetchone()


def extend_task_lease(conn: Connection, task_id: str, worker_id: str, lease_minutes: int = 20) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            update scrape_tasks
            set lease_expires_at = now() + make_interval(mins => %s), updated_at = now()
            where id = %s and status = 'running' and locked_by = %s
            """,
            (max(1, lease_minutes), task_id, worker_id),
        )
        return cur.rowcount == 1


def start_run(conn: Connection, task: dict[str, Any]) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into scrape_runs(task_id, platform, task_type, query, url, status, metadata)
            values (%s,%s,%s,%s,%s,'running',%s) returning id
            """,
            (task.get("id"), task["platform"], task["task_type"], task.get("query"),
             task.get("url"), Jsonb({"task_metadata": task.get("metadata") or {}})),
        )
        return str(cur.fetchone()["id"])


def finish_run(conn: Connection, run_id: str, status: str, stats: dict[str, Any], error: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update scrape_runs set status = %s, finished_at = now(),
              raw_items = %s, valid_items = %s, listings_created = %s,
              listings_updated = %s, products_created = %s, products_matched = %s,
              observations_added = %s, review_items = %s, anomaly_count = %s,
              error_count = %s, error_summary = %s, metadata = metadata || %s
            where id = %s
            """,
            (status, stats.get("input", 0), stats.get("valid", 0),
             stats.get("listings_created", 0), stats.get("listings_updated", 0),
             stats.get("products_created", 0), stats.get("products_matched", 0),
             stats.get("observations_added", 0), stats.get("review_items", 0),
             stats.get("anomaly_count", 0), len(stats.get("errors") or []) + (1 if error else 0),
             error, Jsonb({"stats": stats}), run_id),
        )


def complete_task(conn: Connection, task_id: str, result: dict[str, Any] | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update scrape_tasks set status = 'completed', locked_at = null, locked_by = null,
              lease_expires_at = null, result = %s, last_error = null, updated_at = now()
            where id = %s
            """,
            (Jsonb(result or {}), task_id),
        )


def fail_task(
    conn: Connection,
    task: dict[str, Any],
    error: str,
    result: dict[str, Any] | None = None,
    *,
    terminal: bool = False,
) -> None:
    attempts = int(task.get("attempts") or 0)
    max_attempts = int(task.get("max_attempts") or 3)
    # Live verification must reach a terminal row so the PDP never spins on
    # requeued pending tasks; listing cooldowns already gate user retries.
    if terminal or str(task.get("task_type") or "") == "verify_listing":
        next_status = "failed"
    else:
        next_status = "dead" if attempts >= max_attempts else "pending"
    backoff_minutes = min(5 * (3 ** max(attempts - 1, 0)), 360)
    with conn.cursor() as cur:
        cur.execute(
            """
            update scrape_tasks set status = %s, locked_at = null, locked_by = null,
              lease_expires_at = null, last_error = %s, result = %s,
              scheduled_at = case when %s = 'pending' then now() + make_interval(mins => %s) else scheduled_at end,
              updated_at = now()
            where id = %s
            """,
            (next_status, error[:2000], Jsonb(result or {}), next_status, backoff_minutes, task["id"]),
        )


def defer_task(conn: Connection, task_id: str, reason: str, delay_seconds: int = 15) -> None:
    """Return a claimed task to the queue without burning a retry attempt."""
    with conn.cursor() as cur:
        cur.execute(
            """
            update scrape_tasks
            set status = 'pending', attempts = greatest(attempts - 1, 0),
                locked_at = null, locked_by = null, lease_expires_at = null,
                scheduled_at = now() + make_interval(secs => %s),
                last_error = left(%s, 2000), updated_at = now()
            where id = %s
            """,
            (max(1, delay_seconds), reason, task_id),
        )


def record_worker_heartbeat(conn: Connection, worker_id: str, tasks_processed_delta: int = 0) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into worker_heartbeats(worker_id, last_heartbeat_at, tasks_processed_total)
            values (%s, now(), %s)
            on conflict (worker_id) do update set
              last_heartbeat_at = excluded.last_heartbeat_at,
              tasks_processed_total = worker_heartbeats.tasks_processed_total + excluded.tasks_processed_total
            """,
            (worker_id, tasks_processed_delta),
        )


def record_diagnostic(
    conn: Connection,
    run_id: str | None,
    task_id: str | None,
    platform: str,
    url: str | None,
    stage: str,
    severity: str,
    message: str,
    screenshot_path: str | None = None,
    html_path: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into scraper_diagnostics(run_id, task_id, platform, url, stage, severity,
                                            message, screenshot_path, html_path, metadata)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (run_id, task_id, canonical_platform(platform), url, stage, severity,
             message, screenshot_path, html_path, Jsonb(metadata or {})),
        )
