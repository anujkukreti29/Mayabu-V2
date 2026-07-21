"""Reusable Playwright scraping base for Mayabu.

This module intentionally avoids stealth/bypass tricks. Use it with respectful
rate limits and only where scraping is allowed by the platform's terms/robots.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from mayabu_common import (
    canonical_platform,
    compact_space,
    detect_category,
    extract_native_id,
    listing_id,
    normalize_raw_listing,
    normalize_url,
    parse_price,
    product_source_id,
    utc_now,
    write_json,
)

DEFAULT_USER_AGENT = os.getenv("MAYABU_DEFAULT_USER_AGENT") or (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class ScrapeConfig:
    query: str
    max_products: Optional[int] = None
    max_pages: Optional[int] = None
    headless: bool = True
    delay_min: float = 1.0
    delay_max: float = 2.5
    timeout_ms: int = 45_000
    output: Optional[str] = None
    debug: bool = False


class ScrapeError(RuntimeError):
    pass


class BrowserSession:
    def __init__(self, headless: bool = True, timeout_ms: int = 45_000, proxy: str | None = None) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.proxy = proxy or os.getenv("MAYABU_SCRAPER_PROXY") or None
        self._playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserSession":
        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}
        self.browser = await self._playwright.chromium.launch(**launch_kwargs)
        self.context = await self.browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        self.context.set_default_timeout(self.timeout_ms)
        return self

    async def new_page(self) -> Page:
        if self.context is None:
            raise ScrapeError("Browser context is not ready")
        return await self.context.new_page()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()


async def polite_sleep(config: ScrapeConfig, multiplier: float = 1.0) -> None:
    if random.random() < 0.15:
        await asyncio.sleep(random.uniform(4.0, 12.0) * multiplier)
    else:
        await asyncio.sleep(random.uniform(config.delay_min, config.delay_max) * multiplier)


async def text_or_none(root: Any, selectors: list[str]) -> Optional[str]:
    for selector in selectors:
        try:
            el = await root.query_selector(selector)
            if el:
                value = (await el.inner_text()).strip()
                if value:
                    return value
        except Exception:
            continue
    return None


async def attr_or_none(root: Any, selectors: list[str], attrs: list[str]) -> Optional[str]:
    for selector in selectors:
        try:
            el = await root.query_selector(selector)
            if not el:
                continue
            for attr in attrs:
                value = await el.get_attribute(attr)
                if value:
                    return value
        except Exception:
            continue
    return None


async def first_existing_selector(page: Page, selectors: list[str], min_count: int = 1) -> Optional[str]:
    for selector in selectors:
        try:
            els = await page.query_selector_all(selector)
            if len(els) >= min_count:
                return selector
        except Exception:
            continue
    return None


async def wait_for_any_selector(page: Page, selectors: list[str], timeout_ms: int = 15_000) -> Optional[str]:
    deadline = timeout_ms / 1000
    interval = 0.5
    waited = 0.0
    while waited < deadline:
        found = await first_existing_selector(page, selectors)
        if found:
            return found
        await asyncio.sleep(interval)
        waited += interval
    return None


async def human_scroll(page: Page, steps: int = 5) -> bool:
    try:
        height = await page.evaluate("document.body.scrollHeight")
        for i in range(1, steps + 1):
            await page.evaluate(f"window.scrollTo(0, {int(height * i / steps)})")
            await asyncio.sleep(random.uniform(0.15, 0.35))
        return True
    except Exception as exc:
        message = str(exc).lower()
        if "target closed" in message or "context" in message or "browser has been closed" in message:
            raise
        return False


def finalize_records(
    platform: str,
    query: str,
    records: list[dict[str, Any]],
    observed_at: str,
) -> list[dict[str, Any]]:
    prefix, _category = detect_category(query)
    clean_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    fallback_counter = 0
    for raw in records:
        url = raw.get("link") or raw.get("url") or ""
        native = raw.get("native_id") or extract_native_id(platform, url, raw.get("productId"))
        fallback_counter += 1
        raw["native_id"] = native
        raw["listing_id"] = listing_id(platform, native, url, raw.get("title") or "")
        raw["productId"] = product_source_id(prefix, platform, native, fallback_counter)
        normalized = normalize_raw_listing(raw, platform_hint=platform, query=query, observed_at=observed_at)
        if not normalized:
            continue
        lid = normalized["listing_id"]
        if lid in seen:
            continue
        seen.add(lid)
        # Preserve legacy fields while also giving typed fields to the merger.
        clean_records.append({
            "source": platform,
            "platform": platform,
            "productId": raw["productId"],
            "native_id": normalized["native_id"],
            "listing_id": normalized["listing_id"],
            "query": query,
            "category": normalized["category"],
            "title": normalized["title"],
            "currentPrice": raw.get("currentPrice") or normalized["price"],
            "maxRetailPrice": raw.get("maxRetailPrice") or normalized["mrp"],
            "price": normalized["price"],
            "mrp": normalized["mrp"],
            "discount": raw.get("discount"),
            "discount_pct": normalized["discount_pct"],
            "currency": normalized.get("currency") or "INR",
            "link": normalized["url"],
            "image": normalized["image"],
            "scraped_at": observed_at,
            "specs": normalized["specs"],
        })
    return clean_records


def save_scrape_output(path: str | Path, platform: str, query: str, records: list[dict[str, Any]], observed_at: str) -> None:
    payload = {
        "schema_version": "mayabu.raw_listings.v2",
        "platform": platform,
        "query": query,
        "scraped_at": observed_at,
        "count": len(records),
        "records": records,
    }
    write_json(path, payload)


def default_output_path(platform: str, query: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in query.lower()).strip("_") or "query"
    return f"{safe}_{platform}.json"


async def save_or_print(config: ScrapeConfig, platform: str, records: list[dict[str, Any]], observed_at: str) -> list[dict[str, Any]]:
    if config.output:
        save_scrape_output(config.output, platform, config.query, records, observed_at)
        print(f"[{platform}] saved {len(records)} records -> {config.output}")
    return records


async def capture_debug_artifacts(page: Page, platform: str, query: str, reason: str, out_dir: str | Path = "artifacts/debug") -> dict[str, str]:
    """Capture HTML and screenshot when extraction fails.

    This is not a bypass technique. It is for maintainability: when a selector
    breaks or a platform returns an empty/CAPTCHA page, developers can inspect
    exactly what the scraper saw.
    """
    safe_query = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (query or "query").lower()).strip("_") or "query"
    safe_reason = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (reason or "debug").lower()).strip("_") or "debug"
    stamp = utc_now().replace(":", "").replace("+", "_")
    base = Path(out_dir) / platform
    base.mkdir(parents=True, exist_ok=True)
    html_path = base / f"{safe_query}_{safe_reason}_{stamp}.html"
    screenshot_path = base / f"{safe_query}_{safe_reason}_{stamp}.png"
    result: dict[str, str] = {}
    try:
        html_path.write_text(await page.content(), encoding="utf-8")
        result["html_path"] = str(html_path)
    except Exception:
        pass
    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
        result["screenshot_path"] = str(screenshot_path)
    except Exception:
        pass
    return result


def _candidate_link_pattern(platform: str) -> str:
    platform = platform.lower()
    if platform == "amazon":
        return r"/dp/[A-Za-z0-9]{10}|/gp/product/[A-Za-z0-9]{10}"
    if platform == "flipkart":
        return r"/p/|pid="
    if platform == "croma":
        return r"/p/\d{4,12}"
    if platform == "reliancedigital":
        return r"/p/|/product/"
    return r"/p/|/dp/|pid="


async def extract_dom_product_candidates(page: Page, platform: str, max_items: int = 120) -> list[dict[str, Any]]:
    """Fallback extraction from DOM anchors when CSS card selectors fail.

    It intentionally uses generic DOM structure instead of brittle class names.
    This is useful when ecommerce CSS classes change. It may return noisier data,
    so the DB quality layer still validates every record.
    """
    pattern = _candidate_link_pattern(platform)
    try:
        candidates = await page.evaluate(
            """({pattern, maxItems}) => {
                const rx = new RegExp(pattern, 'i');
                const priceRx = /(₹|Rs\\.?|INR)\\s*[0-9][0-9,.]*/i;
                const rows = [];
                const seen = new Set();
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                for (const a of anchors) {
                    if (rows.length >= maxItems) break;
                    const href = a.href || a.getAttribute('href') || '';
                    if (!rx.test(href) || seen.has(href)) continue;
                    let node = a;
                    let text = '';
                    for (let i = 0; i < 4 && node; i++) {
                        text = (node.innerText || '').trim();
                        if (text && priceRx.test(text) && text.length > 20) break;
                        node = node.parentElement;
                    }
                    const aria = a.getAttribute('aria-label') || a.getAttribute('title') || '';
                    const lines = (text || aria || a.innerText || '').split('\n').map(x => x.trim()).filter(Boolean);
                    let title = aria || lines.find(x => !priceRx.test(x) && x.length > 8) || a.innerText || '';
                    title = title.replace(/\\s+/g, ' ').trim();
                    if (!title) continue;
                    let rawPrice = (text.match(priceRx) || [''])[0];
                    let price = rawPrice.replace(/[₹Rs.,\\s]/gi, '').trim();
                    let img = '';
                    const root = node || a.parentElement || a;
                    const image = root.querySelector ? root.querySelector('img[src],img[data-src]') : null;
                    if (image) img = image.getAttribute('src') || image.getAttribute('data-src') || '';
                    seen.add(href);
                    rows.push({ title, currentPrice: price || 'N/A', maxRetailPrice: 'N/A', discount: null, link: href, image: img, extraction_method: 'dom_fallback' });
                }
                return rows;
            }""",
            {"pattern": pattern, "maxItems": max_items},
        )
        if isinstance(candidates, list):
            return [c for c in candidates if isinstance(c, dict)]
    except Exception:
        return []
    return []


async def recover_cards_when_empty(
    page: Page,
    platform: str,
    query: str,
    config: ScrapeConfig,
    reason: str = "empty_cards",
) -> list[dict[str, Any]]:
    """Try a second extraction path and capture diagnostics if still empty."""
    try:
        await page.wait_for_load_state("networkidle", timeout=min(config.timeout_ms, 15_000))
    except Exception:
        pass
    await human_scroll(page, steps=7)
    fallback = await extract_dom_product_candidates(page, platform, max_items=config.max_products or 120)
    if not fallback:
        artifacts = await capture_debug_artifacts(page, platform, query, reason)
        if config.debug:
            print(f"[{platform}] debug artifacts: {artifacts}")
    return fallback


# ---------------------------------------------------------------------------
# Mayabu v4.3 structural discovery extraction
# ---------------------------------------------------------------------------
# This layer avoids depending on generated frontend CSS classes.  It looks for
# stable ecommerce structure instead: product URLs, visible card text, INR price
# patterns, images inside the same card, line-through/nearby larger prices, and
# sanity checks.  Platform scrapers can still keep their old selectors as a
# last-resort fallback, but generated classes should not be the primary signal.

PRICE_TEXT_RE = re.compile(r"(?:₹|rs\.?|inr)\s*[\d,]+(?:\.\d+)?", re.I)
PLAIN_PRICE_TEXT_RE = re.compile(r"\b\d{1,3}(?:,\d{2,3})+\b")
DISCOUNT_TEXT_RE = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:off|discount)?\b", re.I)

BAD_PRICE_CONTEXT = (
    "emi", "per month", "month", "bank", "offer", "cashback", "exchange",
    "delivery", "fee", "protect", "promise fee", "secure", "warranty",
    "coupon", "extra", "save", "upto", "up to", "minimum", "assured",
    "free", "buy at", "apply offers", "unbeatable deal", "no cost",
)

TITLE_BAD_TERMS = (
    "sponsored", "only few left", "bank offer", "exchange", "emi", "free delivery",
    "add to compare", "ratings", "reviews", "off", "₹", "rs.", "inr",
)

TITLE_POSITIVE_HINTS = (
    "laptop", "notebook", "macbook", "chromebook", "intel", "ryzen", "core i3",
    "core i5", "core i7", "core i9", "ssd", "windows", "gaming", "lenovo",
    "hp", "dell", "asus", "acer", "samsung", "apple", "msi", "infinix",
)

PLATFORM_LINK_PATTERNS = {
    "amazon": r"/(?:dp|gp/product)/[A-Za-z0-9]{10}|/sspa/click|/gp/slredirect",
    "flipkart": r"/p/|pid=",
    "croma": r"/p/\d{4,12}|/p/",
    "reliancedigital": r"/p/|/product/|/products/",
}

PLATFORM_BASE_URLS = {
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "croma": "https://www.croma.com",
    "reliancedigital": "https://www.reliancedigital.in",
}


def price_text_to_int(value: Any, *, min_value: int = 5_000, max_value: int = 500_000) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL", "COMPARE"}:
        return None
    match = PRICE_TEXT_RE.search(text)
    candidate = match.group(0) if match else text
    candidate = re.sub(r"\.\d{1,2}$", "", candidate.strip())
    digits = re.sub(r"[^\d]", "", candidate)
    if not digits:
        return None
    try:
        parsed = int(digits)
    except ValueError:
        return None
    if parsed < min_value or parsed > max_value:
        return None
    return parsed


def plain_price_text_to_int(value: Any, *, min_value: int = 5_000, max_value: int = 500_000) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        return None
    try:
        parsed = int(digits)
    except ValueError:
        return None
    if parsed < min_value or parsed > max_value:
        return None
    return parsed


def discount_from_text(value: str | None) -> float | None:
    if not value:
        return None
    values: list[float] = []
    for raw in DISCOUNT_TEXT_RE.findall(value):
        try:
            pct = float(raw)
        except ValueError:
            continue
        if 1 <= pct <= 95:
            values.append(pct)
    return max(values) if values else None


def discount_from_prices(current_price: int | float | None, mrp: int | float | None) -> float | None:
    if not current_price or not mrp:
        return None
    try:
        current = float(current_price)
        old = float(mrp)
    except (TypeError, ValueError):
        return None
    if current <= 0 or old <= current:
        return None
    pct = round(((old - current) / old) * 100, 2)
    return pct if 0 < pct <= 95 else None


def _clean_card_title(lines: list[str]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for line in lines:
        line = compact_space(line)
        if not line or len(line) < 18:
            continue
        lower = line.lower()
        if any(term in lower for term in TITLE_BAD_TERMS):
            continue
        alpha_count = sum(ch.isalpha() for ch in line)
        if alpha_count < 8:
            continue
        score = len(line)
        if any(hint in lower for hint in TITLE_POSITIVE_HINTS):
            score += 120
        if re.search(r"\b(?:\d{1,3}\s*gb|\d{3,4}\s*gb|\d+\s*tb|i[3579]|ryzen|ssd|windows)\b", lower):
            score += 40
        candidates.append((score, line))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    title = candidates[0][1]
    if len(title) > 280:
        title = title[:280].rsplit(" ", 1)[0].strip()
    return title


def _classify_structural_card_prices(card: dict[str, Any]) -> tuple[int | None, int | None, float | None]:
    text = str(card.get("text") or "")
    price_nodes = card.get("price_nodes") or []
    parsed_nodes: list[dict[str, Any]] = []

    for node in price_nodes:
        node_text = str(node.get("text") or "")
        price = price_text_to_int(node.get("price_text") or node_text)
        if price is None:
            continue
        lower_text = node_text.lower()
        context = str(node.get("context") or "").lower()
        decoration = str(node.get("text_decoration") or "").lower()
        is_struck = "line-through" in decoration
        bad_context = any(word in lower_text or word in context for word in BAD_PRICE_CONTEXT)
        font_size = float(node.get("font_size") or 0)
        y = float(node.get("y") or 99999)
        width = float(node.get("width") or 0)
        height = float(node.get("height") or 0)
        try:
            weight = int(str(node.get("font_weight") or "400"))
        except ValueError:
            weight = 700 if "bold" in str(node.get("font_weight") or "").lower() else 400
        score = (
            font_size * 10
            + weight / 20
            + min(width, 320) / 20
            + min(height, 80) / 10
            - y / 220
            - (180 if bad_context else 0)
            - (220 if is_struck else 0)
        )
        parsed_nodes.append({"price": price, "is_struck": is_struck, "bad_context": bad_context, "score": score})

    if not parsed_nodes:
        first_text_price = price_text_to_int(text)
        return first_text_price, None, discount_from_text(text)

    current_candidates = [
        p for p in parsed_nodes
        if not p["is_struck"] and not p["bad_context"] and p["price"] >= 10_000
    ]
    if not current_candidates:
        current_candidates = [p for p in parsed_nodes if not p["is_struck"] and p["price"] >= 10_000]
    if not current_candidates:
        return None, None, discount_from_text(text)
    current_candidates.sort(key=lambda p: p["score"], reverse=True)
    current_price = current_candidates[0]["price"]

    mrp_candidates = [
        p["price"] for p in parsed_nodes
        if p["is_struck"] and current_price < p["price"] <= current_price * 2.8
    ]
    mrp = min(mrp_candidates) if mrp_candidates else None

    if mrp is None:
        plain_values: list[int] = []
        for raw in PLAIN_PRICE_TEXT_RE.findall(text):
            value = plain_price_text_to_int(raw)
            if value is not None:
                plain_values.append(value)
        plain_values = [v for v in plain_values if v != current_price and current_price < v <= current_price * 2.8]
        if plain_values:
            mrp = min(plain_values)

    if mrp is None:
        larger_prices = [
            p["price"] for p in parsed_nodes
            if current_price < p["price"] <= current_price * 2.8 and not p["bad_context"]
        ]
        if larger_prices:
            mrp = min(larger_prices)

    discount = discount_from_prices(current_price, mrp) or discount_from_text(text)
    return current_price, mrp, discount


async def close_common_popups(page: Page) -> None:
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.25)
    except Exception:
        pass
    for text in ["Close", "close", "×", "✕", "No thanks", "Not Now", "Cancel"]:
        try:
            locator = page.get_by_text(text, exact=True).first
            if await locator.count():
                await locator.click(timeout=800)
                await asyncio.sleep(0.25)
                return
        except Exception:
            continue


async def extract_structural_product_cards(page: Page, platform: str, *, max_items: int = 160) -> list[dict[str, Any]]:
    platform = canonical_platform(platform)
    pattern = PLATFORM_LINK_PATTERNS.get(platform, r"/p/|/dp/|pid=")
    try:
        cards = await page.evaluate(
            r"""({pattern, maxItems}) => {
              const linkRx = new RegExp(pattern, 'i');
              const priceRx = /(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?/i;
              const rows = [];
              const seen = new Set();

              function isVisible(el) {
                if (!el) return false;
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' &&
                       s.visibility !== 'hidden' && Number(s.opacity || '1') !== 0;
              }

              function normText(el) {
                return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, ' ').trim();
              }

              function ownOrShortText(el) {
                let own = '';
                for (const n of Array.from(el.childNodes || [])) {
                  if (n.nodeType === Node.TEXT_NODE) own += ' ' + (n.textContent || '');
                }
                own = own.replace(/\s+/g, ' ').trim();
                return own || normText(el);
              }

              function findCard(anchor) {
                let cur = anchor;
                let best = null;
                for (let depth = 0; depth < 9 && cur; depth++) {
                  const text = normText(cur);
                  const r = cur.getBoundingClientRect();
                  const area = r.width * r.height;
                  const hasPrice = priceRx.test(text);
                  const hasImage = !!cur.querySelector('img');
                  if (hasPrice && hasImage && r.width >= 160 && r.height >= 100 && area < 900000) {
                    best = cur;
                    break;
                  }
                  cur = cur.parentElement;
                }
                return best || anchor;
              }

              function nearestContext(el) {
                let ctx = '';
                let cur = el;
                for (let i = 0; i < 3 && cur; i++) {
                  ctx += ' ' + normText(cur).slice(0, 320);
                  cur = cur.parentElement;
                }
                return ctx.trim();
              }

              const anchors = Array.from(document.querySelectorAll('a[href]'));
              for (const a of anchors) {
                if (rows.length >= maxItems) break;
                const href = a.href || a.getAttribute('href') || '';
                if (!href || !linkRx.test(href) || seen.has(href)) continue;
                if (!isVisible(a)) continue;
                const card = findCard(a);
                if (!card || !isVisible(card)) continue;
                const cardText = (card.innerText || card.textContent || '').trim();
                if (!priceRx.test(cardText)) continue;
                const r = card.getBoundingClientRect();

                const images = Array.from(card.querySelectorAll('img')).map(img => {
                  const ir = img.getBoundingClientRect();
                  return {
                    src: img.currentSrc || img.src || img.getAttribute('data-src') || img.getAttribute('data-original') || '',
                    width: ir.width,
                    height: ir.height,
                    area: ir.width * ir.height,
                    x: ir.x,
                    y: ir.y
                  };
                }).filter(img => img.src && img.width > 35 && img.height > 35).sort((a, b) => b.area - a.area);

                const priceNodes = [];
                for (const el of Array.from(card.querySelectorAll('*'))) {
                  if (!isVisible(el)) continue;
                  const text = ownOrShortText(el);
                  if (!text || !priceRx.test(text)) continue;
                  if (text.length > 170) continue;
                  const matches = text.match(new RegExp(priceRx, 'gi')) || [];
                  if (matches.length > 2) continue;
                  const er = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  priceNodes.push({
                    text,
                    price_text: matches[0],
                    context: nearestContext(el),
                    x: er.x,
                    y: er.y,
                    width: er.width,
                    height: er.height,
                    font_size: parseFloat(style.fontSize || '0'),
                    font_weight: style.fontWeight || '',
                    text_decoration: style.textDecorationLine || ''
                  });
                }

                seen.add(href);
                rows.push({
                  href,
                  anchor_text: (a.innerText || a.textContent || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim(),
                  text: cardText,
                  image_url: images.length ? images[0].src : '',
                  rect: {x: r.x, y: r.y, width: r.width, height: r.height},
                  price_nodes: priceNodes
                });
              }
              return rows;
            }""",
            {"pattern": pattern, "maxItems": max_items},
        )
    except Exception:
        return []
    return [row for row in cards if isinstance(row, dict)] if isinstance(cards, list) else []


def structural_cards_to_raw_records(platform: str, query: str, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    platform = canonical_platform(platform)
    raw_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    base_url = PLATFORM_BASE_URLS.get(platform, "")
    for card in cards:
        href = str(card.get("href") or "").strip()
        if not href:
            continue
        link = urllib.parse.urljoin(base_url, href)
        if platform == "amazon":
            # Avoid importing amazon_scraper.clean_amazon_link here to keep this
            # shared base free of platform-module cycles.  This extracts the ASIN
            # from both direct and redirect-style URLs when present.
            decoded = urllib.parse.unquote(link)
            m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?#]|$)", decoded, re.I)
            if m:
                link = f"https://www.amazon.in/dp/{m.group(1).upper()}"
        normalized_key = normalize_url(link)
        if normalized_key in seen:
            continue
        seen.add(normalized_key)

        text = str(card.get("text") or "")
        anchor_text = str(card.get("anchor_text") or "")
        lines = [line.strip() for line in (anchor_text + "\n" + text).splitlines() if line.strip()]
        # If the browser collapsed lines into spaces, split around common price markers too.
        if len(lines) <= 2:
            lines.extend(re.split(r"\s{2,}|(?=₹)|(?=Rs\.?)", anchor_text + " " + text))
        title = _clean_card_title(lines)
        current_price, mrp, discount = _classify_structural_card_prices(card)
        image = str(card.get("image_url") or "").strip()

        if not title or not current_price:
            continue
        raw_records.append({
            "title": title,
            "currentPrice": f"₹{current_price}",
            "maxRetailPrice": f"₹{mrp}" if mrp else "N/A",
            "discount": f"{discount}% off" if discount is not None else None,
            "link": link,
            "image": image,
            "query": query,
            "extraction_method": "structural_text",
        })
    return raw_records


async def extract_structural_discovery_records(
    page: Page,
    platform: str,
    query: str,
    *,
    max_items: int = 160,
) -> list[dict[str, Any]]:
    cards = await extract_structural_product_cards(page, platform, max_items=max_items)
    return structural_cards_to_raw_records(platform, query, cards)


def discovery_health_report(records: list[dict[str, Any]], *, min_products: int = 10) -> dict[str, Any]:
    total = len(records)
    if total == 0:
        return {
            "status": "failed",
            "count": 0,
            "title_rate": 0.0,
            "price_rate": 0.0,
            "image_rate": 0.0,
            "url_rate": 0.0,
            "duplicate_rate": 0.0,
            "reasons": ["no_products_found"],
        }
    titles = sum(1 for r in records if r.get("title"))
    prices = sum(1 for r in records if parse_price(r.get("currentPrice") or r.get("price")) is not None)
    images = sum(1 for r in records if r.get("image") or r.get("image_url"))
    urls = [str(r.get("link") or r.get("url") or r.get("product_url") or "") for r in records]
    valid_urls = sum(1 for u in urls if u.startswith("http"))
    duplicate_rate = 1.0 - (len(set(urls)) / total if total else 0.0)
    title_rate = titles / total
    price_rate = prices / total
    image_rate = images / total
    url_rate = valid_urls / total
    reasons: list[str] = []
    if total < min_products:
        reasons.append("low_product_count")
    if title_rate < 0.90:
        reasons.append("low_title_rate")
    if price_rate < 0.80:
        reasons.append("low_price_rate")
    if image_rate < 0.60:
        reasons.append("low_image_rate")
    if url_rate < 1.0:
        reasons.append("invalid_product_url_rate")
    if duplicate_rate > 0.30:
        reasons.append("high_duplicate_rate")
    status = "healthy" if not reasons else ("failed" if total == 0 or price_rate == 0 else "degraded")
    return {
        "status": status,
        "count": total,
        "title_rate": round(title_rate, 3),
        "price_rate": round(price_rate, 3),
        "image_rate": round(image_rate, 3),
        "url_rate": round(url_rate, 3),
        "duplicate_rate": round(duplicate_rate, 3),
        "reasons": reasons,
    }
