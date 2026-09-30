"""Health and readiness collection for Mayabu services.

Liveness: process is up (/api/live).
Readiness: required dependencies available (/api/ready) — PostgreSQL only.
Health: full operational snapshot including optional deps (/api/health).

A blocked retailer or Redis cache outage must not make the API unready.
"""

from __future__ import annotations

from typing import Any

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection, pool_stats
from mayabu.monitoring import instrumentation as m
from mayabu.monitoring.metrics import collect_queue_lag
from mayabu.platforms.coverage import ALL_TRACKED_PLATFORMS, CATALOG_CATEGORIES, get_coverage
from mayabu.search.cache import get_cache
from mayabu.search.search_repository import search_source_status


def _dependency_roles() -> dict[str, Any]:
    settings = get_app_settings()
    return {
        "api": {
            "postgresql": "required",
            "redis_search_cache": "optional_fail_open" if settings.enable_redis_cache else "disabled",
            "redis_rate_limit": (
                "optional_process_local_fallback"
                if settings.enable_redis_rate_limit
                else "disabled"
            ),
            "retailer_sites": "external_not_startup",
        },
        "worker": {
            "postgresql": "required",
            "redis": (
                "required_for_distributed_slots_when_configured"
                if settings.redis_url
                else "optional"
            ),
            "retailer_sites": "external_runtime",
        },
    }


def collect_liveness() -> dict[str, Any]:
    return {"status": "ok", "service": "mayabu-backend", "role": "liveness"}


