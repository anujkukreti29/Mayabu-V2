from __future__ import annotations

from pathlib import Path

from mayabu_refresh.browser_pool import get_refresh_browser_pool, wait_for_price_or_stock
from mayabu_refresh.common import (
    close_common_popups,
    classify_and_apply_stock,
    extract_first_price_text,
    extract_price_refresh_by_visible_text,
    maybe_save_debug,
    result_from_texts,
)
from mayabu_refresh.models import RefreshResult

_PRICE_SELECTORS = [
    "meta[property='product:price:amount']",
    "meta[itemprop='price']",
    "[itemprop='price']",
]


async def scrape_flipkart_refresh(
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
) -> RefreshResult:
    """Refresh only Flipkart price fields: current_price, mrp, discount_percent.

    Generated Flipkart class names are intentionally not used. Stable selectors
    and selectorless visible-text extraction are used instead.
    """
    pool = get_refresh_browser_pool()
    try:
        async with pool.page(headless=headless, default_timeout_ms=12_000) as page:
            await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
            await close_common_popups(page)
            await wait_for_price_or_stock(
                page,
                price_selectors=_PRICE_SELECTORS,
                timeout_ms=6_000,
            )
            await page.evaluate("window.scrollTo(0, 340)")

            html_lc = (await page.content()).lower()
            if any(
                term in html_lc
                for term in ["captcha", "unusual traffic", "verify you are human"]
            ):
                await maybe_save_debug(
                    page,
                    prefix="flipkart_blocked",
                    debug=debug,
                    artifact_dir=artifact_dir,
                )
                return RefreshResult.failed("flipkart_blocked_or_captcha", "captcha")

            price_text = None
            for selector in _PRICE_SELECTORS:
                el = await page.query_selector(selector)
                if el:
                    raw = (
                        await el.get_attribute("content")
                        or await el.get_attribute("value")
                        or await el.inner_text()
                    )
                    price_text = extract_first_price_text(raw) or (raw or "").strip()
                    if price_text:
                        break

            # Do not use generated class chains for MRP. Let the visible-text
            # fallback detect nearby line-through/plain larger MRP.
            selector_result = result_from_texts(price_text=price_text, mrp_text=None)
            if selector_result.current_price is not None:
                visible_result = await extract_price_refresh_by_visible_text(page)
                if visible_result.mrp or visible_result.discount_percent:
                    selector_result.mrp = visible_result.mrp
                    selector_result.discount_percent = visible_result.discount_percent
                result = selector_result
            else:
                result = await extract_price_refresh_by_visible_text(page)

            await maybe_save_debug(
                page, prefix="flipkart_refresh", debug=debug, artifact_dir=artifact_dir
            )
            classify_and_apply_stock(result, html_lc, scoped=False)
            return result
    except Exception as exc:
        return RefreshResult.failed(f"flipkart_refresh_error: {exc}")
