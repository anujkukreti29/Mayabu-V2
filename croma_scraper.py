from __future__ import annotations

import argparse
import asyncio
import html as html_lib
import re
import urllib.parse
from typing import Any

from playwright.async_api import async_playwright

from mayabu_common import utc_now
from mayabu_scraper_base import (
    ScrapeConfig,
    attr_or_none,
    close_common_popups,
    discovery_health_report,
    extract_structural_discovery_records,
    finalize_records,
    first_existing_selector,
    human_scroll,
    recover_cards_when_empty,
    save_or_print,
    text_or_none,
    wait_for_any_selector,
)

PLATFORM = "croma"

CROMA_HEADLESS_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

CARD_SELECTORS = [
    "li.product-item",
    "div.product-item",
    "[class*='product-item']",
    "[class*='plp-card']",
    "div[class*='product-card']",
    "li[class*='product']",
    "[data-testid*='product']",
]

TITLE_SELECTORS = [
    "h3",
    "h2",
    "h4",
    "[class*='product-title']",
    "[class*='product__title']",
    "[class*='title']",
]

PRICE_SELECTORS = [
    ".new-price",
    "[class*='new-price']",
    "[class*='selling-price']",
    "[class*='offer-price']",
    "[class*='discounted-price']",
    "[class*='amount']",
]

MRP_SELECTORS = [
    ".old-price",
    "[class*='old-price']",
    "[class*='mrp']",
    "[class*='original-price']",
    "[class*='market-price']",
    "[class*='strike']",
]

DISCOUNT_SELECTORS = [
    "[class*='discount']",
    "[class*='offer']",
    "[class*='savings']",
]

LINK_SELECTORS = ["a[href*='/p/']", "a[href]"]
IMAGE_SELECTORS = ["img[src]", "img[data-src]", "source[srcset]"]

VIEW_MORE_SELECTORS = [
    "button:has-text('View More')",
    "button:has-text('Load More')",
    "button:has-text('Show More')",
]

POPUP_SELECTORS = [
    "button:has-text('Allow')",
    "button:has-text('Accept')",
    "button:has-text('OK')",
    "button:has-text('Close')",
    "button:has-text('No thanks')",
    "button:has-text('Continue')",
    "button:has-text('CONTINUE')",
    "[aria-label='Close']",
    "[class*='close']",
]

PRICE_TEXT_RE = re.compile(
    r"(?:₹|Rs\.?|INR)?\s*"
    r"([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.\d{1,2})?|[0-9]{4,6}(?:\.\d{1,2})?)",
    re.I,
)

PRODUCT_URL_RE = re.compile(
    r"(?:https?:\\?/\\?/www\.croma\.com)?(?P<url>/[^\"'<>\\]*?/p/(?P<id>\d{4,12}))",
    re.I,
)

MEDIA_URL_RE = re.compile(
    r"https?:\\?/\\?/media\.(?:tata)?croma\.com[^\"'<>\s]+",
    re.I,
)


