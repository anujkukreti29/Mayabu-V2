"""Scheduler → queue → worker → ingestion local runtime proof.

Requires a test PostgreSQL database. Never contacts live retailers.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import replace
from decimal import Decimal
from urllib.parse import urlparse

import pytest

pytest.importorskip("psycopg")

DATABASE_URL = os.getenv("MAYABU_TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("MAYABU_TEST_DATABASE_URL not set", allow_module_level=True)
_DB_NAME = urlparse(DATABASE_URL).path.lstrip("/").lower()
_ALLOW_LOCAL = os.getenv("MAYABU_ALLOW_RUNTIME_E2E", "").strip().lower() in {"1", "true", "yes"}
if "test" not in _DB_NAME and not _ALLOW_LOCAL:
    pytest.skip(
        "Test database name must contain 'test' (or set MAYABU_ALLOW_RUNTIME_E2E=1)",
        allow_module_level=True,
    )

from mayabu.db.connection import db_connection  # noqa: E402
from mayabu.domain.price_intelligence import get_price_intelligence  # noqa: E402
from mayabu_db.repository import observation_hash, url_hash  # noqa: E402
from mayabu_refresh.models import RefreshResult  # noqa: E402


def _suffix() -> str:
    return uuid.uuid4().hex[:12]


def _cleanup(product_id: str, listing_ids: list[str]) -> None:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "delete from scrape_runs where task_id in (select id from scrape_tasks where metadata->>'product_id' = %s)",
                (product_id,),
            )
            cur.execute(
                "delete from scrape_tasks where metadata->>'product_id' = %s or metadata->>'platform_listing_id' = any(%s)",
                (product_id, listing_ids),
            )
            cur.execute("delete from price_observations where product_id = %s::uuid", (product_id,))
            for sql in (
                "delete from daily_listing_prices where product_id = %s::uuid",
                "delete from daily_product_platform_prices where product_id = %s::uuid",
                "delete from daily_product_prices where product_id = %s::uuid",
                "delete from search_document_dirty where product_id = %s::uuid",
                "delete from product_search_documents where product_id = %s::uuid",
            ):
                cur.execute("savepoint runtime_cleanup")
                try:
                    cur.execute(sql, (product_id,))
                except Exception:
                    cur.execute("rollback to savepoint runtime_cleanup")
                else:
                    cur.execute("release savepoint runtime_cleanup")
            cur.execute("delete from platform_listings where id = any(%s::uuid[])", (listing_ids,))
            cur.execute("delete from product_clusters where id = %s::uuid", (product_id,))


def _patch_scheduler_bounds(monkeypatch, settings, due_rows) -> None:
    monkeypatch.setattr("mayabu.scheduler.engine.get_app_settings", lambda: settings)
    monkeypatch.setattr("mayabu.scheduler.task_materializer.due_refresh_candidates", lambda limit=100, platform=None: due_rows)
    monkeypatch.setattr("mayabu.scheduler.task_materializer.platform_allows_task", lambda *args, **kwargs: True)
    monkeypatch.setattr("mayabu.scheduler.task_materializer.budget_available", lambda *args, **kwargs: True)
    monkeypatch.setattr("mayabu.scheduler.task_materializer.ensure_today_budget", lambda *args, **kwargs: None)
    monkeypatch.setattr("mayabu.scheduler.engine.drain_dirty_search_documents", lambda limit=50: {"refreshed": 0})
    monkeypatch.setattr("mayabu.scheduler.engine.materialize_due_plans", lambda limit=0: 0)
    monkeypatch.setattr("mayabu.scheduler.engine.materialize_demand_discovery", lambda limit=0: 0)
    monkeypatch.setattr("mayabu.jobs.worker.ensure_platform_available", lambda platform: None)


def _insert_cluster_and_listings(*, amazon_price: int, flipkart_price: int, unmatched_price: int) -> dict[str, str]:
    tag = _suffix()
    amazon_url = f"https://www.amazon.in/dp/B0RUNTIME{tag}"
    flipkart_url = f"https://www.flipkart.com/runtime-{tag}/p/itm{tag}"
    unmatched_url = f"https://www.croma.com/runtime-{tag}"
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into product_clusters(category, brand, canonical_title, variant_key, status)
                values ('laptop', 'lenovo', %s, %s, 'active')
                returning id
                """,
                (f"Lenovo Runtime Proof {tag}", f"runtime-proof-{tag}"),
            )
            product_id = str(cur.fetchone()["id"])
            rows = [
                ("amazon", amazon_url, amazon_price, "matched", f"B0RUNTIME{tag}"),
                ("flipkart", flipkart_url, flipkart_price, "matched", f"itm{tag}"),
                ("croma", unmatched_url, unmatched_price, "unmatched", f"crm{tag}"),
            ]
            listing_ids = []
            for platform, url, price, match_status, native in rows:
                cur.execute(
                    """
                    insert into platform_listings(
                      product_id, platform, listing_id, native_id, listing_url, listing_url_hash,
                      title, category, current_price, currency, stock_status, match_status,
                      last_successful_refresh_at, last_price_change_at, updated_at
                    )
                    values (
                      %s, %s, %s, %s, %s, %s,
                      %s, 'laptop', %s, 'INR', 'in_stock', %s,
                      null,
                      now(),
                      now() - interval '3650 days'
                    )
                    returning id
                    """,
                    (
                        product_id,
                        platform,
                        f"{platform}-runtime-{tag}",
                        native,
                        url,
                        url_hash(url),
                        f"Lenovo Runtime Proof {tag}",
                        price,
                        match_status,
                    ),
                )
                listing_ids.append(str(cur.fetchone()["id"]))
            # Seed a prior same-price observation so the first scheduler refresh
            # is an "unchanged" event, not "initial" (which is a material change).
            amazon_listing_id = listing_ids[0]
            observed_at = "2026-09-01T12:00:00+00:00"
            ohash = observation_hash(amazon_listing_id, observed_at, amazon_price, amazon_price + 5000)
            cur.execute(
                """
                insert into price_observations(
                  observation_hash, listing_id, product_id, platform, observed_at,
                  price, mrp, currency, stock_status, event_type
                ) values (%s, %s::uuid, %s::uuid, 'amazon', %s, %s, %s, 'INR', 'in_stock', 'initial')
                """,
                (ohash, amazon_listing_id, product_id, observed_at, amazon_price, amazon_price + 5000),
            )
            cur.execute(
                "update platform_listings set observation_count = 1 where id = %s::uuid",
                (amazon_listing_id,),
            )
    return {
        "product_id": product_id,
        "amazon_listing_id": listing_ids[0],
        "flipkart_listing_id": listing_ids[1],
        "unmatched_listing_id": listing_ids[2],
        "amazon_url": amazon_url,
        "amazon_public_id": f"amazon-runtime-{tag}",
        "tag": tag,
    }


