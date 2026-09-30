from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mayabu_common import canonical_platform
from mayabu_refresh.models import RefreshResult

PRICE_RE = re.compile(
    r"₹\s?[\d,]+(?:\.\d+)?|rs\.?\s?[\d,]+(?:\.\d+)?|inr\s?[\d,]+(?:\.\d+)?", re.I
)
PLAIN_PRICE_RE = re.compile(r"\b\d{1,3}(?:,\d{2,3})+\b")
PERCENT_RE = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:off|discount)?\b", re.I)

DEFAULT_USER_AGENT = os.getenv("MAYABU_DEFAULT_USER_AGENT") or (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

from mayabu.platforms.registry import PLATFORM_HOSTS as PLATFORM_DOMAINS

BAD_PRICE_CONTEXT = (
    "emi",
    "per month",
    "month",
    "bank",
    "offer",
    "cashback",
    "exchange",
    "delivery",
    "fee",
    "protect",
    "promise fee",
    "secure",
    "warranty",
    "coupon",
    "extra",
    "save",
    "upto",
    "up to",
    "minimum",
    "assured",
    "free",
    "buy at",
    "apply offers",
    "unbeatable deal",
    "no cost",
)


def clean_price_to_int(
    value: Any, *, min_value: int = 100, max_value: int = 2_000_000, category: str | None = None
) -> int | None:
    """Convert an Indian retail price string to integer rupees.

    Category-aware bounds reject obvious extraction mistakes without assuming
    laptop-only price ranges for TVs, cameras, appliances, etc.
    """
    if category:
        from mayabu.domain.categories.registry import price_bounds_for

        min_value, max_value = price_bounds_for(category)
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL", "COMPARE"}:
        return None
    match = PRICE_RE.search(text)
    candidate = match.group(0) if match else text
    candidate = re.sub(r"\.\d{1,2}$", "", candidate.strip())
    cleaned = re.sub(r"[^\d]", "", candidate)
    if not cleaned:
        return None
    try:
        price = int(cleaned)
    except ValueError:
        return None
    if price < min_value or price > max_value:
        return None
    return price


def clean_plain_price_to_int(
    value: Any, *, min_value: int = 5_000, max_value: int = 500_000
) -> int | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d]", "", str(value))
    if not cleaned:
        return None
    try:
        price = int(cleaned)
    except ValueError:
        return None
    if price < min_value or price > max_value:
        return None
    return price


def extract_first_price_text(text: str | None) -> str | None:
    if not text:
        return None
    match = PRICE_RE.search(text)
    return match.group(0).strip() if match else None


def calculate_discount_percent(price: int | None, mrp: int | None) -> float | None:
    if not price or not mrp or mrp <= price:
        return None
    pct = round(((mrp - price) / mrp) * 100, 2)
    return pct if 0 < pct <= 95 else None


def extract_discount_percent(text: str | None) -> float | None:
    if not text:
        return None
    values: list[float] = []
    for raw in PERCENT_RE.findall(text):
        try:
            pct = float(raw)
        except ValueError:
            continue
        if 1 <= pct <= 95:
            values.append(pct)
    return max(values) if values else None


def detect_stock_status(text: str | None) -> str:
    """Classify stock from page text. UNKNOWN never becomes OOS from weak signals.

    Prefer mayabu_refresh.stock.classify_stock_text for structured evidence.
    """
    from mayabu_refresh.stock import classify_stock_text

    return classify_stock_text(text, scoped=False).public_stock


def classify_and_apply_stock(result: "RefreshResult", text: str | None, *, scoped: bool = False) -> None:
    """Set stock fields on a RefreshResult from evidence-based classification."""
    from mayabu_refresh.stock import classify_stock_text

    classified = classify_stock_text(text, page_status=result.page_status, scoped=scoped)
    result.stock_status = classified.public_stock  # type: ignore[assignment]
    result.stock_reason = classified.reason
    result.stock_confidence = classified.confidence
    if classified.state == "challenge" and result.page_status not in {"blocked", "captcha"}:
        result.page_status = "captcha"


def validate_platform_url(platform: str, url: str) -> bool:
    platform = canonical_platform(platform)
    host = urlparse(url or "").netloc.lower()
    allowed = PLATFORM_DOMAINS.get(platform, ())
    return bool(host) and any(
        host == domain or host.endswith("." + domain) for domain in allowed
    )