def collect_health() -> dict[str, Any]:
    settings = get_app_settings()
    data: dict[str, Any] = {
        "status": "ok",
        "database": "unknown",
        "redis": "disabled",
        "dependencies": _dependency_roles(),
        "api_concurrency": {
            "workers": settings.api_workers,
            "threadpool_tokens_per_worker": settings.api_threadpool_tokens,
            "db_pool_max_per_worker": settings.db_pool_max_size,
            "estimated_max_db_connections": settings.api_workers * settings.db_pool_max_size,
        },
    }
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 as ok")
                cur.fetchone()
                cur.execute("select count(*) as count from anomaly_events where status = 'open'")
                anomalies = int(cur.fetchone()["count"])
                cur.execute("select count(*) as count from review_queue where status = 'needs_review'")
                reviews = int(cur.fetchone()["count"])
                cur.execute("select count(*) as count from search_document_dirty")
                dirty = int(cur.fetchone()["count"])
                cur.execute(
                    """
                    select worker_id,
                           last_heartbeat_at,
                           tasks_processed_total,
                           extract(epoch from (now() - last_heartbeat_at)) as age_seconds
                    from worker_heartbeats
                    order by last_heartbeat_at desc
                    limit 20
                    """
                )
                heartbeats = [dict(row) for row in cur.fetchall()]
        queue = collect_queue_lag()
        stats = pool_stats()
        m.refresh_pool_gauges(stats)
        recent_workers = [
            row
            for row in heartbeats
            if row.get("age_seconds") is not None and float(row["age_seconds"]) <= 120
        ]
        data.update({
            "database": "ok",
            "pending_tasks": queue["pending"],
            "running_tasks": queue["running"],
            "oldest_pending_age_seconds": queue["oldest_pending_age_seconds"],
            "dead_tasks_24h": queue["dead_last_24h"],
            "open_anomalies": anomalies,
            "review_queue": reviews,
            "dirty_search_documents": dirty,
            "db_pool": stats,
            "worker_heartbeats": heartbeats,
            "workers_seen_recently": len(recent_workers),
            "worker_status": "ok" if recent_workers else ("stale" if heartbeats else "none"),
        })
        if not recent_workers and data["status"] == "ok":
            data["status"] = "degraded"
            data["degraded_reasons"] = list(data.get("degraded_reasons") or []) + ["worker_heartbeat_stale"]
        try:
            from mayabu.scheduler.lease import heartbeat_status
            from mayabu.scheduler.freshness import catalog_freshness, retailer_health_snapshot
            from mayabu.monitoring.instrumentation import SCHEDULER_HEARTBEAT_AGE

            scheduler = heartbeat_status()
            data["scheduler"] = scheduler
            age = scheduler.get("heartbeat_age_seconds")
            if isinstance(age, (int, float)):
                SCHEDULER_HEARTBEAT_AGE.set(float(age))
            if settings.scheduler_enabled and not scheduler.get("scheduler_alive"):
                data["status"] = "degraded" if data["status"] == "ok" else data["status"]
                data["degraded_reasons"] = list(data.get("degraded_reasons") or []) + [
                    "scheduler_heartbeat_stale"
                ]
            if settings.scheduler_enabled and scheduler.get("last_tick_result") == "error":
                data["status"] = "degraded" if data["status"] == "ok" else data["status"]
                data["degraded_reasons"] = list(data.get("degraded_reasons") or []) + [
                    "scheduler_tick_failing"
                ]
            pending = int(data.get("pending_tasks") or 0)
            oldest_age = data.get("oldest_pending_age_seconds")
            worker_stale = data.get("worker_status") in {"none", "stale"}
            queue_stalled = bool(
                settings.scheduler_enabled
                and pending > 0
                and worker_stale
                and (oldest_age is None or float(oldest_age) >= 120)
            )
            if queue_stalled:
                data["status"] = "degraded" if data["status"] == "ok" else data["status"]
                reasons = list(data.get("degraded_reasons") or [])
                if "worker_queue_stalled" not in reasons:
                    reasons.append("worker_queue_stalled")
                data["degraded_reasons"] = reasons
            verify = _verify_stall_snapshot()
            verify_stalled = bool(
                int(verify.get("pending") or 0) > 0
                and worker_stale
                and float(verify.get("oldest_pending_age_seconds") or 0) >= 120
            )
            if verify_stalled:
                data["status"] = "degraded" if data["status"] == "ok" else data["status"]
                reasons = list(data.get("degraded_reasons") or [])
                if "user_verify_stalled" not in reasons:
                    reasons.append("user_verify_stalled")
                data["degraded_reasons"] = reasons
            data["automation"] = {
                "scheduler_enabled": settings.scheduler_enabled,
                "scheduler_alive": bool(scheduler.get("scheduler_alive")),
                "scheduler_functioning": bool(scheduler.get("scheduler_functioning")),
                "last_tick_result": scheduler.get("last_tick_result"),
                "workers_recent": int(data.get("workers_seen_recently") or 0),
                "worker_status": data.get("worker_status"),
                "pending_tasks": pending,
                "oldest_pending_age_seconds": oldest_age,
                "queue_stalled": queue_stalled,
                "user_verify": verify,
                "user_verify_stalled": verify_stalled,
            }
            data["catalog_freshness"] = catalog_freshness()
            data["retailer_health"] = retailer_health_snapshot()
        except Exception:
            data.setdefault("scheduler", {"scheduler_alive": False})
    except Exception as exc:  # pragma: no cover - exercised in failure tests
        data.update({
            "status": "unhealthy",
            "database": "error",
            "database_error": type(exc).__name__,
        })

    try:
        data["search"] = search_source_status()
    except Exception as exc:  # pragma: no cover
        data["search"] = {"mode": "unknown", "error": type(exc).__name__}

    cache = get_cache()
    if cache.enabled:
        redis_ok = cache.ping()
        data["redis"] = "ok" if redis_ok else "error"
        # Optional cache — degraded, not unhealthy/unready.
        if not redis_ok and data["status"] == "ok":
            data["status"] = "degraded"
            data["degraded_reasons"] = list(data.get("degraded_reasons") or []) + ["redis_cache"]
    else:
        data["redis"] = "disabled"

    # Compact readiness matrix snapshot (not temporary health).
    readiness_counts: dict[str, int] = {}
    for platform in ALL_TRACKED_PLATFORMS:
        for category in CATALOG_CATEGORIES:
            cell = get_coverage(platform, category)
            key = cell.readiness
            readiness_counts[key] = readiness_counts.get(key, 0) + 1
    data["platform_category_readiness"] = readiness_counts

    # Required schema objects — incomplete migrations should be visible.
    data["schema"] = _schema_integrity()
    if data["schema"].get("status") == "incomplete" and data["status"] in {"ok", "degraded"}:
        data["status"] = "degraded"
        data["degraded_reasons"] = list(data.get("degraded_reasons") or []) + [
            "database_migrations_incomplete"
        ]
    return data


