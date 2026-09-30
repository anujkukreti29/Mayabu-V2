"""Stock classification correctness — false OOS must be zero on curated cases."""

from __future__ import annotations

from mayabu_refresh.models import RefreshResult
from mayabu_refresh.stock import classify_stock_text, resolve_stock_for_ingest


def test_full_html_with_add_to_cart_is_in_stock_despite_related_oos() -> None:
    html = """
    related products: this item is currently unavailable
    <button>Add to Cart</button>
    In Stock.
    """
    c = classify_stock_text(html, scoped=False)
    assert c.public_stock == "in_stock"
    assert c.reason in {"purchase_cta", "explicit_in_stock_text"}


def test_not_available_alone_is_not_oos() -> None:
    c = classify_stock_text("delivery: not available in your area", scoped=False)
    assert c.public_stock == "unknown"
    assert c.state in {"parser_uncertain", "unknown", "delivery_location_required"}


def test_explicit_oos_scoped_is_oos() -> None:
    c = classify_stock_text("Currently unavailable.", scoped=True)
    assert c.public_stock == "out_of_stock"
    assert c.confidence == "high"


def test_challenge_is_not_oos() -> None:
    c = classify_stock_text("robot check captcha", page_status="captcha")
    assert c.state == "challenge"
    assert c.public_stock == "unknown"


def test_in_stock_to_oos_requires_high_confidence() -> None:
    stock, reason = resolve_stock_for_ingest(
        detected="out_of_stock",
        previous="in_stock",
        page_status="success",
        update_stock=True,
        reason="explicit_oos_text",
        confidence="medium",
    )
    assert stock == "unknown"
    assert reason == "ambiguous_oos_not_published"

    stock2, _ = resolve_stock_for_ingest(
        detected="out_of_stock",
        previous="in_stock",
        page_status="success",
        update_stock=True,
        reason="explicit_oos_text",
        confidence="high",
    )
    assert stock2 == "out_of_stock"


def test_challenge_preserves_prior_in_stock() -> None:
    stock, reason = resolve_stock_for_ingest(
        detected="unknown",
        previous="in_stock",
        page_status="captcha",
        update_stock=True,
        reason="challenge_or_captcha",
        confidence="high",
    )
    assert stock == "in_stock"
    assert "preserve" in reason


def test_croma_uses_browser_pool() -> None:
    import inspect

    from mayabu_refresh import croma

    source = inspect.getsource(croma.scrape_croma_refresh)
    assert "get_refresh_browser_pool" in source
    assert "async_playwright" not in source


def test_detect_stock_status_wrapper_never_oos_on_weak_noise() -> None:
    from mayabu_refresh.common import detect_stock_status

    assert detect_stock_status("something not available somehow") == "unknown"
