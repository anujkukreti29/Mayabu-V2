"""Observability unit tests — names, labels, health semantics, singleflight."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from mayabu.monitoring.health import collect_liveness, readiness
from mayabu.monitoring.instrumentation import route_template, status_class
from mayabu.monitoring.registry import get_registry
from mayabu.monitoring.singleflight import SingleFlight


def test_route_template_collapses_ids() -> None:
    assert ":id" in route_template("/api/products/f79ffc18-a49c-4d0a-b1bd-cd224968f38c")
    assert route_template("/api/search") == "/api/search"


def test_status_class_buckets() -> None:
    assert status_class(200) == "2xx"
    assert status_class(429) == "4xx"
    assert status_class(503) == "5xx"


def test_metrics_render_contains_http_counter() -> None:
    reg = get_registry()
    reg.reset()
    from mayabu.monitoring import instrumentation as m

    m.HTTP_REQUESTS.inc(route="/api/search", method="GET", status_class="2xx")
    m.SEARCH_CACHE.inc(event="hit")
    body = reg.render_prometheus()
    assert "mayabu_http_requests_total" in body
    assert 'route="/api/search"' in body
    assert "mayabu_search_cache_events_total" in body


def test_liveness_never_requires_db() -> None:
    data = collect_liveness()
    assert data["status"] == "ok"
    assert data["role"] == "liveness"


def test_readiness_requires_database_only(monkeypatch) -> None:
    # When DB is ok and schema complete, ready is true even if redis is broken.
    from mayabu.monitoring import health as health_mod

    monkeypatch.setattr(
        health_mod,
        "collect_health",
        lambda: {
            "status": "degraded",
            "database": "ok",
            "redis": "error",
            "degraded_reasons": ["redis_cache"],
            "schema": {"status": "ok", "missing": []},
        },
    )
    data = readiness()
    assert data["ready"] is True


def test_readiness_fails_when_migrations_incomplete(monkeypatch) -> None:
    from mayabu.monitoring import health as health_mod

    monkeypatch.setattr(
        health_mod,
        "collect_health",
        lambda: {
            "status": "degraded",
            "database": "ok",
            "redis": "ok",
            "schema": {
                "status": "incomplete",
                "missing": ["watch_events"],
                "message": "database migrations incomplete: missing watch_events",
            },
        },
    )
    data = readiness()
    assert data["ready"] is False
    assert data["status"] == "not_ready"
    assert "migrations incomplete" in (data.get("not_ready_reason") or "").lower()


def test_singleflight_coalesces_concurrent_producers() -> None:
    flight = SingleFlight(recent_ttl_seconds=2.0)
    calls = {"n": 0}
    lock = threading.Lock()
    barrier = threading.Barrier(20)

    def producer() -> str:
        with lock:
            calls["n"] += 1
        return "ok"

    def worker(_: int) -> str:
        barrier.wait(timeout=5)
        return flight.do("same-key", producer)

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(worker, range(20)))
    assert all(r == "ok" for r in results)
    assert calls["n"] == 1