def _verify_stall_snapshot() -> dict[str, Any]:
    """Bounded Check Latest Price / verify_listing queue signal (no product IDs)."""
    try:
        with db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select
                  count(*) filter (where status = 'pending') as pending,
                  count(*) filter (where status = 'running') as running,
                  extract(epoch from (
                    now() - min(scheduled_at) filter (
                      where status = 'pending' and scheduled_at <= now()
                    )
                  )) as oldest_pending_age_seconds
                from scrape_tasks
                where task_type = 'verify_listing'
                """
            )
            row = cur.fetchone() or {}
            cur.execute(
                """
                select
                  count(*) filter (where status in ('failed','blocked','dead')) as terminal_fail,
                  count(*) filter (where status = 'partial') as partial,
                  count(*) as total,
                  percentile_cont(0.5) within group (order by duration_ms)
                    filter (where duration_ms is not null) as p50_ms,
                  percentile_cont(0.95) within group (order by duration_ms)
                    filter (where duration_ms is not null) as p95_ms
                from live_verification_events
                where created_at >= now() - interval '24 hours'
                """
            )
            ev = cur.fetchone() or {}
        total = int(ev.get("total") or 0)
        terminal = int(ev.get("terminal_fail") or 0)
        partial = int(ev.get("partial") or 0)
        age = row.get("oldest_pending_age_seconds")
        return {
            "pending": int(row.get("pending") or 0),
            "running": int(row.get("running") or 0),
            "oldest_pending_age_seconds": (
                round(float(age), 1) if age is not None else None
            ),
            "last_24h_terminal_fail_pct": (
                round(100.0 * terminal / total, 1) if total else 0.0
            ),
            "last_24h_partial_pct": (
                round(100.0 * partial / total, 1) if total else 0.0
            ),
            "last_24h_p50_ms": ev.get("p50_ms"),
            "last_24h_p95_ms": ev.get("p95_ms"),
        }
    except Exception:
        return {
            "pending": 0,
            "running": 0,
            "oldest_pending_age_seconds": None,
            "error": "verify_snapshot_unavailable",
        }


REQUIRED_RELATIONS = (
    "product_clusters",
    "platform_listings",
    "price_observations",
    "product_search_documents",
    "scrape_tasks",
    "user_wishlist",
    "watch_events",
    "daily_product_prices",
    "product_images",
    "scheduler_heartbeats",
    "worker_heartbeats",
)


def _schema_integrity() -> dict[str, Any]:
    missing: list[str] = []
    present: list[str] = []
    try:
        with db_connection() as conn, conn.cursor() as cur:
            for name in REQUIRED_RELATIONS:
                cur.execute(
                    """
                    select exists(
                      select 1 from information_schema.tables
                      where table_schema = 'public' and table_name = %s
                    ) as ok
                    """,
                    (name,),
                )
                row = cur.fetchone() or {}
                if row.get("ok"):
                    present.append(name)
                else:
                    missing.append(name)
            version = None
            try:
                cur.execute(
                    """
                    select version from schema_migrations
                    order by applied_at desc nulls last, version desc
                    limit 1
                    """
                )
                vrow = cur.fetchone()
                if vrow:
                    version = vrow.get("version")
            except Exception:
                conn.rollback()
                version = None
        return {
            "status": "ok" if not missing else "incomplete",
            "required": list(REQUIRED_RELATIONS),
            "present": present,
            "missing": missing,
            "latest_migration": version,
            "message": (
                None
                if not missing
                else "database migrations incomplete: missing " + ", ".join(missing)
            ),
        }
    except Exception as exc:
        return {
            "status": "error",
            "required": list(REQUIRED_RELATIONS),
            "present": [],
            "missing": list(REQUIRED_RELATIONS),
            "error": type(exc).__name__,
            "message": "database migrations incomplete",
        }


def readiness() -> dict[str, Any]:
    """Ready iff PostgreSQL is reachable and required migrations/schema are present.

    Redis/retailers do not block readiness. Incomplete migrations must fail ready.
    """
    data = collect_health()
    schema = data.get("schema") if isinstance(data.get("schema"), dict) else {}
    schema_ok = schema.get("status") == "ok"
    data["ready"] = data.get("database") == "ok" and schema_ok
    data["role"] = "readiness"
    if data.get("database") == "ok" and not schema_ok:
        data["status"] = "not_ready"
        data["not_ready_reason"] = schema.get("message") or "database_migrations_incomplete"
    return data


def main() -> None:
    print(collect_health())


if __name__ == "__main__":
    main()