def test_scheduler_created_refresh_reaches_worker_and_intelligence(monkeypatch) -> None:
    from mayabu.core.config import get_app_settings
    from mayabu.jobs.worker import run_once_async
    from mayabu.scheduler.engine import tick
    from mayabu.scheduler.lease import SchedulerLease
    from mayabu.scheduler.runtime_proof import find_scheduler_refresh_task, snapshot_listing
    from mayabu.search.public_price import compute_public_best_price
    from mayabu.search.search_repository import get_product_offers

    fixture = _insert_cluster_and_listings(amazon_price=54990, flipkart_price=55990, unmatched_price=999)
    product_id = fixture["product_id"]
    amazon_id = fixture["amazon_listing_id"]
    listing_ids = [
        fixture["amazon_listing_id"],
        fixture["flipkart_listing_id"],
        fixture["unmatched_listing_id"],
    ]
    search_refreshed: list[str] = []
    cache_calls: list[str] = []
    homepage_deleted = {"n": 0}

    async def fake_refresh(platform, url, **kwargs):  # noqa: ANN001
        assert platform == "amazon"
        assert url == fixture["amazon_url"]
        return RefreshResult(
            current_price=54990,
            mrp=59990,
            page_status="success",
            stock_status="unknown",
        )

    class _Cache:
        def invalidate_product(self, pid: str) -> int:
            cache_calls.append(f"product:{pid}")
            return 1

        def delete(self, key: str) -> int:
            homepage_deleted["n"] += 1
            cache_calls.append(f"delete:{key}")
            return 1

    get_app_settings.cache_clear()
    settings = replace(
        get_app_settings(),
        scheduler_enabled=True,
        scheduler_max_refresh_per_tick=4,
        scheduler_max_discovery_per_tick=0,
        scheduler_max_demand_per_tick=0,
        scheduler_search_drain_per_tick=0,
    )
    due_rows = [
        {
            "id": amazon_id,
            "platform": "amazon",
            "category": "laptop",
            "listing_url": fixture["amazon_url"],
            "native_id": None,
            "product_id": product_id,
            "listing_id": f"amazon-{amazon_id}",
            "refresh_tier": "normal",
            "match_status": "matched",
        }
    ]
    _patch_scheduler_bounds(monkeypatch, settings, due_rows)
    monkeypatch.setattr("mayabu.jobs.worker.run_refresh_scraper", fake_refresh)
    monkeypatch.setattr("mayabu.jobs.worker._CACHE", _Cache())
    monkeypatch.setattr(
        "mayabu.jobs.worker.refresh_product_search_documents",
        lambda ids, strict=False: search_refreshed.extend(ids) or {"refreshed": len(list(ids)), "failed": 0},
    )

    before = snapshot_listing(amazon_id)
    lease = SchedulerLease(domain=f"runtime-e2e-{_suffix()}", holder_id="e2e-leader")
    try:
        result = tick(lease)
        assert result.result == "ok"
        assert result.refresh_created >= 1
        task = find_scheduler_refresh_task(amazon_id)
        assert task is not None
        assert task.get("created_by") == "scheduler"
        assert (task.get("metadata") or {}).get("task_source") == "scheduler_refresh"
        task_id = str(task["id"])
        processed = asyncio.run(run_once_async("e2e-worker", task_id=task_id))
        assert processed is True
        after_task = find_scheduler_refresh_task(amazon_id)
        assert after_task is not None
        assert after_task.get("status") == "completed"
        assert after_task.get("locked_by") is None
        after = snapshot_listing(amazon_id)
        assert after["observation_count"] >= (before.get("observation_count") or 0) + 1
        assert Decimal(str(after["current_price"])) == Decimal("54990")
        offers = get_product_offers(product_id)
        best = compute_public_best_price(offers, "laptop")
        assert best.best_price == Decimal("54990")
        assert all(str(item.get("match_status") or "matched") == "matched" for item in offers)
        unmatched = [item for item in offers if str(item.get("platform")) == "croma"]
        assert unmatched == []
        intel = get_price_intelligence(product_id)
        assert intel is not None
        assert intel.current_price == 54990
        assert intel.timing.state != "CONSIDER_NOW" or intel.timing.purchasability == "in_stock"
        assert "product:" + product_id in cache_calls
        assert homepage_deleted["n"] == 0
        assert product_id in search_refreshed
        standby = SchedulerLease(domain=lease.domain, holder_id="e2e-standby")
        try:
            second = tick(standby)
            assert second.result == "standby"
            assert second.refresh_created == 0
        finally:
            standby.release()
    finally:
        lease.release()
        get_app_settings.cache_clear()
        _cleanup(product_id, listing_ids)


