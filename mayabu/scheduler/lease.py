"""Database-backed scheduler leader lease.

Session advisory locks are unsafe on pooled connections (the lock is released
when the connection is returned). The scheduler therefore:

1. Holds ``pg_try_advisory_lock`` on a dedicated, non-pooled connection.
2. Mirrors leadership into ``scheduler_heartbeats`` for health/observability.

Correctness does not depend on Redis. Leader loss recovers when the lock
session disconnects or the heartbeat lease expires.
"""

from __future__ import annotations

import logging
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mayabu.db.connection import db_connection, open_session_connection

logger = logging.getLogger(__name__)

AUTOMATION_DOMAIN = "automation"
LOCK_NAMESPACE = 942001


def default_holder_id() -> str:
    host = socket.gethostname().split(".")[0][:40]
    return f"scheduler-{host}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True, slots=True)
class SchedulerHeartbeat:
    domain: str
    holder_id: str
    leased_until: datetime | None
    heartbeat_at: datetime | None
    last_successful_tick_at: datetime | None
    jobs_scheduled_total: int
    last_error: str | None
    last_tick_result: str | None
    last_tick_duration_ms: int | None
    last_tick_jobs: int | None
    age_seconds: float | None
    alive: bool


class SchedulerLease:
    def __init__(self, domain: str = AUTOMATION_DOMAIN, holder_id: str | None = None) -> None:
        self.domain = domain
        self.holder_id = holder_id or default_holder_id()
        self._lock_conn = None
        self._holds_lock = False

    def _ensure_lock_conn(self):
        conn = self._lock_conn
        if conn is not None and not getattr(conn, "closed", False):
            return conn
        self._lock_conn = open_session_connection()
        self._holds_lock = False
        return self._lock_conn

    def try_acquire(self, ttl_seconds: int) -> bool:
        ttl = max(15, int(ttl_seconds))
        try:
            conn = self._ensure_lock_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "select pg_try_advisory_lock(%s, hashtext(%s)) as locked",
                    (LOCK_NAMESPACE, self.domain),
                )
                row = cur.fetchone()
                locked = bool(row and row["locked"])
            if not locked:
                self._holds_lock = False
                return False
            self._holds_lock = True
        except Exception:
            logger.exception("scheduler_advisory_lock_failed")
            self._holds_lock = False
            return False

        try:
            with db_connection() as pooled:
                with pooled.cursor() as cur:
                    cur.execute(
                        """
                        insert into scheduler_heartbeats(
                          domain, holder_id, leased_until, heartbeat_at, updated_at
                        )
                        values (%s, %s, now() + make_interval(secs => %s), now(), now())
                        on conflict (domain) do update
                          set holder_id = excluded.holder_id,
                              leased_until = excluded.leased_until,
                              heartbeat_at = excluded.heartbeat_at,
                              updated_at = now()
                        returning holder_id
                        """,
                        (self.domain, self.holder_id, ttl),
                    )
                    row = cur.fetchone()
                    if row and row["holder_id"] == self.holder_id:
                        return True
        except Exception:
            logger.exception("scheduler_heartbeat_upsert_failed")
            # Advisory lock is still the leadership source of truth.
            return True
        return True

    def record_tick(
        self,
        *,
        ttl_seconds: int,
        jobs_scheduled: int,
        result: str,
        error: str | None = None,
        success: bool = False,
        duration_ms: int | None = None,
    ) -> None:
        ttl = max(15, int(ttl_seconds))
        jobs = max(0, int(jobs_scheduled))
        duration = None if duration_ms is None else max(0, int(duration_ms))
        with db_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        update scheduler_heartbeats
                        set heartbeat_at = now(),
                            leased_until = now() + make_interval(secs => %s),
                            jobs_scheduled_total = jobs_scheduled_total + %s,
                            last_tick_result = %s,
                            last_error = %s,
                            last_tick_duration_ms = %s,
                            last_tick_jobs = %s,
                            last_successful_tick_at = case
                              when %s then now() else last_successful_tick_at end,
                            updated_at = now()
                        where domain = %s and holder_id = %s
                        """,
                        (
                            ttl,
                            jobs,
                            result[:80],
                            (error or "")[:2000] or None,
                            duration,
                            jobs,
                            success,
                            self.domain,
                            self.holder_id,
                        ),
                    )
                except Exception:
                    conn.rollback()
                    cur.execute(
                        """
                        update scheduler_heartbeats
                        set heartbeat_at = now(),
                            leased_until = now() + make_interval(secs => %s),
                            jobs_scheduled_total = jobs_scheduled_total + %s,
                            last_tick_result = %s,
                            last_error = %s,
                            last_successful_tick_at = case
                              when %s then now() else last_successful_tick_at end,
                            updated_at = now()
                        where domain = %s and holder_id = %s
                        """,
                        (
                            ttl,
                            jobs,
                            result[:80],
                            (error or "")[:2000] or None,
                            success,
                            self.domain,
                            self.holder_id,
                        ),
                    )

    def release(self) -> None:
        conn = self._lock_conn
        self._lock_conn = None
        held = self._holds_lock
        self._holds_lock = False
        if conn is None:
            return
        try:
            if held and not getattr(conn, "closed", False):
                with conn.cursor() as cur:
                    cur.execute(
                        "select pg_advisory_unlock(%s, hashtext(%s))",
                        (LOCK_NAMESPACE, self.domain),
                    )
            if not getattr(conn, "closed", False):
                conn.close()
        except Exception:
            logger.debug("scheduler_lock_release_failed", extra={"holder_id": self.holder_id})


def read_heartbeat(domain: str = AUTOMATION_DOMAIN) -> SchedulerHeartbeat | None:
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        select domain, holder_id, leased_until, heartbeat_at,
                               last_successful_tick_at, jobs_scheduled_total,
                               last_error, last_tick_result,
                               last_tick_duration_ms, last_tick_jobs,
                               extract(epoch from (now() - heartbeat_at)) as age_seconds
                        from scheduler_heartbeats
                        where domain = %s
                        """,
                        (domain,),
                    )
                except Exception:
                    conn.rollback()
                    cur.execute(
                        """
                        select domain, holder_id, leased_until, heartbeat_at,
                               last_successful_tick_at, jobs_scheduled_total,
                               last_error, last_tick_result,
                               extract(epoch from (now() - heartbeat_at)) as age_seconds
                        from scheduler_heartbeats
                        where domain = %s
                        """,
                        (domain,),
                    )
                row = cur.fetchone()
    except Exception as exc:  # pragma: no cover - missing table before migrate
        logger.debug("scheduler_heartbeat_unavailable", extra={"error": str(exc)[:200]})
        return None
    if not row:
        return None
    age = float(row["age_seconds"]) if row.get("age_seconds") is not None else None
    leased_until = row.get("leased_until")
    lease_active = False
    if leased_until is not None:
        try:
            now = datetime.now(tz=leased_until.tzinfo) if leased_until.tzinfo else datetime.now()
            lease_active = leased_until >= now
        except Exception:
            lease_active = age is not None and age <= 180
    alive = bool(age is not None and age <= 180 and lease_active)
    duration = row.get("last_tick_duration_ms")
    jobs = row.get("last_tick_jobs")
    return SchedulerHeartbeat(
        domain=str(row["domain"]),
        holder_id=str(row["holder_id"]),
        leased_until=row.get("leased_until"),
        heartbeat_at=row.get("heartbeat_at"),
        last_successful_tick_at=row.get("last_successful_tick_at"),
        jobs_scheduled_total=int(row.get("jobs_scheduled_total") or 0),
        last_error=row.get("last_error"),
        last_tick_result=row.get("last_tick_result"),
        last_tick_duration_ms=None if duration is None else int(duration),
        last_tick_jobs=None if jobs is None else int(jobs),
        age_seconds=age,
        alive=alive,
    )


