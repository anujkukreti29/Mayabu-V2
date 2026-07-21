from __future__ import annotations

from pathlib import Path

from playwright.async_api import async_playwright

from mayabu_refresh.common import (
    DEFAULT_USER_AGENT,
    detect_stock_status,
    close_common_popups,
    extract_first_price_text,
    extract_price_refresh_by_visible_text,
    maybe_save_debug,
    result_from_texts,
)
from mayabu_refresh.models import RefreshResult


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
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
        )
        page = await context.new_page()
        page.set_default_timeout(15000)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=55000)
            await page.wait_for_timeout(3000)
            await close_common_popups(page)
            await page.evaluate("window.scrollTo(0, 300)")
            await page.wait_for_timeout(900)

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
            result.stock_status = detect_stock_status(html_lc)  # type: ignore[assignment]
            return result
        except Exception as exc:
            await maybe_save_debug(
                page, prefix="reliance_error", debug=debug, artifact_dir=artifact_dir
            )
            return RefreshResult.failed(f"reliance_refresh_error: {exc}")
        finally:
            await context.close()
            await browser.close()