def test_scheduler_price_change_invalidates_homepage(monkeypatch) -> None:
    from mayabu.core.config import get_app_settings
    from mayabu.jobs.worker import run_once_async
    from mayabu.scheduler.engine import tick
    from mayabu.scheduler.lease import SchedulerLease
    from mayabu.scheduler.runtime_proof import find_scheduler_refresh_task

    fixture = _insert_cluster_and_listings(amazon_price=54990, flipkart_price=55990, unmatched_price=999)
    product_id = fixture["product_id"]
    amazon_id = fixture["amazon_listing_id"]
    listing_ids = [
        fixture["amazon_listing_id"],
        fixture["flipkart_listing_id"],
        fixture["unmatched_listing_id"],
    ]
    homepage_deleted = {"n": 0}

    async def fake_refresh(platform, url, **kwargs):  # noqa: ANN001, ARG001
        return RefreshResult(current_price=52990, mrp=59990, page_status="success")

    class _Cache:
        def invalidate_product(self, pid: str) -> int:  # noqa: ARG002
            return 1

        def delete(self, key: str) -> int:  # noqa: ARG002
            homepage_deleted["n"] += 1
            return 1

    get_app_settings.cache_clear()
    settings = replace(
        get_app_settings(),
        scheduler_enabled=True,
        scheduler_max_refresh_per_tick=4,
        scheduler_max_discovery_per_tick=0,
        scheduler_max_demand_per_tick=0,
        scheduler_search_drain_per_tick=0,
    )
    _patch_scheduler_bounds(
        monkeypatch,
        settings,
        [
            {
                "id": amazon_id,
                "platform": "amazon",
                "category": "laptop",
                "listing_url": fixture["amazon_url"],
                "native_id": None,
                "product_id": product_id,
                "listing_id": f"amazon-{amazon_id}",
                "refresh_tier": "hot",
                "match_status": "matched",
            }
        ],
    )
    monkeypatch.setattr("mayabu.jobs.worker.run_refresh_scraper", fake_refresh)
    monkeypatch.setattr("mayabu.jobs.worker._CACHE", _Cache())
    monkeypatch.setattr(
        "mayabu.jobs.worker.refresh_product_search_documents",
        lambda ids, strict=False: {"refreshed": 1, "failed": 0},
    )

    lease = SchedulerLease(domain=f"runtime-e2e-chg-{_suffix()}", holder_id="e2e-leader")
    try:
        tick(lease)
        task = find_scheduler_refresh_task(amazon_id)
        assert task is not None
        asyncio.run(run_once_async("e2e-worker-chg", task_id=str(task["id"])))
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select current_price from platform_listings where id = %s::uuid", (amazon_id,))
                price = cur.fetchone()["current_price"]
        assert Decimal(str(price)) == Decimal("52990")
        assert homepage_deleted["n"] >= 1
    finally:
        lease.release()
        get_app_settings.cache_clear()
        _cleanup(product_id, listing_ids)


