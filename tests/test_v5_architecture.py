from __future__ import annotations

from pathlib import Path

import pytest

from mayabu.api.search_routes import _decode_cursor, _encode_cursor
from mayabu.domain.product_identity import build_identity, classify_relation
from mayabu.jobs.queue import idempotency_key
from mayabu.scrapers.detail.models import DetailProduct
from mayabu.scrapers.platforms import detect_platform, validate_product_url
from mayabu.search.query_parser import parse_query


def test_sku_only_query_is_a_relevant_exact_product_search() -> None:
    parsed = parse_query("X1407CA-LY1581WS")
    assert parsed.is_relevant is True
    # SKU-only queries search across public categories (no laptop fallback).
    assert parsed.detected_category in {None, "laptop"}
    assert parsed.intent in {"exact_product", "cross_category_search"}
    assert parsed.model_codes
    assert any("X1407CA" in code for code in parsed.model_codes)


def test_exact_and_variant_relations_are_kept_separate() -> None:
    one_tb = build_identity("ASUS Vivobook 14 Core Ultra 5 225H 16GB RAM 1TB SSD X1407CA-LY1581WS")
    same = build_identity("ASUS Vivobook 14 Core Ultra 5 225H 16GB RAM 1TB SSD X1407CA-LY1581WS")
    half_tb = build_identity("ASUS Vivobook 14 Core Ultra 5 225H 16GB RAM 512GB SSD X1407CA-LY160WS")
    assert classify_relation(one_tb, same) == "exact"
    assert classify_relation(one_tb, half_tb) == "variant"
    assert one_tb.exact_fingerprint != half_tb.exact_fingerprint
    assert one_tb.family_fingerprint == half_tb.family_fingerprint


def test_macbook_storage_variants_are_not_exact() -> None:
    base = build_identity("Apple MacBook Air M2 8GB 256GB")
    larger = build_identity("Apple MacBook Air M2 8GB 512GB")
    assert classify_relation(base, larger) == "variant"


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.amazon.in/dp/B0ABCDEFGHI", "amazon"),
        ("https://www.flipkart.com/example/p/itm123?pid=COM123", "flipkart"),
        ("https://www.croma.com/example/p/123456", "croma"),
        ("https://www.reliancedigital.in/example/p/123456", "reliancedigital"),
    ],
)
def test_platform_detection(url: str, platform: str) -> None:
    assert detect_platform(url) == platform
    assert validate_product_url(platform, url).startswith("https://")


def test_platform_detection_rejects_lookalike_and_non_http_urls() -> None:
    with pytest.raises(ValueError):
        detect_platform("https://amazon.in.evil.example/dp/B0ABCDEFGHI")
    with pytest.raises(ValueError):
        detect_platform("file:///etc/passwd")


def test_pagination_cursor_roundtrip_and_bounds() -> None:
    cursor = _encode_cursor(120)
    assert _decode_cursor(cursor) == 120
    with pytest.raises(Exception):
        _decode_cursor("not-a-valid-cursor")


def test_job_idempotency_is_stable_and_sensitive_to_url() -> None:
    first = idempotency_key("direct_ingest", "amazon", url="https://amazon.in/dp/B0ABCDEFGHI?tag=tracking")
    same = idempotency_key("direct_ingest", "amazon", url="https://amazon.in/dp/B0ABCDEFGHI")
    other = idempotency_key("direct_ingest", "amazon", url="https://amazon.in/dp/B0ZZZZZZZZZ")
    assert first == same
    assert first != other


def test_detail_product_conversion_handles_discount() -> None:
    detail = DetailProduct(
        platform="flipkart",
        url="https://www.flipkart.com/example/p/itm123?pid=COM123",
        canonical_url="https://www.flipkart.com/example/p/itm123?pid=COM123",
        title="Apple MacBook Air M2 8GB 256GB",
        current_price=70000,
        mrp=100000,
        status="success",
    )
    raw = detail.to_raw_listing()
    assert raw["discount_pct"] == 30.0
    assert raw["price"] == 70000


def test_v5_schema_contains_production_primitives() -> None:
    schema = Path("mayabu_db/schema.sql").read_text(encoding="utf-8")
    for expected in (
        "create table if not exists product_search_documents",
        "create table if not exists search_document_dirty",
        "create table if not exists variant_groups",
        "create table if not exists maintenance_runs",
        "lease_expires_at",
        "circuit_open_until",
        "refresh_product_search_document",
    ):
        assert expected in schema
