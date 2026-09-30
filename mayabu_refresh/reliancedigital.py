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
    "div.product-price",
    ".product-price",
    "[class*='selling-price']",
    "[class*='offer-price']",
    "meta[property='product:price:amount']",
]


async def _price_text(el) -> str | None:
    if not el:
        return None
    aria_price = await el.get_attribute("aria-label")
    if aria_price:
        return aria_price.strip()
    text = (await el.inner_text()).strip()
    text = (
        text.replace("Deal Price", "")
        .replace("Offer Price", "")
        .replace("MRP", "")
        .strip()
    )
    return extract_first_price_text(text) or (text if text else None)


async def scrape_reliancedigital_refresh(
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
) -> RefreshResult:
    """Refresh only Reliance Digital price fields."""
    pool = get_refresh_browser_pool()
    try:
        async with pool.page(headless=headless, default_timeout_ms=12_000) as page:
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            await close_common_popups(page)
            await wait_for_price_or_stock(
                page,
                price_selectors=_PRICE_SELECTORS,
                timeout_ms=6_000,
            )
            await page.evaluate("window.scrollTo(0, 300)")

            html_lc = (await page.content()).lower()
            if any(
                term in html_lc
                for term in ["captcha", "verify you are human", "access denied"]
            ):
                await maybe_save_debug(
                    page,
                    prefix="reliance_blocked",
                    debug=debug,
                    artifact_dir=artifact_dir,
                )
                return RefreshResult.failed("reliance_blocked_or_captcha", "captcha")

            price_text = await _price_text(
                await page.query_selector(
                    "div.product-price, .product-price, [class*='selling-price'], [class*='offer-price']"
                )
            )
            mrp_text = await _price_text(
                await page.query_selector(
                    "span.product-marked-price, .product-marked-price, [class*='marked-price'], [class*='mrp']"
                )
            )

            result = result_from_texts(price_text=price_text, mrp_text=mrp_text)
            if result.current_price is None or result.mrp is None:
                fallback = await extract_price_refresh_by_visible_text(page)
                if result.current_price is None:
                    result.current_price = fallback.current_price
                if result.mrp is None:
                    result.mrp = fallback.mrp
                result.discount_percent = (
                    result.discount_percent or fallback.discount_percent
                )
                result.page_status = (
                    "success" if result.current_price is not None else "partial"
                )

            await maybe_save_debug(
                page, prefix="reliance_refresh", debug=debug, artifact_dir=artifact_dir
            )
            classify_and_apply_stock(result, html_lc, scoped=False)
            return result
    except Exception as exc:
        return RefreshResult.failed(f"reliance_refresh_error: {exc}")