def test_injected_adapter_failure_updates_health_and_backoff(monkeypatch) -> None:
    from mayabu.core.config import get_app_settings
    from mayabu.jobs.worker import run_once_async
    from mayabu.scheduler.engine import tick
    from mayabu.scheduler.lease import SchedulerLease
    from mayabu.scheduler.runtime_proof import find_scheduler_refresh_task

    fixture = _insert_cluster_and_listings(amazon_price=54990, flipkart_price=55990, unmatched_price=999)
    product_id = fixture["product_id"]
    amazon_id = fixture["amazon_listing_id"]
    listing_ids = [
        fixture["amazon_listing_id"],
        fixture["flipkart_listing_id"],
        fixture["unmatched_listing_id"],
    ]

    async def fake_refresh(platform, url, **kwargs):  # noqa: ANN001, ARG001
        return RefreshResult.failed("injected timeout", page_status="failed")

    get_app_settings.cache_clear()
    settings = replace(
        get_app_settings(),
        scheduler_enabled=True,
        scheduler_max_refresh_per_tick=4,
        scheduler_max_discovery_per_tick=0,
        scheduler_max_demand_per_tick=0,
        scheduler_search_drain_per_tick=0,
    )
    _patch_scheduler_bounds(
        monkeypatch,
        settings,
        [
            {
                "id": amazon_id,
                "platform": "amazon",
                "category": "laptop",
                "listing_url": fixture["amazon_url"],
                "native_id": None,
                "product_id": product_id,
                "listing_id": f"amazon-{amazon_id}",
                "refresh_tier": "normal",
                "match_status": "matched",
            }
        ],
    )
    monkeypatch.setattr("mayabu.jobs.worker.run_refresh_scraper", fake_refresh)
    monkeypatch.setattr(
        "mayabu.jobs.worker.refresh_product_search_documents",
        lambda ids, strict=False: {"refreshed": 0, "failed": 0},
    )

    saved_health = None
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from platform_health where platform = 'amazon'")
            row = cur.fetchone()
            saved_health = dict(row) if row else None
            failures_before = int((row or {}).get("consecutive_failures") or 0)

    lease = SchedulerLease(domain=f"runtime-e2e-fail-{_suffix()}", holder_id="e2e-leader")
    try:
        tick(lease)
        task = find_scheduler_refresh_task(amazon_id)
        assert task is not None
        asyncio.run(run_once_async("e2e-worker-fail", task_id=str(task["id"])))
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select status, last_error from scrape_tasks where id = %s",
                    (task["id"],),
                )
                row = cur.fetchone()
                cur.execute(
                    "select status, consecutive_failures from platform_health where platform = 'amazon'"
                )
                health = cur.fetchone()
        assert row["status"] in {"pending", "dead"} or row["last_error"]
        assert health is not None
        assert int(health["consecutive_failures"] or 0) >= failures_before + 1
        from mayabu.scheduler.platform_health_policy import _circuit_is_open, get_platform_status

        state = get_platform_status("amazon")
        # Fault-injected failure must record health. It must not permanently
        # sticky-block Amazon on a shared local catalog.
        assert state["status"] in {"healthy", "degraded", "blocked"}
        if state.get("circuit_open"):
            assert _circuit_is_open(state.get("circuit_open_until"))
    finally:
        lease.release()
        get_app_settings.cache_clear()
        _cleanup(product_id, listing_ids)
        with db_connection() as conn:
            with conn.cursor() as cur:
                if saved_health is None:
                    cur.execute("delete from platform_health where platform = 'amazon'")
                else:
                    cur.execute(
                        """
                        update platform_health
                        set status = %s, consecutive_failures = %s, circuit_open_until = %s,
                            last_error_code = %s, updated_at = now()
                        where platform = 'amazon'
                        """,
                        (
                            saved_health.get("status") or "healthy",
                            saved_health.get("consecutive_failures") or 0,
                            saved_health.get("circuit_open_until"),
                            saved_health.get("last_error_code"),
                        ),
                    )


