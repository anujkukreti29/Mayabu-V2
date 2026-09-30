from __future__ import annotations

from pathlib import Path

from mayabu_refresh.browser_pool import get_refresh_browser_pool, wait_for_price_or_stock
from mayabu_refresh.common import (
    calculate_discount_percent,
    close_common_popups,
    classify_and_apply_stock,
    extract_first_price_text,
    extract_price_refresh_by_visible_text,
    maybe_save_debug,
    result_from_texts,
)
from mayabu_refresh.models import RefreshResult

_PRICE_SELECTORS = [
    "#corePrice_feature_div span.priceToPay span.a-offscreen",
    "#corePriceDisplay_desktop_feature_div span.priceToPay span.a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price.priceToPay .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    "span.priceToPay span.a-offscreen",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    "[itemprop='price']",
]
_STOCK_SELECTORS = ["#availability span", "#outOfStock"]


async def scrape_amazon_refresh(
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
) -> RefreshResult:
    """Refresh only Amazon India price fields."""
    pool = get_refresh_browser_pool()
    try:
        async with pool.page(headless=headless, default_timeout_ms=12_000) as page:
            await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
            await close_common_popups(page)
            await wait_for_price_or_stock(
                page,
                price_selectors=_PRICE_SELECTORS,
                stock_selectors=_STOCK_SELECTORS,
                timeout_ms=6_000,
            )
            await page.evaluate("window.scrollTo(0, 260)")

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

            if not price_text:
                for whole_sel in (
                    "#corePrice_feature_div span.priceToPay span.a-price-whole",
                    "#corePriceDisplay_desktop_feature_div span.priceToPay span.a-price-whole",
                    "#corePriceDisplay_desktop_feature_div .a-price[data-a-color='price'] span.a-price-whole",
                ):
                    whole_el = await page.query_selector(whole_sel)
                    if not whole_el:
                        continue
                    whole = (await whole_el.inner_text() or "").strip()
                    frac_el = await page.query_selector(
                        whole_sel.replace("a-price-whole", "a-price-fraction")
                    )
                    frac = (await frac_el.inner_text() or "").strip() if frac_el else ""
                    price_text = extract_first_price_text(
                        f"{whole}.{frac}" if frac else whole
                    ) or (f"{whole}.{frac}" if frac else whole)
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
            # Prefer availability region when present; fall back to full HTML conservatively.
            avail = ""
            for sel in ("#availability", "#outOfStock", "#addToCart"):
                try:
                    el = await page.query_selector(sel)
                    if el:
                        avail += " " + ((await el.inner_text()) or "")
                except Exception:
                    continue
            classify_and_apply_stock(result, avail.strip() or html_lc, scoped=bool(avail.strip()))
            return result
    except Exception as exc:
        return RefreshResult.failed(f"amazon_refresh_error: {exc}")
