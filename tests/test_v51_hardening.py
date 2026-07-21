from __future__ import annotations

import inspect
from pathlib import Path
from mayabu.domain.matching import assess_product_match
from mayabu.scrapers.capacity import platform_limit
from mayabu.search.cache import Cache
from mayabu.search import search_repository
from mayabu_db.matching import choose_match


def _listing(title: str, *, storage: int) -> dict:
    return {
        "title": title,
        "title_norm": title.lower(),
        "category": "laptop",
        "specs": {
            "brand": "asus",
            "family": "vivobook 14",
            "model_codes": [
                "X1407CA-LY1581WS" if storage == 1024 else "X1407CA-LY160WS"
            ],
            "cpu_models": ["intel core ultra 5 225h"],
            "ram_gb": 16,
            "storage_gb": storage,
            "screen_inch": 14.0,
        },
    }


def _product(title: str, *, storage: int, product_id: str = "p1") -> dict:
    row = _listing(title, storage=storage)
    return {
        "id": product_id,
        "product_id": product_id,
        "canonical_title": title,
        "title_norm": title.lower(),
        "category": "laptop",
        "brand": "asus",
        "specs": row["specs"],
    }


def test_unified_matcher_accepts_exact_product() -> None:
    title = "ASUS Vivobook 14 Ultra 5 225H 16GB 1TB X1407CA-LY1581WS"
    assessment = assess_product_match(
        _listing(title, storage=1024), _product(title, storage=1024)
    )
    assert assessment.relation == "exact"
    assert assessment.merge_allowed is True
    assert assessment.needs_review is False


def test_unified_matcher_blocks_storage_variant_even_with_nearly_identical_title() -> (
    None
):
    one_tb = _listing(
        "ASUS Vivobook 14 Ultra 5 225H 16GB 1TB X1407CA-LY1581WS", storage=1024
    )
    half_tb = _product(
        "ASUS Vivobook 14 Ultra 5 225H 16GB 512GB X1407CA-LY160WS", storage=512
    )
    assessment = assess_product_match(one_tb, half_tb)
    assert assessment.relation == "variant"
    assert assessment.merge_allowed is False
    assert assessment.needs_review is False


def test_discovery_choose_match_uses_unified_identity_rules() -> None:
    listing = _listing(
        "ASUS Vivobook 14 Ultra 5 225H 16GB 1TB X1407CA-LY1581WS", storage=1024
    )
    variant = _product(
        "ASUS Vivobook 14 Ultra 5 225H 16GB 512GB X1407CA-LY160WS",
        storage=512,
        product_id="variant",
    )
    exact = _product(
        "ASUS Vivobook 14 Ultra 5 225H 16GB 1TB X1407CA-LY1581WS",
        storage=1024,
        product_id="exact",
    )
    product_id, score, method, evidence, needs_review = choose_match(
        listing, [variant, exact]
    )
    assert product_id == "exact"
    assert score == 1000.0
    assert method == "deterministic_identity_exact"
    assert evidence["deterministic_relation"] == "exact"
    assert needs_review is False


def test_product_invalidation_does_not_wipe_search_cache() -> None:
    cache = Cache()
    calls: list[str] = []
    cache.delete_prefix = lambda prefix, batch_size=500: calls.append(prefix) or 1  # type: ignore[method-assign]
    assert cache.invalidate_product("abc") == 2
    assert calls == ["product:abc:", "price-history:abc:"]


def test_worker_platform_limit_uses_configuration() -> None:
    assert platform_limit("flipkart", configured=1) == 1
    assert platform_limit("flipkart", configured=5) == 2
    assert platform_limit("amazon", configured=5) == 1
    assert platform_limit("unknown", configured=5) == 1


def test_v5_search_paginates_in_sql() -> None:
    source = inspect.getsource(search_repository._v5_indexed_search)
    assert "limit %s offset %s" in source.lower()
    assert "ranked[offset" not in source


def test_search_source_is_memoized() -> None:
    assert hasattr(search_repository._source_relation, "cache_clear")
    assert hasattr(search_repository._source_relation, "cache_info")


def test_production_modules_no_longer_depend_on_json_catalog_matcher() -> None:
    root = Path(__file__).resolve().parents[1]
    production_files = list((root / "mayabu").rglob("*.py")) + list(
        (root / "mayabu_db").rglob("*.py")
    )
    offenders = [
        str(path.relative_to(root))
        for path in production_files
        if "mayabu_catalog" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_container_runtime_is_non_root_and_schema_has_admin_audit_log() -> None:
    root = Path(__file__).resolve().parents[1]
    assert "USER mayabu" in (root / "Dockerfile.api").read_text(encoding="utf-8")
    assert "USER mayabu" in (root / "Dockerfile.worker").read_text(encoding="utf-8")
    assert (
        "create table if not exists admin_audit_log"
        in (root / "mayabu_db" / "schema.sql").read_text(encoding="utf-8").lower()
    )
