"""Platform health policy helpers.

Configured/enabled platforms are distinct from current health.
Blocked or circuit-open platforms must not be hammered.
"""

from __future__ import annotations

from datetime import datetime, timezone

from mayabu.db.connection import db_connection
from mayabu.platforms.registry import get_platform
from mayabu_common import canonical_platform


def _circuit_is_open(circuit_until: object) -> bool:
    """True only while circuit_open_until is still in the future."""
    if circuit_until is None:
        return False
    try:
        tzinfo = getattr(circuit_until, "tzinfo", None)
        now = datetime.now(tzinfo) if tzinfo else datetime.now(timezone.utc)
        return circuit_until >= now  # type: ignore[operator]
    except Exception:
        return False


def get_platform_status(platform: str) -> dict[str, object]:
    platform = canonical_platform(platform)
    info = get_platform(platform)
    configured = bool(info and info.enabled)
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select status, circuit_open_until, consecutive_failures, reason
                from platform_health where platform = %s
                """,
                (platform,),
            )
            row = cur.fetchone()
    if not row:
        return {
            "platform": platform,
            "configured": configured,
            "enabled": configured,
            "status": "healthy",
            "circuit_open": False,
            "allows_work": configured,
        }
    status = str(row["status"] or "healthy")
    circuit_open = _circuit_is_open(row.get("circuit_open_until"))
    sticky_block = status == "blocked" and row.get("circuit_open_until") is None
    allows_refresh = (
        configured
        and status != "paused"
        and not circuit_open
        and not sticky_block
    )
    # Expired auto-circuit leaves status=blocked until a success; refresh may
    # retry, but discovery stays off until the platform is healthy again.
    allows_discovery = allows_refresh and status not in {"degraded", "blocked"}
    allows = allows_refresh
    return {
        "platform": platform,
        "configured": configured,
        "enabled": configured,
        "status": status,
        "circuit_open": circuit_open,
        "circuit_open_until": row.get("circuit_open_until"),
        "consecutive_failures": row.get("consecutive_failures") or 0,
        "reason": row.get("reason"),
        "allows_work": allows,
        "allows_discovery": allows_discovery,
        "allows_refresh": allows_refresh,
    }


def platform_allows_task(platform: str, task_type: str) -> bool:
    state = get_platform_status(platform)
    if not state.get("configured"):
        return False
    kind = str(task_type or "")
    if kind.startswith("refresh") or kind in {"verify_listing"}:
        return bool(state.get("allows_refresh"))
    if kind.startswith("discover"):
        return bool(state.get("allows_discovery"))
    return bool(state.get("allows_work"))


def record_health_observation(platform: str, scrape_status: str, *, reason: str | None = None) -> None:
    """Update platform_health from a scraper health observation without rewriting config."""
    platform = canonical_platform(platform)
    status_map = {
        "healthy": "healthy",
        "degraded": "degraded",
        "partial": "degraded",
        "empty": "degraded",
        "blocked": "blocked",
        "failed": "degraded",
    }
    mapped = status_map.get(scrape_status, "degraded")
    with db_connection() as conn:
        with conn.cursor() as cur:
            if mapped == "blocked":
                cur.execute(
                    """
                    insert into platform_health(platform, status, reason, consecutive_failures, last_failure_at, updated_at)
                    values (%s, 'blocked', %s, 1, now(), now())
                    on conflict (platform) do update set
                      status = 'blocked',
                      reason = excluded.reason,
                      consecutive_failures = platform_health.consecutive_failures + 1,
                      last_failure_at = now(),
                      updated_at = now()
                    """,
                    (platform, reason or "blocked_or_captcha"),
                )
            elif mapped == "healthy":
                cur.execute(
                    """
                    insert into platform_health(platform, status, reason, consecutive_failures, last_success_at, updated_at)
                    values (%s, 'healthy', null, 0, now(), now())
                    on conflict (platform) do update set
                      status = case when platform_health.status = 'paused' then 'paused' else 'healthy' end,
                      reason = null,
                      consecutive_failures = 0,
                      last_success_at = now(),
                      circuit_open_until = null,
                      updated_at = now()
                    """,
                    (platform,),
                )
            else:
                cur.execute(
                    """
                    insert into platform_health(platform, status, reason, consecutive_failures, last_failure_at, updated_at)
                    values (%s, %s, %s, 1, now(), now())
                    on conflict (platform) do update set
                      status = case
                        when platform_health.status = 'paused' then 'paused'
                        when platform_health.status = 'blocked' then 'blocked'
                        else excluded.status
                      end,
                      reason = excluded.reason,
                      consecutive_failures = platform_health.consecutive_failures + 1,
                      last_failure_at = now(),
                      updated_at = now()
                    """,
                    (platform, mapped, reason or scrape_status),
                )