def scheduler_is_functioning(beat: SchedulerHeartbeat | None) -> bool:
    """Alive is not enough: a looping failed tick is not functioning automation."""
    if beat is None or not beat.alive:
        return False
    return beat.last_tick_result != "error"


def heartbeat_status() -> dict[str, Any]:
    beat = read_heartbeat()
    if not beat:
        return {
            "scheduler_alive": False,
            "scheduler_functioning": False,
            "last_scheduler_tick": None,
            "last_successful_tick": None,
            "jobs_scheduled": 0,
            "scheduler_errors": None,
            "holder_id": None,
            "heartbeat_age_seconds": None,
            "last_tick_duration_ms": None,
            "last_tick_jobs": None,
            "last_tick_result": None,
        }
    return {
        "scheduler_alive": beat.alive,
        "scheduler_functioning": scheduler_is_functioning(beat),
        "last_scheduler_tick": beat.heartbeat_at.isoformat() if beat.heartbeat_at else None,
        "last_successful_tick": (
            beat.last_successful_tick_at.isoformat() if beat.last_successful_tick_at else None
        ),
        "jobs_scheduled": beat.jobs_scheduled_total,
        "scheduler_errors": beat.last_error,
        "holder_id": beat.holder_id,
        "heartbeat_age_seconds": beat.age_seconds,
        "last_tick_result": beat.last_tick_result,
        "last_tick_duration_ms": beat.last_tick_duration_ms,
        "last_tick_jobs": beat.last_tick_jobs,
    }
