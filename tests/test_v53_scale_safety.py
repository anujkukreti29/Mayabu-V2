from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from mayabu.core import distributed_limit
from mayabu.search import search_repository


class FakeRedis:
    def __init__(self):
        self.tokens: set[str] = set()
        self.released: list[tuple[str, str]] = []

    def eval(self, script, key_count, key, *args):
        assert key_count == 1
        if "ZREMRANGEBYSCORE" in script:
            token = str(args[3])
            self.tokens.add(token)
            return 1
        token = str(args[0])
        return 1 if token in self.tokens else 0

    def zrem(self, key, token):
        self.tokens.discard(token)
        self.released.append((key, token))
        return 1


class FakeCache:
    def __init__(self):
        self.client = FakeRedis()
        self.failures: list[Exception] = []

    def coordination_client(self):
        return self.client

    def note_failure(self, exc):
        self.failures.append(exc)


def test_distributed_slot_acquires_shared_key_and_releases(monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(
        distributed_limit,
        "get_app_settings",
        lambda: SimpleNamespace(
            redis_url="redis://test",
            environment="production",
            redis_key_prefix="production",
        ),
    )

    async def run():
        async with distributed_limit.distributed_slot(
            "scrape-platform",
            "Amazon",
            1,
            ttl_seconds=30,
            wait_seconds=1,
            cache=cache,
        ):
            assert len(cache.client.tokens) == 1

    asyncio.run(run())
    assert cache.client.released
    assert cache.client.released[0][0] == "mayabu:production:slots:scrape-platform:amazon"


def test_distributed_slot_enforces_shared_cap_across_concurrent_holders(monkeypatch):
    """Two concurrent holders with limit=1: second must fail to acquire."""

    class CountingRedis(FakeRedis):
        def eval(self, script, key_count, key, *args):
            assert key_count == 1
            if "ZREMRANGEBYSCORE" in script:
                now = float(args[0])
                # Drop expired (scores are expiry timestamps in FakeRedis tokens map
                # we store only active tokens without scores — approximate with set size).
                token = str(args[3])
                limit = int(args[2])
                if len(self.tokens) >= limit:
                    return 0
                self.tokens.add(token)
                return 1
            token = str(args[0])
            return 1 if token in self.tokens else 0

    cache = FakeCache()
    cache.client = CountingRedis()
    monkeypatch.setattr(
        distributed_limit,
        "get_app_settings",
        lambda: SimpleNamespace(
            redis_url="redis://test",
            environment="production",
            redis_key_prefix="production",
        ),
    )

    async def run():
        async with distributed_limit.distributed_slot(
            "scrape-platform",
            "amazon",
            1,
            ttl_seconds=30,
            wait_seconds=0.2,
            cache=cache,
        ):
            assert len(cache.client.tokens) == 1

            async def second_holder() -> None:
                async with distributed_limit.distributed_slot(
                    "scrape-platform",
                    "amazon",
                    1,
                    ttl_seconds=30,
                    wait_seconds=0.2,
                    cache=cache,
                ):
                    return None

            with pytest.raises(distributed_limit.DistributedCapacityError):
                await second_holder()

    asyncio.run(run())


def test_all_network_scrape_paths_use_the_shared_capacity_gate():
    root = Path(__file__).resolve().parents[1]
    source = (root / "mayabu" / "jobs" / "worker.py").read_text(encoding="utf-8")
    assert source.count("async with scraper_capacity.acquire(platform):") == 4
    assert "run_discovery_scraper" in source
    assert "run_refresh_scraper" in source
    assert "verify_listing" in source
    assert "ingest_product_url" in source


def test_dynamic_sql_identifiers_are_composed_safely():
    root = Path(__file__).resolve().parents[1]
    budget = (root / "mayabu" / "scheduler" / "budget_policy.py").read_text(
        encoding="utf-8"
    )
    health = (root / "mayabu_db" / "health.py").read_text(encoding="utf-8")
    assert "sql.Identifier" in budget
    assert "sql.Identifier" in health
    assert 'f"select count(*)' not in health
    assert 'f"update scrape_budget' not in budget


def test_search_mode_is_explicit(monkeypatch):
    monkeypatch.setattr(
        search_repository,
        "_source_relation",
        lambda: ("product_search_documents", True),
    )
    assert search_repository.search_source_status() == {
        "mode": "v5_indexed",
        "relation": "product_search_documents",
        "v5": True,
    }
    monkeypatch.setattr(
        search_repository, "_source_relation", lambda: ("product_search_index", False)
    )
    assert search_repository.search_source_status()["mode"] == "legacy_indexed"
    monkeypatch.setattr(search_repository, "_source_relation", lambda: ("", False))
    assert search_repository.search_source_status()["mode"] == "live_fallback"


def test_ci_pipeline_covers_backend_and_frontend_quality_gates():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for command in (
        "python -m compileall",
        "ruff check",
        "pytest",
        "npm run typecheck",
        "npm run lint",
        "npm run test",
        "npm run build",
    ):
        assert command in workflow


def test_default_worker_id_is_hostname_derived():
    root = Path(__file__).resolve().parents[1]
    config = (root / "mayabu" / "core" / "config.py").read_text(encoding="utf-8")
    assert "socket.gethostname()" in config
    assert 'os.getenv("MAYABU_WORKER_ID")' in config


def test_verification_is_marked_running_only_after_capacity_is_acquired():
    root = Path(__file__).resolve().parents[1]
    source = (root / "mayabu" / "jobs" / "worker.py").read_text(encoding="utf-8")
    capacity = source.index(
        "async with scraper_capacity.acquire(platform):",
        source.index("def _execute_verification"),
    )
    started = source.index("mark_verification_started", capacity)
    outcome = source.index("outcome = await verify_listing", started)
    assert capacity < started < outcome
