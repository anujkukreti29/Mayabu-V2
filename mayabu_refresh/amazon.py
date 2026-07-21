from __future__ import annotations

from pathlib import Path

from playwright.async_api import async_playwright

from mayabu_refresh.common import (
    DEFAULT_USER_AGENT,
    detect_stock_status,
    calculate_discount_percent,
    close_common_popups,
    extract_first_price_text,
    extract_price_refresh_by_visible_text,
    maybe_save_debug,
    result_from_texts,
)
from mayabu_refresh.models import RefreshResult


async def scrape_amazon_refresh(
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
) -> RefreshResult:
    """Refresh only Amazon India price fields."""
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
            await page.wait_for_timeout(2500)
            await close_common_popups(page)
            await page.evaluate("window.scrollTo(0, 260)")
            await page.wait_for_timeout(700)

            html_lc = (await page.content()).lower()
            if any(
                term in html_lc
                for term in [
                    "robot check",
                    "captcha",
                    "enter the characters you see below",
                ]
            ):
                await maybe_save_debug(
                    page,
                    prefix="amazon_blocked",
                    debug=debug,
                    artifact_dir=artifact_dir,
                )
                return RefreshResult.failed("amazon_blocked_or_captcha", "captcha")

            price_text = None
            for selector in [
                "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
                "span.priceToPay span.a-offscreen",
                "#priceblock_ourprice",
                "#priceblock_dealprice",
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

            mrp_text = None
            for selector in [
                "span.a-price.a-text-price.apex-basisprice-value span.a-offscreen",
                "#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen",
                "span.a-text-price span.a-offscreen",
            ]:
                el = await page.query_selector(selector)
                if el:
                    raw = await el.inner_text()
                    mrp_text = extract_first_price_text(raw) or (raw or "").strip()
                    if mrp_text:
                        break

            result = result_from_texts(price_text=price_text, mrp_text=mrp_text)
            if result.current_price is None or result.mrp is None:
                fallback = await extract_price_refresh_by_visible_text(page)

                if result.current_price is None:
                    result.current_price = fallback.current_price

                if result.mrp is None:
                    result.mrp = fallback.mrp

                calculated_discount = calculate_discount_percent(
                    result.current_price, result.mrp
                )

                if calculated_discount is not None:
                    result.discount_percent = calculated_discount
                else:
                    result.discount_percent = (
                        result.discount_percent or fallback.discount_percent
                    )

                result.page_status = (
                    "success" if result.current_price is not None else "partial"
                )
            else:
                result.discount_percent = calculate_discount_percent(
                    result.current_price, result.mrp
                )

            await maybe_save_debug(
                page, prefix="amazon_refresh", debug=debug, artifact_dir=artifact_dir
            )
            result.stock_status = detect_stock_status(html_lc)  # type: ignore[assignment]
            return result
        except Exception as exc:
            await maybe_save_debug(
                page, prefix="amazon_error", debug=debug, artifact_dir=artifact_dir
            )
            return RefreshResult.failed(f"amazon_refresh_error: {exc}")
        finally:
            await context.close()
            await browser.close()