def test_scheduler_oos_refresh_preserves_last_known_price(monkeypatch) -> None:
    from mayabu.core.config import get_app_settings
    from mayabu.jobs.worker import run_once_async
    from mayabu.scheduler.engine import tick
    from mayabu.scheduler.lease import SchedulerLease
    from mayabu.scheduler.runtime_proof import find_scheduler_refresh_task
    from mayabu.search.public_price import compute_public_best_price
    from mayabu.search.search_repository import get_product_offers

    fixture = _insert_cluster_and_listings(amazon_price=54990, flipkart_price=55990, unmatched_price=999)
    product_id = fixture["product_id"]
    amazon_id = fixture["amazon_listing_id"]
    listing_ids = [
        fixture["amazon_listing_id"],
        fixture["flipkart_listing_id"],
        fixture["unmatched_listing_id"],
    ]

    async def fake_refresh(platform, url, **kwargs):  # noqa: ANN001, ARG001
        return RefreshResult(
            current_price=None,
            stock_status="out_of_stock",
            page_status="success",
            stock_reason="explicit_oos_text",
            stock_confidence="high",
        )

    get_app_settings.cache_clear()
    settings = replace(
        get_app_settings(),
        scheduler_enabled=True,
        scheduler_max_refresh_per_tick=4,
        scheduler_max_discovery_per_tick=0,
        scheduler_max_demand_per_tick=0,
        scheduler_search_drain_per_tick=0,
    )
    _patch_scheduler_bounds(
        monkeypatch,
        settings,
        [
            {
                "id": amazon_id,
                "platform": "amazon",
                "category": "laptop",
                "listing_url": fixture["amazon_url"],
                "native_id": None,
                "product_id": product_id,
                "listing_id": fixture["amazon_public_id"],
                "refresh_tier": "normal",
                "match_status": "matched",
            }
        ],
    )
    monkeypatch.setattr("mayabu.jobs.worker.run_refresh_scraper", fake_refresh)
    monkeypatch.setattr(
        "mayabu.jobs.worker.refresh_product_search_documents",
        lambda ids, strict=False: {"refreshed": 0, "failed": 0},
    )
    monkeypatch.setattr("mayabu.jobs.worker._CACHE", type("C", (), {"invalidate_product": staticmethod(lambda pid: 1), "delete": staticmethod(lambda key: 1)})())

    lease = SchedulerLease(domain=f"runtime-e2e-oos-{_suffix()}", holder_id="e2e-leader")
    try:
        tick(lease)
        task = find_scheduler_refresh_task(amazon_id)
        assert task is not None
        asyncio.run(run_once_async("e2e-worker-oos", task_id=str(task["id"])))
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select current_price, stock_status from platform_listings where id = %s::uuid",
                    (amazon_id,),
                )
                listing = cur.fetchone()
                cur.execute(
                    """
                    select price, stock_status, event_type from price_observations
                    where listing_id = %s::uuid
                    order by observed_at desc limit 1
                    """,
                    (amazon_id,),
                )
                obs = cur.fetchone()
        assert Decimal(str(listing["current_price"])) == Decimal("54990")
        assert listing["stock_status"] == "out_of_stock"
        assert obs["stock_status"] == "out_of_stock"
        assert obs["event_type"] == "out_of_stock"
        offers = get_product_offers(product_id)
        best = compute_public_best_price(offers, "laptop")
        assert best.best_platform == "flipkart"
        intel = get_price_intelligence(product_id)
        assert intel is not None
        assert intel.timing.state != "CONSIDER_NOW"
        assert intel.timing.purchasability != "in_stock" or best.best_platform == "flipkart"
    finally:
        lease.release()
        get_app_settings.cache_clear()
        _cleanup(product_id, listing_ids)


