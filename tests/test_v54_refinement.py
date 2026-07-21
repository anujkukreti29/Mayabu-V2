from __future__ import annotations

from mayabu.domain.matching import score_product_similarity
from mayabu.search.query_parser import normalize_query


def test_rom_normalization_only_rewrites_the_standalone_spec_token() -> None:
    assert normalize_query("8GB RAM 128GB ROM") == "8gb ram 128gb storage"
    assert "chromebook" in normalize_query("HP Chromebook 14")
    assert "ch storage ebook" not in normalize_query("HP Chromebook 14")


def test_matching_handles_malformed_numeric_specs_conservatively() -> None:
    listing = {
        "title": "Example laptop 16GB 512GB",
        "specs": {"brand": "example", "ram_gb": "sixteen", "storage_gb": "512"},
    }
    product = {
        "canonical_title": "Example laptop 8GB 512GB",
        "specs": {"brand": "example", "ram_gb": "8", "storage_gb": 512},
    }
    score, evidence = score_product_similarity(listing, product)
    assert score == -100.0
    assert "ram" in evidence["reject"]


def test_fuzzy_matching_caps_pathological_title_length() -> None:
    long_title = "example laptop " + ("x" * 100_000)
    product = {
        "canonical_title": long_title,
        "specs": {"brand": "example"},
    }
    score, evidence = score_product_similarity(
        {"title": long_title, "specs": {"brand": "example"}},
        product,
    )
    assert score >= 0
    assert evidence["title_sequence"] == 1.0


def test_distributed_slot_stops_work_when_renewal_is_lost(monkeypatch) -> None:
    import pytest

    from mayabu.core import distributed_limit

    class Redis:
        def eval(self, script, key_count, key, *args):
            del key_count, key, args
            return 1 if "ZREMRANGEBYSCORE" in script else 0

        def zrem(self, key, token):
            del key, token
            return 1

    class Cache:
        def coordination_client(self):
            return Redis()

        def note_failure(self, exc):
            del exc

    monkeypatch.setattr(
        distributed_limit,
        "get_app_settings",
        lambda: type(
            "Settings", (), {"redis_url": "redis://test", "environment": "production"}
        )(),
    )

    async def lose_lease(client, cache, key, token, policy, stop, lost, owner):
        del client, cache, key, token, policy, stop
        lost.set()
        if owner and not owner.done():
            owner.cancel()

    monkeypatch.setattr(distributed_limit, "_renew_lease", lose_lease)

    async def run() -> None:
        with pytest.raises(distributed_limit.DistributedCapacityError):
            async with distributed_limit.distributed_slot(
                "scrape-platform",
                "amazon",
                1,
                ttl_seconds=30,
                wait_seconds=1,
                cache=Cache(),
            ):
                await __import__("asyncio").sleep(0.01)

    __import__("asyncio").run(run())


def test_worker_task_registry_keeps_compatible_aliases() -> None:
    from mayabu.jobs.worker import _TASK_HANDLERS

    expected = {
        "discovery",
        "discovery_search",
        "refresh_listing",
        "refresh_hot_product",
        "verify_listing",
        "direct_ingest",
        "enrichment",
        "index_product",
        "maintenance",
    }
    assert expected <= set(_TASK_HANDLERS)
