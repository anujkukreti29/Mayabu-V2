"""Shared PDP refresh extraction for newer retail platforms.

Prefers JSON-LD / Offer data, then OpenGraph, then visible price text.
Never overwrites a previously good price with null at the ingestion layer —
this module simply returns what it can extract.
"""

from __future__ import annotations

from pathlib import Path

from mayabu.scrapers.retail_discovery import page_looks_blocked
from mayabu.scrapers.retail_parse import extract_refresh_from_html
from mayabu_refresh.browser_pool import get_refresh_browser_pool, wait_for_price_or_stock
from mayabu_refresh.common import (
    calculate_discount_percent,
    close_common_popups,
    detect_stock_status,
    maybe_save_debug,
    result_from_values,
)
from mayabu_refresh.models import RefreshResult

_GENERIC_PRICE_SELECTORS = [
    "meta[property='product:price:amount']",
    "meta[itemprop='price']",
    "[itemprop='price']",
    "meta[property='og:price:amount']",
]


async def scrape_platform_refresh(
    platform: str,
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
    category: str | None = None,
) -> RefreshResult:
    last_error: str | None = None
    pool = get_refresh_browser_pool()
    try:
        async with pool.page(headless=headless, default_timeout_ms=12_000) as page:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
            await close_common_popups(page)
            await wait_for_price_or_stock(
                page,
                price_selectors=_GENERIC_PRICE_SELECTORS,
                timeout_ms=5_000,
            )
            if response is not None and response.status == 404:
                result = result_from_values(
                    current_price=None,
                    mrp=None,
                    warnings=["http_404"],
                )
                result.page_status = "not_found"
                return result
            if await page_looks_blocked(page):
                await maybe_save_debug(
                    page, prefix=f"{platform}_blocked", debug=debug, artifact_dir=artifact_dir
                )
                result = result_from_values(
                    current_price=None,
                    mrp=None,
                    warnings=["blocked_or_captcha"],
                )
                result.page_status = "blocked"
                return result
            html = await page.content()
            current, mrp = extract_refresh_from_html(html, category=category)
            # Stock detection is best-effort metadata for refresh logs.
            _ = detect_stock_status(html)
            discount = calculate_discount_percent(current, mrp)
            result = result_from_values(
                current_price=current,
                mrp=mrp,
                discount_percent=discount,
                warnings=[] if current is not None else ["missing_price"],
            )
            if debug and result.page_status != "success":
                await maybe_save_debug(
                    page,
                    prefix=f"{platform}_{result.page_status}",
                    debug=debug,
                    artifact_dir=artifact_dir,
                )
            return result
    except Exception as exc:
        last_error = str(exc)[:500]
    result = result_from_values(
        current_price=None,
        mrp=None,
        warnings=[f"refresh_error: {last_error or 'unknown'}"],
    )
    result.page_status = "failed"
    return result