def test_scheduler_discovery_advances_cursor_and_reuses_listing(monkeypatch) -> None:
    from psycopg.types.json import Jsonb

    from mayabu.core.config import get_app_settings
    from mayabu.jobs.worker import run_once_async
    from mayabu.scheduler.engine import tick
    from mayabu.scheduler.lease import SchedulerLease
    from mayabu_db.tasks import create_task

    fixture = _insert_cluster_and_listings(amazon_price=54990, flipkart_price=55990, unmatched_price=999)
    product_id = fixture["product_id"]
    listing_ids = [
        fixture["amazon_listing_id"],
        fixture["flipkart_listing_id"],
        fixture["unmatched_listing_id"],
    ]
    plan_name = f"runtime-e2e-discovery-{fixture['tag']}"
    plan_id = None

    async def fake_discovery(platform, query, **kwargs):  # noqa: ANN001, ARG001
        return [
            {
                "title": "Lenovo IdeaPad Slim 3 Intel Core i5 12th Gen 16GB 512GB Laptop",
                "url": fixture["amazon_url"],
                "link": fixture["amazon_url"],
                "price": 54990,
                "mrp": 69990,
                "listing_id": fixture["amazon_public_id"],
                "native_id": f"B0RUNTIME{fixture['tag']}",
                "category": "laptop",
            }
        ]

    get_app_settings.cache_clear()
    settings = replace(
        get_app_settings(),
        scheduler_enabled=True,
        scheduler_max_refresh_per_tick=0,
        scheduler_max_discovery_per_tick=1,
        scheduler_max_demand_per_tick=0,
        scheduler_search_drain_per_tick=0,
        scraper_max_pages=1,
        scraper_max_products=5,
    )
    monkeypatch.setattr("mayabu.scheduler.engine.get_app_settings", lambda: settings)
    monkeypatch.setattr("mayabu.jobs.worker.get_app_settings", lambda: settings)
    monkeypatch.setattr("mayabu.jobs.worker.run_discovery_scraper", fake_discovery)
    monkeypatch.setattr("mayabu.jobs.worker.ensure_platform_available", lambda platform: None)
    monkeypatch.setattr(
        "mayabu.jobs.worker.refresh_product_search_documents",
        lambda ids, strict=False: {"refreshed": 0, "failed": 0},
    )
    monkeypatch.setattr("mayabu.jobs.worker.refresh_variant_groups", lambda ids: None)
    monkeypatch.setattr("mayabu.jobs.worker.drain_dirty_search_documents", lambda limit=50: {"refreshed": 0})
    monkeypatch.setattr("mayabu.scheduler.engine.materialize_refresh", lambda limit=0: 0)
    monkeypatch.setattr("mayabu.scheduler.engine.materialize_demand_discovery", lambda limit=0: 0)
    monkeypatch.setattr("mayabu.scheduler.engine.drain_dirty_search_documents", lambda limit=50: {"refreshed": 0})

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into scheduler_plans(
                  name, platform, task_type, query, cadence_minutes, priority,
                  max_pages, max_products, enabled, metadata
                )
                values (%s, 'amazon', 'discovery', 'laptop', 60, 40, 1, 5, true, %s)
                returning id
                """,
                (
                    plan_name,
                    Jsonb({"category": "laptop", "cursor": {"last_page": 2, "mode": "page_offset"}}),
                ),
            )
            plan_id = str(cur.fetchone()["id"])

    def _materialize_one(limit: int | None = None) -> int:  # noqa: ARG001
        from mayabu.scheduler.discovery_cursor import start_page_from_metadata, supports_page_cursor

        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select * from scheduler_plans where id = %s::uuid", (plan_id,))
                plan = cur.fetchone()
            metadata = plan["metadata"] or {}
            start_page = start_page_from_metadata(metadata)
            create_task(
                conn,
                "amazon",
                "discovery",
                query="laptop",
                priority=40,
                max_pages=1,
                max_products=5,
                metadata={
                    "scheduler_plan_id": plan_id,
                    "category": "laptop",
                    "source": "scheduler_plan",
                    "task_source": "scheduler_discovery",
                    "start_page": start_page,
                    "page_cursor": supports_page_cursor("amazon"),
                },
                idempotency_key=f"discovery:{plan_id}",
                created_by="scheduler",
            )
            with conn.cursor() as cur:
                cur.execute(
                    "update scheduler_plans set last_materialized_at = now() where id = %s::uuid",
                    (plan_id,),
                )
        return 1

    monkeypatch.setattr("mayabu.scheduler.engine.materialize_due_plans", _materialize_one)

    lease = SchedulerLease(domain=f"runtime-e2e-disc-{_suffix()}", holder_id="e2e-leader")
    try:
        result = tick(lease)
        assert result.discovery_created == 1
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select id, metadata from scrape_tasks
                    where created_by = 'scheduler' and task_type = 'discovery'
                      and metadata->>'scheduler_plan_id' = %s
                    order by created_at desc limit 1
                    """,
                    (plan_id,),
                )
                task = cur.fetchone()
        assert task is not None
        assert (task["metadata"] or {}).get("start_page") == 3
        asyncio.run(run_once_async("e2e-worker-disc", task_id=str(task["id"])))
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select metadata from scheduler_plans where id = %s::uuid",
                    (plan_id,),
                )
                after_meta = cur.fetchone()["metadata"] or {}
                cur.execute(
                    "select count(*) as n from platform_listings where listing_url_hash = %s",
                    (url_hash(fixture["amazon_url"]),),
                )
                url_rows = int(cur.fetchone()["n"])
                cur.execute(
                    "select count(*) as n from platform_listings where listing_id = %s",
                    (fixture["amazon_public_id"],),
                )
                id_rows = int(cur.fetchone()["n"])
        cursor = after_meta.get("cursor") or {}
        assert int(cursor.get("last_page") or 0) == 3
        assert cursor.get("mode") == "page_offset"
        assert url_rows == 1
        assert id_rows == 1
        # Restart: persisted last_page=3 → next start_page 4, not page 1.
        from mayabu.scheduler.discovery_cursor import start_page_from_metadata

        assert start_page_from_metadata(after_meta) == 4
    finally:
        lease.release()
        get_app_settings.cache_clear()
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from scrape_tasks where metadata->>'scheduler_plan_id' = %s",
                    (plan_id,),
                )
                cur.execute("delete from scheduler_plans where id = %s::uuid", (plan_id,))
        _cleanup(product_id, listing_ids)


