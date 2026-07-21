"""Persisted per-platform circuit breaker."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection


class CircuitOpenError(RuntimeError):
    pass


def get_platform_state(platform: str) -> dict[str, Any]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from platform_health where platform = %s", (platform,))
            return dict(cur.fetchone() or {})


def ensure_platform_available(platform: str) -> None:
    state = get_platform_state(platform)
    if not state:
        return
    if state.get("status") == "paused":
        raise CircuitOpenError(f"{platform} is manually paused")
    opened_until = state.get("circuit_open_until")
    if opened_until and opened_until > datetime.now(timezone.utc):
        raise CircuitOpenError(f"{platform} circuit is open until {opened_until.isoformat()}")


def record_platform_success(platform: str, latency_ms: int | None = None) -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into platform_health(platform, status, success_count, consecutive_failures,
                                            last_success_at, last_latency_ms, circuit_open_until,
                                            last_error_code, updated_at)
                values (%s,'healthy',1,0,now(),%s,null,null,now())
                on conflict (platform) do update set
                  status = case when platform_health.status = 'paused' then 'paused' else 'healthy' end,
                  success_count = platform_health.success_count + 1,
                  consecutive_failures = 0,
                  last_success_at = now(),
                  last_latency_ms = excluded.last_latency_ms,
                  circuit_open_until = null,
                  last_error_code = null,
                  updated_at = now()
                """,
                (platform, latency_ms),
            )


def record_platform_failure(platform: str, error_code: str, latency_ms: int | None = None) -> dict[str, Any]:
    settings = get_app_settings()
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into platform_health(platform, status, failure_count, consecutive_failures,
                                            last_failure_at, last_latency_ms, last_error_code, updated_at)
                values (%s,'degraded',1,1,now(),%s,%s,now())
                on conflict (platform) do update set
                  failure_count = platform_health.failure_count + 1,
                  consecutive_failures = platform_health.consecutive_failures + 1,
                  last_failure_at = now(),
                  last_latency_ms = excluded.last_latency_ms,
                  last_error_code = excluded.last_error_code,
                  updated_at = now()
                returning consecutive_failures, status
                """,
                (platform, latency_ms, error_code[:120]),
            )
            row = cur.fetchone() or {}
            failures = int(row.get("consecutive_failures") or 0)
            if failures >= settings.circuit_failure_threshold and row.get("status") != "paused":
                cur.execute(
                    """
                    update platform_health
                    set status = 'blocked',
                        circuit_open_until = now() + (%s::int * interval '1 second'),
                        updated_at = now()
                    where platform = %s
                    returning circuit_open_until
                    """,
                    (settings.circuit_cooldown_seconds, platform),
                )
                opened = cur.fetchone() or {}
                return {"opened": True, "consecutive_failures": failures, **opened}
    return {"opened": False, "consecutive_failures": failures}
