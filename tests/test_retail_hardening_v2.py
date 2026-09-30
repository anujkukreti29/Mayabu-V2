"""Retailer hardening + camera/matching fixture tests."""

from __future__ import annotations

from pathlib import Path

from mayabu.scrapers.jiomart_parse import parse_jiomart_embedded
from mayabu.scrapers.poorvika_parse import (
    parse_poorvika_embedded,
    records_from_pim_group_payload,
    resolve_poorvika_listing_path,
)
from mayabu.scrapers.retail_parse import price_to_int
from mayabu.scrapers.vijaysales_parse import (
    parse_vijaysales_embedded,
    resolve_vijaysales_listing_path,
)
from vijaysales_scraper import build_search_url as vs_url
from poorvika_scraper import build_search_url as pv_url

FIXTURES = Path(__file__).parent / "fixtures" / "retail"


def test_emi_price_rejected() -> None:
    assert price_to_int("EMI from ₹499/month") is None
    assert price_to_int("₹52,990") == 52990
    # Selling price then EMI noise in same card blob → keep selling price
    assert price_to_int("₹1,53,990\nStd. EMI starting from ₹7,050/mo for 24 months.") == 153990


def test_vijaysales_search_url_prefers_category_pages() -> None:
    assert resolve_vijaysales_listing_path("gaming laptop") == "/c/laptops"
    assert vs_url("laptop") == "https://www.vijaysales.com/c/laptops"
    assert vs_url("laptop", 2) == "https://www.vijaysales.com/c/laptops?page=2"
    assert vs_url("smartphone") == "https://www.vijaysales.com/c/mobiles"
    assert vs_url("camera") == "https://www.vijaysales.com/c/camera"
    # Free-text falls back to /search?q=
    assert vs_url("xyz-unknown-sku") == "https://www.vijaysales.com/search?q=xyz-unknown-sku"
    assert "/search/laptop" not in vs_url("laptop")


def test_vijaysales_fixture_jsonld_and_emi_card() -> None:
    html = (FIXTURES / "vijaysales_listing.html").read_text(encoding="utf-8")
    rows = parse_vijaysales_embedded(html)
    assert len(rows) >= 2
    titles = {r["title"] for r in rows}
    assert any("HP 15s" in t for t in titles)
    # EMI-only card must not invent a selling price via price_to_int path
    assert price_to_int("EMI from ₹499/month") is None


def test_poorvika_fixture_dedupes_nested_links() -> None:
    html = (FIXTURES / "poorvika_listing.html").read_text(encoding="utf-8")
    rows = parse_poorvika_embedded(html)
    links = [r.get("link") for r in rows]
    assert len(links) == len(set(links))
    assert any("hp-15s" in str(r.get("link") or "").lower() for r in rows)


def test_poorvika_category_path_mapping() -> None:
    assert resolve_poorvika_listing_path("gaming laptop") == "/laptops/page"
    assert "/laptops/page" in pv_url("laptop")
    assert "search?q=" not in pv_url("laptop")


def test_poorvika_pim_group_payload() -> None:
    payload = {
        "status": 200,
        "data": [
            {
                "name": "ASUS VivoBook 15 Intel Core i3",
                "code": "asus-vivobook-15-i3",
                "prices": [{"pl": "ONLINE", "sp": [{"price": "42990"}]}],
                "mrp": [{"price": "49990"}],
                "image": {"url": "https://www.poorvika.com/img/x.jpg"},
            },
            {
                "name": "ASUS VivoBook 15 Intel Core i3",
                "code": "asus-vivobook-15-i3",
                "prices": [{"pl": "ONLINE", "sp": [{"price": "42990"}]}],
            },
        ],
    }
    rows = records_from_pim_group_payload(payload)
    assert len(rows) == 1
    assert rows[0]["link"].endswith("/asus-vivobook-15-i3/p")
    assert rows[0]["currentPrice"] == "42990"


def test_jiomart_empty_shell_still_empty() -> None:
    html = (FIXTURES / "jiomart_empty_shell.html").read_text(encoding="utf-8")
    assert parse_jiomart_embedded(html) == []
