from __future__ import annotations

import argparse
import asyncio
import re
import urllib.parse
from typing import Any

from mayabu_common import utc_now
from mayabu_scraper_base import (
    BrowserSession,
    ScrapeConfig,
    attr_or_none,
    finalize_records,
    human_scroll,
    polite_sleep,
    recover_cards_when_empty,
    close_common_popups,
    discovery_health_report,
    extract_structural_discovery_records,
    save_or_print,
    text_or_none,
    wait_for_any_selector,
)

PLATFORM = "amazon"
CARD_SELECTORS = [
    "div[data-component-type='s-search-result']",
    "div[role='listitem'] div.sg-col-inner",
]
TITLE_SELECTORS = ["h2 span", "h2", "span.a-size-medium", "span.a-size-base-plus"]
PRICE_SELECTORS = ["span.a-price span.a-offscreen", "span.a-price-whole"]
MRP_SELECTORS = ["span.a-text-price span.a-offscreen", "span[data-a-strike='true'] span.a-offscreen"]
LINK_SELECTORS = ["a[href*='/dp/']", "h2 a", "a.a-link-normal.s-no-outline", "a[href*='url=']"]
IMAGE_SELECTORS = ["img.s-image", "img[src]"]


ASIN_PATH_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?#]|$)", re.I)


def _canonical_amazon_dp_url(value: str | None) -> str | None:
    """Extract a canonical amazon.in /dp/ URL from direct or decoded text."""
    if not value:
        return None
    match = ASIN_PATH_RE.search(value)
    if not match:
        return None
    return f"https://www.amazon.in/dp/{match.group(1).upper()}"


def clean_amazon_link(raw_link: str | None) -> str:
    """Canonicalize Amazon result links, including nested sponsored redirects.

    Amazon search often wraps product cards in /sspa/click? redirects where the
    real /dp/<ASIN> URL is one or more URL-decoding layers deep. We only decode
    and canonicalize the public product URL; no request is made to follow the
    redirect.
    """
    if not raw_link:
        return ""

    link = raw_link.strip()
    if link.startswith("/"):
        link = "https://www.amazon.in" + link

    seen: set[str] = set()
    candidates: list[str] = [link]

    for _ in range(4):
        next_candidates: list[str] = []
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)

            canonical = _canonical_amazon_dp_url(candidate)
            if canonical:
                return canonical

            parsed = urllib.parse.urlparse(candidate)
            for values in urllib.parse.parse_qs(parsed.query).values():
                for value in values:
                    if value:
                        next_candidates.append(value)

            decoded = urllib.parse.unquote(candidate)
            if decoded and decoded != candidate:
                next_candidates.append(decoded)

        if not next_candidates:
            break
        candidates = next_candidates

    return link


async def extract_card(card: Any) -> dict[str, Any] | None:
    title = await text_or_none(card, TITLE_SELECTORS)
    raw_link = await attr_or_none(card, LINK_SELECTORS, ["href"])
    link = clean_amazon_link(raw_link)
    price = await text_or_none(card, PRICE_SELECTORS)
    mrp = await text_or_none(card, MRP_SELECTORS)
    image = await attr_or_none(card, IMAGE_SELECTORS, ["src", "data-src"])
    if not title or not link:
        return None
    return {
        "title": title,
        "currentPrice": price or "N/A",
        "maxRetailPrice": mrp or "N/A",
        "discount": None,
        "link": link,
        "image": image or "",
    }


async def scrape_amazon(
    query: str,
    max_products: int | None = None,
    max_pages: int | None = 3,
    output: str | None = None,
    headless: bool = True,
    debug: bool = False,
    start_page: int = 1,
) -> list[dict[str, Any]]:
    config = ScrapeConfig(query=query, max_products=max_products, max_pages=max_pages, output=output, headless=headless, debug=debug)
    observed_at = utc_now()
    raw_records: list[dict[str, Any]] = []

    async with BrowserSession(headless=headless, timeout_ms=config.timeout_ms) as session:
        page = await session.new_page()
        encoded = urllib.parse.quote_plus(query)
        total_pages = max_pages or 1
        first_page = max(1, int(start_page or 1))
        for page_no in range(first_page, first_page + total_pages):
            if max_products and len(raw_records) >= max_products:
                break
            url = f"https://www.amazon.in/s?k={encoded}&page={page_no}"
            print(f"[amazon] page {page_no}: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            except Exception as exc:
                print(f"[amazon] navigation failed on page {page_no}: {exc}")
                break
            await close_common_popups(page)
            selector = await wait_for_any_selector(page, CARD_SELECTORS, timeout_ms=20_000)
            if not selector:
                print("[amazon] no product cards found; trying structural fallback")
                fallback = await extract_structural_discovery_records(page, PLATFORM, query, max_items=max_products or 120)
                if not fallback:
                    fallback = await recover_cards_when_empty(page, PLATFORM, query, config, reason="no_selector")
                raw_records.extend(fallback)
                if fallback:
                    print(f"[amazon] structural/DOM fallback recovered {len(fallback)} raw cards")
                    continue
                print("[amazon] no product cards found after fallback; stopping")
                break
            await human_scroll(page)
            cards = await page.query_selector_all(selector)
            page_added = 0
            for card in cards:
                item = await extract_card(card)
                if not item:
                    continue
                raw_records.append(item)
                page_added += 1
                if max_products and len(raw_records) >= max_products:
                    break
            print(f"[amazon] page {page_no}: +{page_added} raw cards")
            if page_added == 0:
                fallback = await extract_structural_discovery_records(page, PLATFORM, query, max_items=max_products or 120)
                if not fallback:
                    fallback = await recover_cards_when_empty(page, PLATFORM, query, config, reason="zero_cards")
                raw_records.extend(fallback)
                if fallback:
                    print(f"[amazon] structural/DOM fallback recovered {len(fallback)} raw cards")
                else:
                    break
            await polite_sleep(config)

    records = finalize_records(PLATFORM, query, raw_records, observed_at)
    health = discovery_health_report(records, min_products=min(10, max_products or 10))
    if debug:
        print(f"[amazon] health: {health}")
    return await save_or_print(config, PLATFORM, records, observed_at)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mayabu Amazon scraper")
    parser.add_argument("query")
    parser.add_argument("--max-products", type=int)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output")
    parser.add_argument("--show-browser", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    asyncio.run(scrape_amazon(args.query, args.max_products, args.max_pages, args.output, not args.show_browser, args.debug))


if __name__ == "__main__":
    main()
