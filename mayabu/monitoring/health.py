"""Health and readiness collection for Mayabu services."""

from __future__ import annotations

from typing import Any

from mayabu.core.config import get_app_settings
from mayabu.db.connection import db_connection, pool_stats
from mayabu.search.cache import get_cache
from mayabu.search.search_repository import search_source_status


def collect_health() -> dict[str, Any]:
    settings = get_app_settings()
    data: dict[str, Any] = {
        "status": "ok",
        "database": "unknown",
        "redis": "disabled",
        "api_concurrency": {
            "workers": settings.api_workers,
            "threadpool_tokens_per_worker": settings.api_threadpool_tokens,
            "db_pool_max_per_worker": settings.db_pool_max_size,
        },
    }
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 as ok")
                cur.fetchone()
                cur.execute("select count(*) as count from scrape_tasks where status = 'pending'")
                pending = int(cur.fetchone()["count"])
                cur.execute("select count(*) as count from scrape_tasks where status = 'running'")
                running = int(cur.fetchone()["count"])
                cur.execute("select count(*) as count from anomaly_events where status = 'open'")
                anomalies = int(cur.fetchone()["count"])
                cur.execute("select count(*) as count from review_queue where status = 'needs_review'")
                reviews = int(cur.fetchone()["count"])
                cur.execute("select count(*) as count from search_document_dirty")
                dirty = int(cur.fetchone()["count"])
        data.update({
            "database": "ok",
            "pending_tasks": pending,
            "running_tasks": running,
            "open_anomalies": anomalies,
            "review_queue": reviews,
            "dirty_search_documents": dirty,
            "db_pool": pool_stats(),
        })
    except Exception as exc:  # pragma: no cover
        data.update({"status": "degraded", "database": "error", "database_error": str(exc)[:500]})

    try:
        data["search"] = search_source_status()
    except Exception as exc:  # pragma: no cover
        data["search"] = {"mode": "unknown", "error": str(exc)[:300]}

    cache = get_cache()
    if cache.enabled:
        redis_ok = cache.ping()
        data["redis"] = "ok" if redis_ok else "error"
        if not redis_ok and data["status"] == "ok":
            data["status"] = "degraded"
    return data


def readiness() -> dict[str, Any]:
    data = collect_health()
    data["ready"] = data.get("database") == "ok"
    return data


def main() -> None:
    print(collect_health())


if __name__ == "__main__":
    main()
