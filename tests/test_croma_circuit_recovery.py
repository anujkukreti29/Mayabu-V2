"""Prove Croma circuit opens on challenge failures and recovers on success."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mayabu.db.connection import db_connection
from mayabu.scrapers.circuit_breaker import (
    CircuitOpenError,
    ensure_platform_available,
    get_platform_state,
    record_platform_failure,
    record_platform_success,
)


def test_croma_circuit_opens_then_recovers(monkeypatch) -> None:
    # Lower threshold for the test via settings if available; otherwise drive failures.
    from mayabu.core.config import get_app_settings

    settings = get_app_settings()
    threshold = max(1, int(getattr(settings, "circuit_failure_threshold", 3) or 3))

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into platform_health(platform, status, consecutive_failures, circuit_open_until, updated_at)
                values ('croma', 'healthy', 0, null, now())
                on conflict (platform) do update set
                  status = 'healthy',
                  consecutive_failures = 0,
                  circuit_open_until = null,
                  updated_at = now()
                """
            )

    opened = False
    for i in range(threshold):
        result = record_platform_failure("croma", "captcha", latency_ms=100 + i)
        if result.get("opened"):
            opened = True
    assert opened or get_platform_state("croma").get("status") == "blocked"

    state = get_platform_state("croma")
    assert state.get("circuit_open_until") is not None

    # Force cooldown expired so recovery path can run.
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update platform_health
                set circuit_open_until = now() - interval '1 second',
                    status = 'blocked',
                    updated_at = now()
                where platform = 'croma'
                """
            )

    # Expired open-until should no longer block.
    ensure_platform_available("croma")
    record_platform_success("croma", latency_ms=250)
    recovered = get_platform_state("croma")
    assert recovered.get("status") in {"healthy", "paused"}
    assert recovered.get("circuit_open_until") is None
    assert int(recovered.get("consecutive_failures") or 0) == 0
