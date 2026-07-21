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
        page.set_default_timeout(14000)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=50000)
            await page.wait_for_timeout(2400)
            await close_common_popups(page)
            await page.evaluate("window.scrollTo(0, 340)")
            await page.wait_for_timeout(700)

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
            for selector in [
                "meta[property='product:price:amount']",
                "meta[itemprop='price']",
                "[itemprop='price']",
            ]:
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
            result.stock_status = detect_stock_status(html_lc)  # type: ignore[assignment]
            return result
        except Exception as exc:
            await maybe_save_debug(
                page, prefix="flipkart_error", debug=debug, artifact_dir=artifact_dir
            )
            return RefreshResult.failed(f"flipkart_refresh_error: {exc}")
        finally:
            await context.close()
            await browser.close()
