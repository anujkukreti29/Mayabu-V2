from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from mayabu_refresh.common import (
    detect_stock_status,
    calculate_discount_percent,
    clean_price_to_int,
    close_common_popups,
    extract_first_price_text,
    extract_price_refresh_by_visible_text,
    maybe_save_debug,
    result_from_values,
)
from mayabu_refresh.models import RefreshResult


CROMA_HEADLESS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

PRICE_RE = (
    r"(?:₹|Rs\.?|INR)\s*"
    r"([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.\d{1,2})?|[0-9]{4,6}(?:\.\d{1,2})?)"
)


def _price_to_int(value: str | None) -> int | None:
    if not value:
        return None

    text = str(value)
    text = text.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace("INR", "")
    text = re.sub(r"\.\d{1,2}$", "", text.strip())
    digits = re.sub(r"[^\d]", "", text)

    if not digits:
        return None

    try:
        price = int(digits)
    except ValueError:
        return None

    if price < 5_000 or price > 500_000:
        return None

    return price


def _clean_html_text(value: str | None) -> str:
    if not value:
        return ""

    text = str(value)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)

    text = (
        text.replace("&nbsp;", " ")
        .replace("&#8377;", "₹")
        .replace("&amp;", "&")
        .replace("\\u20b9", "₹")
        .replace("\u20b9", "₹")
    )

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _first_price(patterns: list[str], text: str) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if not match:
            continue

        for group in match.groups():
            price = _price_to_int(group)
            if price is not None:
                return price

    return None


def _all_prices(text: str) -> list[int]:
    prices: list[int] = []

    for raw in re.findall(PRICE_RE, text, flags=re.I):
        price = _price_to_int(raw)
        if price is not None:
            prices.append(price)

    return prices


def _extract_initial_data_prices(html: str | None) -> tuple[int | None, int | None]:
    """
    Croma product pages include reliable SSR price data in window.__INITIAL_DATA__.

    Example:
    "pdpPriceReducer":{"pdpPriceData":{"sellingPrice":{"value":"92994.00"},"mrp":{"value":"125890.00"}}}
    """
    if not html:
        return None, None

    text = str(html)
    text = (
        text.replace("&quot;", '"')
        .replace("&#34;", '"')
        .replace("\\u002F", "/")
        .replace("\\u20b9", "₹")
    )

    start = text.find('"pdpPriceReducer"')
    if start == -1:
        start = text.find("pdpPriceReducer")

    if start == -1:
        return None, None

    chunk = text[start : start + 5000]

    selling_match = re.search(
        r'"sellingPrice"\s*:\s*\{\s*"value"\s*:\s*"([^"]+)"',
        chunk,
        flags=re.I | re.S,
    )

    mrp_match = re.search(
        r'"mrp"\s*:\s*\{\s*"value"\s*:\s*"([^"]+)"',
        chunk,
        flags=re.I | re.S,
    )

    current_price = _price_to_int(selling_match.group(1)) if selling_match else None
    mrp = _price_to_int(mrp_match.group(1)) if mrp_match else None

    return current_price, mrp


def _extract_ld_json_price(html: str | None) -> int | None:
    if not html:
        return None

    match = re.search(
        r'"offers"\s*:\s*\{.*?"price"\s*:\s*"([^"]+)"',
        html,
        flags=re.I | re.S,
    )

    if not match:
        return None

    return _price_to_int(match.group(1))


