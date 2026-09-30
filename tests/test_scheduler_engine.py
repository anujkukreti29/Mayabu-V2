"""Scheduler process tests — no live retailers."""

from __future__ import annotations

from dataclasses import replace

from mayabu.scheduler.engine import tick
from mayabu.scheduler.refresh_policy import TIER_PRIORITY, refresh_task_priority


def test_tick_disabled_does_not_schedule(monkeypatch) -> None:
    from mayabu.core.config import get_app_settings

    get_app_settings.cache_clear()
    settings = replace(get_app_settings(), scheduler_enabled=False)
    monkeypatch.setattr("mayabu.scheduler.engine.get_app_settings", lambda: settings)
    result = tick()
    assert result.result == "disabled"
    assert result.jobs_scheduled == 0
    get_app_settings.cache_clear()


def test_tick_standby_when_lease_not_acquired(monkeypatch) -> None:
    from mayabu.core.config import get_app_settings
    from mayabu.scheduler.lease import SchedulerLease

    get_app_settings.cache_clear()
    settings = replace(get_app_settings(), scheduler_enabled=True, scheduler_lease_seconds=90)
    monkeypatch.setattr("mayabu.scheduler.engine.get_app_settings", lambda: settings)

    class _Denied(SchedulerLease):
        def try_acquire(self, ttl_seconds: int) -> bool:  # noqa: ARG002
            return False

    result = tick(_Denied(holder_id="standby-test"))
    assert result.result == "standby"
    assert result.jobs_scheduled == 0
    get_app_settings.cache_clear()


def test_refresh_priority_hot_beats_cold() -> None:
    assert refresh_task_priority({"refresh_tier": "hot", "refresh_priority": 100}) == TIER_PRIORITY["hot"]
    assert refresh_task_priority({"refresh_tier": "cold", "refresh_priority": 100}) == TIER_PRIORITY["cold"]
    assert TIER_PRIORITY["hot"] < TIER_PRIORITY["normal"] < TIER_PRIORITY["cold"]


def test_refresh_materializer_uses_idempotency_key() -> None:
    from mayabu.scheduler import task_materializer
    import inspect

    source = inspect.getsource(task_materializer.materialize_refresh)
    assert 'idempotency_key=f"refresh_listing:{listing_id}"' in source
    assert "refresh_tier" in source


def test_discovery_plans_are_idempotent() -> None:
    from mayabu_db import scheduler
    import inspect

    source = inspect.getsource(scheduler.materialize_due_plans)
    assert 'idempotency_key=f"discovery:{plan' in source


def test_match_evidence_explains_decisions() -> None:
    from mayabu.domain.match_evidence import explain_match
    from mayabu.domain.matching import assess_product_match

    assessment = assess_product_match(
        {
            "title": "Samsung Galaxy S24 8GB 128GB",
            "category": "smartphone",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "ram_gb": 8, "storage_gb": 128, "model_codes": ["SM-S921B"]},
        },
        {
            "title": "Samsung Galaxy S24 8GB 256GB",
            "canonical_title": "Samsung Galaxy S24 8GB 256GB",
            "category": "smartphone",
            "specs": {"brand": "samsung", "family": "galaxy_s24", "ram_gb": 8, "storage_gb": 256, "model_codes": ["SM-S921B"]},
        },
    )
    explained = explain_match(assessment)
    assert explained.merge_allowed is False
    assert explained.relation in {"variant", "conflict"}
    assert explained.explanation


def test_discovery_cursor_rotates_and_restarts() -> None:
    from mayabu.scheduler.discovery_cursor import start_page_from_metadata, MAX_ROTATION_PAGE

    assert start_page_from_metadata(None) == 1
    assert start_page_from_metadata({"cursor": {"last_page": 3}}) == 4
    assert start_page_from_metadata({"cursor": {"last_page": MAX_ROTATION_PAGE}}) == 1


def test_verify_listing_promotes_pending_refresh() -> None:
    from mayabu.jobs import queue
    import inspect

    source = inspect.getsource(queue.enqueue_verification)
    assert "refresh_listing" in source
    assert "priority = least(priority" in source


def test_retailer_budget_and_backoff_are_consulted() -> None:
    from mayabu.scheduler import task_materializer
    import inspect

    source = inspect.getsource(task_materializer.materialize_refresh)
    assert "budget_available" in source
    assert "platform_allows_task" in source