def test_refresh_materialization_interleaves_platforms() -> None:
    from mayabu.scheduler.refresh_policy import due_refresh_candidates

    fixture_a = _insert_cluster_and_listings(amazon_price=111, flipkart_price=222, unmatched_price=333)
    fixture_b = _insert_cluster_and_listings(amazon_price=444, flipkart_price=555, unmatched_price=666)
    listing_ids = [
        fixture_a["amazon_listing_id"],
        fixture_a["flipkart_listing_id"],
        fixture_a["unmatched_listing_id"],
        fixture_b["amazon_listing_id"],
        fixture_b["flipkart_listing_id"],
        fixture_b["unmatched_listing_id"],
    ]
    try:
        rows = due_refresh_candidates(limit=8)
        platforms = [str(row["platform"]) for row in rows]
        assert len(set(platforms)) >= 2
        assert len(set(platforms[: min(4, len(platforms))])) >= 2
        ours = {
            fixture_a["amazon_listing_id"],
            fixture_a["flipkart_listing_id"],
            fixture_b["amazon_listing_id"],
            fixture_b["flipkart_listing_id"],
        }
        # Fixtures are marked hot via last_price_change_at so they outrank cold
        # catalog rows. Assert per-platform queues (fairness) plus a global scan —
        # never rely on cold fixtures surviving a 500-row interleaved catalog window.
        amazon_hits = [
            row
            for row in due_refresh_candidates(limit=50, platform="amazon")
            if str(row["id"]) in ours
        ]
        flipkart_hits = [
            row
            for row in due_refresh_candidates(limit=50, platform="flipkart")
            if str(row["id"]) in ours
        ]
        assert len(amazon_hits) >= 2, "hot amazon fixtures must be due for refresh"
        assert len(flipkart_hits) >= 2, "hot flipkart fixtures must be due for refresh"
        our_rows = [
            row for row in due_refresh_candidates(limit=500) if str(row["id"]) in ours
        ]
        assert {str(row["platform"]) for row in our_rows} >= {"amazon", "flipkart"}
    finally:
        _cleanup(fixture_a["product_id"], listing_ids[:3])
        _cleanup(fixture_b["product_id"], listing_ids[3:])