def result_from_values(
    *,
    current_price: int | None,
    mrp: int | None,
    discount_percent: float | None = None,
    warnings: list[str] | None = None,
    raw_price_text: str | None = None,
    raw_mrp_text: str | None = None,
) -> RefreshResult:
    if mrp is not None and current_price is not None and mrp < current_price:
        mrp = None

    calculated_discount = calculate_discount_percent(current_price, mrp)

    # Final rule:
    # If current_price and mrp are both available, always trust calculated discount.
    # This prevents Amazon/other pages from using unrelated body text like 86%.
    if calculated_discount is not None:
        discount = calculated_discount
    else:
        discount = discount_percent

    if discount is not None and not (0 <= discount <= 95):
        discount = None

    out = RefreshResult(
        current_price=current_price,
        mrp=mrp,
        discount_percent=discount,
        page_status="success" if current_price is not None else "partial",
        warnings=list(warnings or []),
        raw_price_text=raw_price_text,
        raw_mrp_text=raw_mrp_text,
    )

    if current_price is None:
        out.warnings.append("missing_current_price")

    return out


def result_from_texts(
    *,
    title: str | None = None,
    price_text: str | None,
    mrp_text: str | None,
    effective_price_text: str | None = None,
    stock_text: str | None = None,
    warnings: list[str] | None = None,
) -> RefreshResult:
    # title/effective/stock arguments are accepted for backward compatibility,
    # but refresh output intentionally remains price-only.
    price = clean_price_to_int(price_text)
    mrp = clean_price_to_int(mrp_text)
    return result_from_values(
        current_price=price,
        mrp=mrp,
        discount_percent=calculate_discount_percent(price, mrp),
        warnings=warnings,
        raw_price_text=price_text,
        raw_mrp_text=mrp_text,
    )


async def maybe_save_debug(
    page: Any, *, prefix: str, debug: bool, artifact_dir: str | Path | None = None
) -> dict[str, str | None]:
    if not debug:
        return {"screenshot_path": None, "html_path": None}
    base = Path(artifact_dir or "artifacts/debug")
    base.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", prefix)[:80]
    screenshot_path = base / f"{safe_prefix}.png"
    html_path = base / f"{safe_prefix}.html"
    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        screenshot_path = None
    try:
        content = await page.content()
        html_path.write_text(content, encoding="utf-8")
    except Exception:
        html_path = None
    return {
        "screenshot_path": str(screenshot_path) if screenshot_path else None,
        "html_path": str(html_path) if html_path else None,
    }


async def close_common_popups(page: Any) -> None:
    try:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(250)
    except Exception:
        pass
    for text in ["Close", "close", "×", "✕", "No thanks", "Not Now", "Cancel"]:
        try:
            loc = page.get_by_text(text, exact=True).first
            if await loc.count():
                await loc.click(timeout=800)
                await page.wait_for_timeout(250)
                return
        except Exception:
            continue


async def extract_visible_price_candidates(page: Any) -> list[dict[str, Any]]:
    """Selectorless price extraction from visible DOM text."""
    try:
        rows = await page.evaluate(
            r"""() => {
              const priceRx = /(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?/i;
              const out = [];
              function isVisible(el) {
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' &&
                       s.visibility !== 'hidden' && Number(s.opacity || '1') !== 0;
              }
              function ownText(el) {
                let own = '';
                for (const n of Array.from(el.childNodes || [])) {
                  if (n.nodeType === Node.TEXT_NODE) own += ' ' + (n.textContent || '');
                }
                own = own.replace(/\s+/g, ' ').trim();
                return own || ((el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim());
              }
              function context(el) {
                let ctx = '';
                let cur = el;
                for (let i = 0; i < 3 && cur; i++) {
                  ctx += ' ' + ((cur.innerText || cur.textContent || '').replace(/\s+/g, ' ').trim()).slice(0, 360);
                  cur = cur.parentElement;
                }
                return ctx.trim();
              }
              for (const el of Array.from(document.querySelectorAll('body *'))) {
                if (!isVisible(el)) continue;
                const text = ownText(el);
                if (!text || !priceRx.test(text)) continue;
                if (text.length > 190) continue;
                const matches = text.match(new RegExp(priceRx, 'gi')) || [];
                if (matches.length > 2) continue;
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                out.push({
                  text,
                  price_text: matches[0],
                  context: context(el),
                  x: r.x,
                  y: r.y,
                  width: r.width,
                  height: r.height,
                  font_size: parseFloat(s.fontSize || '0'),
                  font_weight: s.fontWeight || '',
                  text_decoration: s.textDecorationLine || ''
                });
              }
              return out;
            }"""
        )
    except Exception:
        return []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


@dataclass(frozen=True, slots=True)
class _VisiblePriceCandidate:
    price: int
    is_struck: bool
    bad_context: bool
    score: float
    text: str
    context: str
    y: float