def _decode_text(value: str | None) -> str:
    if not value:
        return ""

    text = str(value)
    text = html_lib.unescape(text)

    replacements = {
        "\\u002F": "/",
        "\\/": "/",
        "\\u003A": ":",
        "\\u003a": ":",
        "\\u0026": "&",
        "\\u003F": "?",
        "\\u003f": "?",
        "\\u003D": "=",
        "\\u003d": "=",
        "\\u002D": "-",
        "\\u002d": "-",
        "\\u20b9": "₹",
        "&nbsp;": " ",
        "&#8377;": "₹",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def _clean_text(value: str | None) -> str:
    text = _decode_text(value)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\[nrt]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _unescape_json_value(value: str | None) -> str:
    if not value:
        return ""

    text = _decode_text(value)

    try:
        text = bytes(text, "utf-8").decode("unicode_escape")
    except Exception:
        pass

    text = _clean_text(text)
    return text.strip(' "')


def _price_to_int(value: Any) -> int | None:
    if value is None:
        return None

    text = _decode_text(str(value))
    match = PRICE_TEXT_RE.search(text)

    if not match:
        return None

    raw = match.group(1)
    raw = re.sub(r"\.\d{1,2}$", "", raw.strip())
    digits = re.sub(r"[^\d]", "", raw)

    if not digits:
        return None

    try:
        price = int(digits)
    except ValueError:
        return None

    if price < 1_000 or price > 800_000:
        return None

    return price


def _abs_url(url: str | None) -> str:
    if not url:
        return ""

    out = _decode_text(url).strip()

    if out.startswith("//"):
        out = "https:" + out

    if out.startswith("/"):
        out = "https://www.croma.com" + out

    return out


def _first_group(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)

        if not match:
            continue

        for group in match.groups():
            if group:
                return group

    return None


def _price_from_keys(chunk: str, keys: list[str]) -> int | None:
    for key in keys:
        patterns = [
            rf'"{re.escape(key)}"\s*:\s*\{{[^{{}}]{{0,300}}?"value"\s*:\s*"?([^",}}]+)"?',
            rf'"{re.escape(key)}"\s*:\s*"?([^",}}]+)"?',
        ]

        raw = _first_group(patterns, chunk)
        price = _price_to_int(raw)

        if price is not None:
            return price

    return None


def _text_from_keys(chunk: str, keys: list[str]) -> str:
    for key in keys:
        raw = _first_group(
            [rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"'],
            chunk,
        )

        text = _unescape_json_value(raw)

        if text and len(text) > 3:
            return text

    return ""


def _image_from_chunk(chunk: str) -> str:
    match = MEDIA_URL_RE.search(chunk)

    if match:
        return _abs_url(match.group(0))

    raw = _first_group(
        [
            r'"image"\s*:\s*"((?:\\.|[^"\\])*)"',
            r'"imageUrl"\s*:\s*"((?:\\.|[^"\\])*)"',
            r'"url"\s*:\s*"((?:\\.|[^"\\])*)"',
        ],
        chunk,
    )

    img = _unescape_json_value(raw)

    if "media" in img or img.startswith("http"):
        return _abs_url(img)

    return ""


def _discount_from_chunk(chunk: str) -> str | None:
    raw = _first_group(
        [
            r'"discount"\s*:\s*"?([0-9]{1,2}(?:\.\d+)?)"?',
            r'"discountPercentage"\s*:\s*"?([0-9]{1,2}(?:\.\d+)?)"?',
            r"([0-9]{1,2}(?:\.\d+)?)\s*%\s*Off",
        ],
        chunk,
    )

    if not raw:
        return None

    try:
        value = float(raw)
    except ValueError:
        return None

    if value <= 0 or value > 95:
        return None

    if value.is_integer():
        return f"{int(value)}%"

    return f"{value:.2f}%"


def _merge_unique_records(
    records: list[dict[str, Any]],
    max_items: int | None = None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in records:
        link = item.get("link") or ""
        title = item.get("title") or ""
        key = link or title.lower()

        if not key or key in seen:
            continue

        seen.add(key)
        merged.append(item)

        if max_items and len(merged) >= max_items:
            break

    return merged


def extract_croma_initial_data_records(
    html: str | None,
    *,
    max_items: int | None = None,
) -> list[dict[str, Any]]:
    text = _decode_text(html)

    if not text:
        return []

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for match in PRODUCT_URL_RE.finditer(text):
        product_id = match.group("id")

        if product_id in seen_ids:
            continue

        seen_ids.add(product_id)

        start = max(0, match.start() - 5_000)
        end = min(len(text), match.end() + 5_000)
        chunk = text[start:end]

        code_idx = text.find(f'"code":"{product_id}"')

        if code_idx == -1:
            code_idx = text.find(f'"productCode":"{product_id}"')

        if code_idx == -1:
            code_idx = text.find(product_id)

        if code_idx != -1:
            c_start = max(0, code_idx - 5_000)
            c_end = min(len(text), code_idx + 5_000)
            chunk = chunk + " " + text[c_start:c_end]

        title = _text_from_keys(
            chunk,
            [
                "name",
                "title",
                "productName",
                "metatitle",
                "metaalttag",
                "summary",
            ],
        )

        if not title or len(title) < 8:
            continue

        if title.lower() in {"products", "laptops", "computers & tablets"}:
            continue

        current_price = _price_from_keys(
            chunk,
            [
                "sellingPrice",
                "price",
                "offerPrice",
                "finalPrice",
                "discountedPrice",
                "payableAmount",
                "amount",
            ],
        )

        mrp = _price_from_keys(
            chunk,
            [
                "mrp",
                "wasPrice",
                "oldPrice",
                "listPrice",
                "maxRetailPrice",
                "originalPrice",
                "strikePrice",
            ],
        )

        if current_price is not None and mrp is not None and current_price >= mrp:
            current_price = None

        if current_price is None:
            prices = [_price_to_int(x) for x in PRICE_TEXT_RE.findall(chunk)]
            prices = [p for p in prices if p is not None and 1_000 <= p <= 800_000]

            if prices:
                current_price = min(prices)

        link = _abs_url(match.group("url"))
        image = _image_from_chunk(chunk)
        discount = _discount_from_chunk(chunk)

        rows.append(
            {
                "title": title,
                "currentPrice": f"₹{current_price:,}" if current_price is not None else "N/A",
                "maxRetailPrice": f"₹{mrp:,}" if mrp is not None else "N/A",
                "discount": discount,
                "link": link,
                "image": image,
                "native_id": product_id,
                "extraction_method": "croma_initial_data",
            }
        )

        if max_items and len(rows) >= max_items:
            break

    return _merge_unique_records(rows, max_items=max_items)


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


async def dismiss_popups(page) -> None:
    for selector in POPUP_SELECTORS:
        try:
            btn = await page.query_selector(selector)

            if btn:
                await btn.click(timeout=1200)
                await asyncio.sleep(0.25)

        except Exception:
            continue


async def click_view_more(page, max_clicks: int = 20) -> None:
    clicks = 0

    while clicks < max_clicks:
        selector = await first_existing_selector(page, VIEW_MORE_SELECTORS)

        if not selector:
            break

        try:
            btn = await page.query_selector(selector)

            if not btn:
                break

            await btn.scroll_into_view_if_needed()
            await btn.click()

            clicks += 1
            await asyncio.sleep(1.2)

        except Exception:
            break


async def _wait_for_croma_search_render(page: Any, max_wait_ms: int = 30_000) -> None:
    loops = max(1, int(max_wait_ms / 1200))

    for _ in range(loops):
        selector = await first_existing_selector(page, CARD_SELECTORS)

        if selector:
            return

        try:
            html = await page.content()

            if len(PRODUCT_URL_RE.findall(_decode_text(html))) >= 3:
                return

        except Exception:
            pass

        try:
            await page.mouse.wheel(0, 650)

        except Exception:
            pass

        await page.wait_for_timeout(1200)


async def extract_card(card: Any) -> dict[str, Any] | None:
    title = await text_or_none(card, TITLE_SELECTORS)
    raw_link = await attr_or_none(card, LINK_SELECTORS, ["href"])
    link = _abs_url(raw_link or "")

    price = await text_or_none(card, PRICE_SELECTORS)
    mrp = await text_or_none(card, MRP_SELECTORS)
    discount = await text_or_none(card, DISCOUNT_SELECTORS)
    image = await attr_or_none(card, IMAGE_SELECTORS, ["src", "data-src", "srcset"])

    if image and " " in image and "," in image:
        image = image.split(",", 1)[0].strip().split(" ", 1)[0]

    if not title or not link:
        return None

    return {
        "title": title,
        "currentPrice": price or "N/A",
        "maxRetailPrice": mrp or "N/A",
        "discount": discount or None,
        "link": link,
        "image": _abs_url(image or ""),
    }


async def _extract_headless_fallback_records(
    page: Any,
    query: str,
    config: ScrapeConfig,
) -> list[dict[str, Any]]:
    try:
        html = await page.content()

    except Exception:
        html = ""

    records = extract_croma_initial_data_records(
        html,
        max_items=config.max_products or 120,
    )

    if records:
        if config.debug:
            print(f"[croma] initial-data fallback recovered {len(records)} raw cards")

        return records

    records = await extract_structural_discovery_records(
        page,
        PLATFORM,
        query,
        max_items=config.max_products or 120,
    )

    if records:
        if config.debug:
            print(f"[croma] structural fallback recovered {len(records)} raw cards")

        return records

    return await recover_cards_when_empty(
        page,
        PLATFORM,
        query,
        config,
        reason="no_selector",
    )


async def scrape_croma(
    query: str,
    max_products: int | None = None,
    max_pages: int | None = 1,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
    max_clicks: int | None = None,
) -> list[dict[str, Any]]:
    click_budget = max_clicks if max_clicks is not None else (max_pages or 5)

    config = ScrapeConfig(
        query=query,
        max_products=max_products,
        max_pages=click_budget,
        output=output,
        headless=headless,
        debug=debug,
        timeout_ms=55_000,
    )

    observed_at = utc_now()
    raw_records: list[dict[str, Any]] = []

    playwright = await async_playwright().start()
    browser = None
    context = None

    try:
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--window-size=1366,768",
        ]

        try:
            browser = await playwright.chromium.launch(
                channel="chrome",
                headless=headless,
                args=launch_args,
            )

        except Exception:
            browser = await playwright.chromium.launch(
                headless=headless,
                args=launch_args,
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

        context.set_default_timeout(config.timeout_ms)
        await _install_croma_stealth(context)

        page = await context.new_page()

        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.croma.com/searchB?q={encoded}%3Arelevance&text={encoded}"

        print(f"[croma] search: {url}")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)

        except Exception as exc:
            print(f"[croma] navigation failed: {exc}")
            return []

        await asyncio.sleep(2.5)
        await close_common_popups(page)
        await dismiss_popups(page)

        try:
            await page.mouse.move(420, 320)
            await page.evaluate("window.scrollTo(0, 500)")

        except Exception:
            pass

        await _wait_for_croma_search_render(page, max_wait_ms=30_000)

        selector = await wait_for_any_selector(page, CARD_SELECTORS, timeout_ms=5_000)

        if not selector:
            print("[croma] no product cards found; trying initial-data/structural fallback")

            raw_records.extend(
                await _extract_headless_fallback_records(page, query, config)
            )

            records = finalize_records(PLATFORM, query, raw_records, observed_at)

            if debug:
                print(
                    f"[croma] health: "
                    f"{discovery_health_report(records, min_products=min(10, max_products or 10))}"
                )

            return await save_or_print(config, PLATFORM, records, observed_at)

        await human_scroll(page)
        await click_view_more(page, max_clicks=click_budget)
        await human_scroll(page)

        cards = await page.query_selector_all(selector)

        page_added = 0

        for card in cards:
            if max_products and len(raw_records) >= max_products:
                break

            item = await extract_card(card)

            if item:
                raw_records.append(item)
                page_added += 1

        if page_added == 0:
            fallback = await _extract_headless_fallback_records(page, query, config)
            raw_records.extend(fallback)

            if fallback:
                print(f"[croma] fallback recovered {len(fallback)} raw cards")

        if (max_products and len(raw_records) < max_products) or any(
            item.get("currentPrice") in {None, "", "N/A"} for item in raw_records
        ):
            try:
                html = await page.content()

            except Exception:
                html = ""

            ssr_records = extract_croma_initial_data_records(
                html,
                max_items=max_products or 120,
            )

            raw_records = _merge_unique_records(
                raw_records + ssr_records,
                max_items=max_products,
            )

        print(f"[croma] collected {len(raw_records)} raw cards")

    finally:
        if context:
            await context.close()

        if browser:
            await browser.close()

        await playwright.stop()

    records = finalize_records(PLATFORM, query, raw_records, observed_at)
    health = discovery_health_report(records, min_products=min(10, max_products or 10))

    if debug:
        print(f"[croma] health: {health}")

    return await save_or_print(config, PLATFORM, records, observed_at)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu Croma scraper")
    parser.add_argument("query")
    parser.add_argument("--max-products", type=int)
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Backward-compatible alias for max View More clicks on Croma",
    )
    parser.add_argument("--output")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    asyncio.run(
        scrape_croma(
            args.query,
            args.max_products,
            args.max_pages,
            args.output,
            not args.show_browser,
            args.debug,
        )
    )


if __name__ == "__main__":
    main()