def _extract_discount_near_price(text: str) -> float | None:
    patterns = [
        r"Save\s*(?:₹|Rs\.?|INR)?\s*[\d,]+(?:\.\d{1,2})?\s*,\s*(\d{1,2}(?:\.\d+)?)\s*%\s*Off",
        r"(\d{1,2}(?:\.\d+)?)\s*%\s*Off",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue

        try:
            value = float(match.group(1))
        except ValueError:
            continue

        if 0 <= value <= 95:
            return value

    return None


def _extract_text_prices(
    text: str | None,
) -> tuple[int | None, int | None, float | None]:
    clean = _clean_html_text(text)

    mrp = _first_price(
        [
            rf"\bMRP\s*[:\-]?\s*{PRICE_RE}",
            rf"\bM\.R\.P\.?\s*[:\-]?\s*{PRICE_RE}",
            rf"\bMaximum\s+Retail\s+Price\s*[:\-]?\s*{PRICE_RE}",
        ],
        clean,
    )

    current_price = _first_price(
        [
            rf"{PRICE_RE}\s*\(\s*Incl\.?\s*all\s*Taxes\s*\)",
            rf"{PRICE_RE}\s*\(Incl\.?\s*all\s*Taxes\)",
        ],
        clean,
    )

    if current_price is None:
        before_mrp = re.split(
            r"\bMRP\b|\bM\.R\.P",
            clean,
            maxsplit=1,
            flags=re.I,
        )[0]

        prices_before_mrp = _all_prices(before_mrp)

        if prices_before_mrp:
            current_price = max(prices_before_mrp)

    discount = None

    mrp_block_match = re.search(
        rf"\bMRP\s*[:\-]?\s*{PRICE_RE}.{{0,160}}",
        clean,
        flags=re.I | re.S,
    )

    if mrp_block_match:
        discount = _extract_discount_near_price(mrp_block_match.group(0))

    return current_price, mrp, discount


async def _extract_dom_prices(page: Any) -> tuple[int | None, int | None]:
    current_price: int | None = None
    mrp: int | None = None

    current_selectors = [
        "meta[property='product:price:amount']",
        "meta[itemprop='price']",
        "[itemprop='price']",
        "#pdp-product-price",
        "[data-testid='new-price']",
        ".new-price .amount",
        ".new-price",
        "[class*='new-price']",
        "[class*='amount']",
        "[class*='price']",
    ]

    for selector in current_selectors:
        try:
            el = await page.query_selector(selector)
            if not el:
                continue

            raw = (
                await el.get_attribute("content")
                or await el.get_attribute("value")
                or await el.inner_text()
            )

            price_text = extract_first_price_text(raw) or raw
            price = clean_price_to_int(price_text) or _price_to_int(price_text)

            if price is not None and 5_000 <= price <= 500_000:
                current_price = price
                break

        except Exception:
            continue

    mrp_selectors = [
        "#old-price",
        ".old-price",
        ".pdp-mrp",
        "[class*='old-price']",
        "[class*='mrp']",
        "[class*='MRP']",
        "[class*='strike']",
    ]

    for selector in mrp_selectors:
        try:
            els = await page.query_selector_all(selector)

            for el in els:
                raw = await el.inner_text()
                price = _first_price(
                    [
                        rf"\bMRP\s*[:\-]?\s*{PRICE_RE}",
                        rf"\bM\.R\.P\.?\s*[:\-]?\s*{PRICE_RE}",
                        rf"{PRICE_RE}",
                    ],
                    raw,
                )

                if price is not None:
                    mrp = price
                    return current_price, mrp

        except Exception:
            continue

    return current_price, mrp


def _sane_mrp(current_price: int | None, mrp: int | None) -> bool:
    if current_price is None or mrp is None:
        return False

    if mrp <= current_price:
        return False

    # Reject wrong values like 464970 for a 92994 laptop.
    if mrp > current_price * 2.5:
        return False

    return True


async def _install_croma_stealth(context: Any) -> None:
    await context.add_init_script(
        """
        (() => {
            try {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            } catch (e) {}

            try {
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-IN', 'en-US', 'en']
                });
            } catch (e) {}

            try {
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            } catch (e) {}

            try {
                window.chrome = window.chrome || {};
                window.chrome.runtime = window.chrome.runtime || {};
            } catch (e) {}

            try {
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : originalQuery(parameters)
                );
            } catch (e) {}
        })();
        """
    )


async def _wait_for_croma_price_render(page: Any) -> None:
    price_patterns = [
        "₹",
        "MRP",
        "Incl. all Taxes",
        "EMI Options",
        "Save",
    ]

    for _ in range(10):
        try:
            body_text = await page.locator("body").inner_text(timeout=2500)
        except Exception:
            body_text = ""

        body_lc = body_text.lower()
        matched = sum(1 for pattern in price_patterns if pattern.lower() in body_lc)

        if matched >= 2 and "₹" in body_text:
            return

        try:
            await page.mouse.wheel(0, 500)
        except Exception:
            pass

        await page.wait_for_timeout(1200)


async def _close_croma_location_modal(page: Any) -> None:
    selectors = [
        "button:has-text('Continue')",
        "button:has-text('CONTINUE')",
        "text=Continue",
        "[class*='close']",
        "button[aria-label='Close']",
        "svg[data-testid='CloseIcon']",
    ]

    for selector in selectors:
        try:
            el = await page.query_selector(selector)
            if not el:
                continue

            await el.click(timeout=1500)
            await page.wait_for_timeout(800)
            return

        except Exception:
            continue


async def scrape_croma_refresh(
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
) -> RefreshResult:
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--window-size=1366,768",
                ],
            )
        except Exception:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--window-size=1366,768",
                ],
            )

        context = await browser.new_context(
            user_agent=CROMA_HEADLESS_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        await _install_croma_stealth(context)

        page = await context.new_page()
        page.set_default_timeout(20000)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=65000)
            await page.wait_for_timeout(2500)

            await close_common_popups(page)
            await _close_croma_location_modal(page)

            try:
                await page.mouse.move(420, 320)
                await page.wait_for_timeout(500)
            except Exception:
                pass

            try:
                await page.evaluate("window.scrollTo(0, 240)")
                await page.wait_for_timeout(1200)
            except Exception:
                pass

            await _wait_for_croma_price_render(page)

            html = await page.content()
            html_lc = html.lower()

            blocked_terms = [
                "captcha",
                "access denied",
                "verify you are human",
                "unusual traffic",
                "are you a human",
            ]

            if any(term in html_lc for term in blocked_terms):
                await maybe_save_debug(
                    page,
                    prefix="croma_blocked",
                    debug=debug,
                    artifact_dir=artifact_dir,
                )
                return RefreshResult.failed("croma_blocked_or_captcha", "captcha")

            # Most reliable for headless Croma.
            initial_current, initial_mrp = _extract_initial_data_prices(html)

            # Secondary fallback from schema.org JSON-LD.
            ld_current = _extract_ld_json_price(html)

            try:
                body_text = await page.locator("body").inner_text(timeout=8000)
            except Exception:
                body_text = ""

            text_current, text_mrp, text_discount = _extract_text_prices(body_text)
            html_current, html_mrp, html_discount = _extract_text_prices(html)
            dom_current, dom_mrp = await _extract_dom_prices(page)

            current_price = (
                initial_current
                or ld_current
                or text_current
                or dom_current
                or html_current
            )

            mrp: int | None = None

            for candidate in [initial_mrp, text_mrp, html_mrp, dom_mrp]:
                if _sane_mrp(current_price, candidate):
                    mrp = candidate
                    break

            if current_price is None or mrp is None:
                fallback = await extract_price_refresh_by_visible_text(page)

                if current_price is None:
                    current_price = fallback.current_price

                if mrp is None and _sane_mrp(current_price, fallback.mrp):
                    mrp = fallback.mrp

            calculated_discount = calculate_discount_percent(current_price, mrp)

            # Accuracy rule:
            # If MRP exists, calculate from current price + MRP.
            # If MRP is missing, never trust random bank-offer percentage.
            discount = calculated_discount

            if discount is None and mrp is not None:
                discount = text_discount or html_discount

            result = result_from_values(
                current_price=current_price,
                mrp=mrp,
                discount_percent=discount,
                raw_price_text=str(current_price)
                if current_price is not None
                else None,
                raw_mrp_text=str(mrp) if mrp is not None else None,
            )

            if mrp is None:
                result.discount_percent = None
                result.warnings.append("missing_or_unsane_mrp")

            await maybe_save_debug(
                page,
                prefix="croma_refresh",
                debug=debug,
                artifact_dir=artifact_dir,
            )

            result.stock_status = detect_stock_status(html_lc)  # type: ignore[assignment]
            return result

        except Exception as exc:
            await maybe_save_debug(
                page,
                prefix="croma_error",
                debug=debug,
                artifact_dir=artifact_dir,
            )
            return RefreshResult.failed(f"croma_refresh_error: {exc}")

        finally:
            await context.close()
            await browser.close()