def _parse_visible_price_candidates(
    candidates: list[dict[str, Any]],
) -> list[_VisiblePriceCandidate]:
    parsed: list[_VisiblePriceCandidate] = []
    for item in candidates:
        text = str(item.get("text") or "")
        price = clean_price_to_int(item.get("price_text") or text)
        if price is None:
            continue

        lower = text.lower()
        context = str(item.get("context") or "").lower()
        is_struck = "line-through" in str(item.get("text_decoration") or "").lower()
        bad_context = any(
            word in lower or word in context for word in BAD_PRICE_CONTEXT
        )
        font_size = float(item.get("font_size") or 0)
        y = float(item.get("y") or 99_999)
        width = float(item.get("width") or 0)
        height = float(item.get("height") or 0)

        raw_weight = str(item.get("font_weight") or "400")
        try:
            weight = int(raw_weight)
        except ValueError:
            weight = 700 if "bold" in raw_weight.lower() else 400

        score = (
            font_size * 10
            + weight / 20
            + min(width, 320) / 20
            + min(height, 80) / 10
            - y / 220
        )
        if bad_context:
            score -= 180
        if is_struck:
            score -= 220

        parsed.append(
            _VisiblePriceCandidate(
                price=price,
                is_struck=is_struck,
                bad_context=bad_context,
                score=score,
                text=text,
                context=context,
                y=y,
            )
        )
    return parsed


def _select_current_price(
    parsed: list[_VisiblePriceCandidate],
) -> _VisiblePriceCandidate | None:
    preferred = [
        item
        for item in parsed
        if not item.is_struck and not item.bad_context and item.price >= 10_000
    ]
    fallback = preferred or [
        item for item in parsed if not item.is_struck and item.price >= 10_000
    ]
    return max(fallback, key=lambda item: item.score, default=None)


def _infer_mrp_from_discount(price: int, discount: float | None) -> int | None:
    if discount is None or not 0 < discount < 95:
        return None
    inferred = price / (1 - discount / 100.0)
    if inferred <= price or not 5_000 <= inferred <= 500_000:
        return None
    return int(round(inferred / 10) * 10)


def _select_mrp(
    parsed: list[_VisiblePriceCandidate],
    main: _VisiblePriceCandidate,
    nearby_text: str,
    inferred_mrp: int | None,
) -> int | None:
    # price -> (source, score); one bounded map replaces candidate-list + dedupe passes.
    candidates: dict[int, tuple[str, float]] = {}

    def add(price: int, source: str, score: float) -> None:
        if price <= main.price or price > main.price * 3.5:
            return
        previous = candidates.get(price)
        if previous is None or score > previous[1]:
            candidates[price] = (source, score)

    for item in parsed:
        if item.is_struck and not item.bad_context:
            add(item.price, "struck", 1_000 - abs(item.y - main.y) / 40)

    for raw in PLAIN_PRICE_RE.findall(nearby_text):
        value = clean_plain_price_to_int(raw)
        if value is not None:
            add(value, "nearby_plain", 700)

    if not candidates:
        return inferred_mrp

    if inferred_mrp is not None:
        closest_price = min(
            candidates,
            key=lambda price: (
                abs(price - inferred_mrp),
                -candidates[price][1],
            ),
        )
        if abs(closest_price - inferred_mrp) <= max(1_500, inferred_mrp * 0.08):
            return closest_price

    struck = [price for price, (source, _) in candidates.items() if source == "struck"]
    return max(struck or candidates.keys())


def classify_visible_prices(
    candidates: list[dict[str, Any]], *, page_text: str | None = None
) -> tuple[int | None, int | None, float | None]:
    parsed = _parse_visible_price_candidates(candidates)
    main = _select_current_price(parsed)
    if main is None:
        return None, None, extract_discount_percent(page_text)

    nearby_text = f"{main.text}\n{main.context}"
    visible_discount = extract_discount_percent(nearby_text)
    if visible_discount is None:
        visible_discount = extract_discount_percent(page_text)

    inferred_mrp = _infer_mrp_from_discount(main.price, visible_discount)
    mrp = _select_mrp(parsed, main, nearby_text, inferred_mrp)
    discount = visible_discount or calculate_discount_percent(main.price, mrp)
    return main.price, mrp, discount


async def extract_price_refresh_by_visible_text(page: Any) -> RefreshResult:
    candidates = await extract_visible_price_candidates(page)
    try:
        body_text = await page.locator("body").inner_text(timeout=1500)
    except Exception:
        body_text = None
    current_price, mrp, discount = classify_visible_prices(
        candidates, page_text=body_text
    )
    return result_from_values(
        current_price=current_price, mrp=mrp, discount_percent=discount
    )


def refresh_health_report(result: RefreshResult) -> dict[str, Any]:
    reasons: list[str] = []
    if result.current_price is None:
        reasons.append("missing_current_price")
    elif result.current_price < 5_000 or result.current_price > 500_000:
        reasons.append("invalid_current_price_range")
    if (
        result.mrp is not None
        and result.current_price is not None
        and result.mrp < result.current_price
    ):
        reasons.append("mrp_below_current_price")
    if result.discount_percent is not None and not (0 <= result.discount_percent <= 95):
        reasons.append("invalid_discount_percent")
    status = "healthy" if not reasons else "failed"
    return {"status": status, "reasons": reasons, **result.as_dict()}
