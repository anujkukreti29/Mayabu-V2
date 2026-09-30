"""Shared Mayabu scraping and catalogue utilities.

Design goals:
- Stable listing identity first: platform:native_id where available.
- Raw observations are never discarded silently.
- No hosted third-party matching APIs. Everything is local Python logic.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from mayabu.platforms.registry import (
    PLATFORMS as _REGISTRY_PLATFORMS,
    canonical_platform_slug,
    product_source_abbrev,
)

PLATFORMS = set(_REGISTRY_PLATFORMS)

CATEGORY_RULES: list[tuple[set[str], str, str]] = [
    ({"laptop", "laptops", "notebook", "notebooks", "ultrabook", "ultrabooks", "chromebook", "macbook"}, "LAP", "laptop"),
    ({"smartphone", "smartphones", "mobile", "mobiles", "phone", "phones", "iphone", "android phone"}, "SMARTPH", "smartphone"),
    ({"tablet", "tablets", "ipad", "android tablet"}, "TAB", "tablet"),
    ({"television", "smart tv", "oled tv", "qled tv", "led tv", "tvs"}, "TV", "television"),
    # Prefer specific audio categories; legacy "audio" remains a compatibility alias.
    ({"tws", "true wireless", "earbuds", "ear buds", "airpods"}, "TWS", "tws"),
    ({"headphone", "headphones", "over ear", "on ear", "wired headset", "wireless headphone", "earphone", "earphones", "neckband"}, "AUDIO", "headphones"),
    ({"camera", "cameras", "dslr", "mirrorless", "action camera"}, "CAM", "camera"),
    ({"refrigerator", "refrigerators", "fridge", "fridges"}, "FRIDGE", "refrigerator"),
    ({"washing machine", "washing machines", "washer", "front load", "top load"}, "WASH", "washing_machine"),
    ({"air conditioner", "air conditioners", "split ac", "window ac"}, "AC", "air_conditioner"),
    ({"microwave", "microwave oven"}, "MICRO", "microwave"),
    ({"printer", "printers", "inkjet", "laser printer"}, "PRINT", "printer"),
    ({"monitor", "monitors", "gaming monitor"}, "MON", "monitor"),
    ({"speaker", "speakers", "bluetooth speaker", "soundbar"}, "SPEAK", "speaker"),
    ({"smartwatch", "smart watch", "fitness band", "fitness tracker"}, "WEAR", "wearable"),
    ({"router", "wifi router", "modem"}, "NET", "networking"),
    ({"hard disk", "hard drive", "ssd", "pen drive"}, "STORE", "storage"),
]

# Legacy alias: historical rows may store category="audio".
CATEGORY_ALIASES = {
    "audio": "headphones",  # soft default; TWS preferred when title evidence is clear
}

ACCESSORY_REJECT_PATTERNS = (
    r"\blaptop\s+(bag|sleeve|backpack|case|stand|cooler|cooling\s+pad)\b",
    r"\btv\s+(stand|mount|wall\s+mount|unit|cover)\b",
    r"\brefrigerator\s+(cover|stand|base|guard)\b",
    r"\bwashing\s+machine\s+(stand|cover|base|trolley)\b",
    r"\bcamera\s+(lens|bag|strap|tripod|filter|battery|charger)\b",
    r"\bphone\s+(case|cover|tempered\s+glass|screen\s+guard|charger|cable)\b",
)

BRANDS = [
    "hp", "dell", "lenovo", "asus", "acer", "apple", "samsung", "msi",
    "lg", "microsoft", "toshiba", "razer", "gigabyte", "huawei", "honor",
    "infinix", "avita", "ultimus", "thomson", "chuwi", "walker", "browsebook",
    "realme", "xiaomi", "redmi", "oneplus", "motorola", "vaio", "jio", "jiobook",
    "primebook", "zebronics", "wings", "iball",
    "sony", "vivo", "oppo", "nothing", "google", "boat", "noise", "jbl", "bose",
    "sennheiser", "whirlpool", "godrej", "haier", "bosch", "ifb", "voltas",
    "tcl", "hisense", "panasonic", "canon", "nikon", "fujifilm", "poco",
    "iqoo", "nokia", "lava", "micromax", "blue star", "carrier", "daikin",
]

BRAND_ALIASES = {
    "hewlett": "hp", "hewlett packard": "hp", "rog": "asus", "vivobook": "asus",
    "zenbook": "asus", "tuf": "asus", "proart": "asus", "expertbook": "asus",
    "ideapad": "lenovo", "thinkpad": "lenovo", "thinkbook": "lenovo", "loq": "lenovo",
    "legion": "lenovo", "yoga": "lenovo", "inspiron": "dell", "xps": "dell",
    "latitude": "dell", "vostro": "dell", "alienware": "dell", "pavilion": "hp",
    "omen": "hp", "victus": "hp", "envy": "hp", "elitebook": "hp", "omnibook": "hp",
    "spectre": "hp", "macbook": "apple", "galaxy": "samsung", "nitro": "acer",
    "aspire": "acer", "predator": "acer", "swift": "acer",
}

TRACKING_KEYS = {
    "gclid", "fbclid", "ref", "tag", "src", "source", "spm", "srsltid",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "qid", "psc", "pd_rd_w", "pd_rd_r", "pd_rd_wg", "internal_source",
    "otracker", "fm", "iid", "ppt", "ppn", "ssid", "qH", "marketplace", "srno",
}

JUNK_TITLE_TERMS = {
    "protection plan", "warranty", "extended warranty", "resq", "oneassist",
    "laptop bag", "laptop sleeve", "laptop backpack", "laptop case", "laptop stand",
    "laptop charger", "cooling pad", "adapter", "charger", "mouse", "keyboard", "screen guard",
    "screen protector", "skin", "sticker", "cleaning kit", "ram upgrade", "ssd enclosure",
    "phone case", "phone cover", "tempered glass", "tv stand", "tv mount", "tv wall mount",
    "tv remote", "refrigerator cover", "fridge stand", "washing machine stand",
    "washing machine cover", "camera bag", "camera lens", "tripod", "memory card",
    "earbud case", "ear tips", "ear cushions", "ear pads", "replacement case",
    "charging case for", "silicone cover for", "headphone cable", "replacement cable",
    "filter by", "sort by", "sort by brand", "clear all", "apply filters",
}

LAPTOP_POSITIVE_TERMS = {
    "laptop", "notebook", "chromebook", "macbook", "vivobook", "zenbook", "expertbook",
    "ideapad", "thinkpad", "thinkbook", "loq", "legion", "yoga", "inspiron", "latitude",
    "vostro", "xps", "aspire", "nitro", "predator", "swift", "victus", "omen", "omnibook",
    "pavilion", "elitebook", "jiobook", "tuf", "rog",
}

_NOISE = re.compile(
    r"\b(laptop|notebook|computer|pc|anti[\s-]?glare|backlit|thin|light|"
    r"ultra[\s-]?slim|gaming|portable|slim|premium|business|standard|smartchoice|"
    r"silver|black|grey|gray|blue|gold|natural|starry|midnight|moonlight|"
    r"graphite|titanium|platinum|arctic|cool|mixed|mica|glacier|previously|powered\s+by|"
    r"windows\s*\d*|home|office|microsoft|ms\b|with|for|and|the|best|new|latest|"
    r"full\s*hd|fhd|wuxga|oled|ips|display|screen|inch|cm|kg)\b",
    re.IGNORECASE,
)
_SYMS = re.compile(r"[^\w\s\-.]")
_MULTISPC = re.compile(r"\s+")

CPU_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcore\s*ultra\s*(\d+)\s*(\d{3}[a-z]?)?\b", re.I), "intel_core_ultra"),
    (re.compile(r"\bcore\s*i([3579])[-\s]*(\d{4,5}[a-z]{0,3})?\b", re.I), "intel_core_i"),
    # Acer / retail titles: "Intel Core5-210H", "Intel Core 7", "Core7-240H"
    (re.compile(r"\b(?:intel\s*)?core\s*([3579])(?:[-\s]+|\s*)(\d{3}[a-z]{0,3})?\b", re.I), "intel_core_new"),
    (re.compile(r"\bintel\s*core\s*([357])\s*(\d{3}[a-z]?)\b", re.I), "intel_core_new"),
    (re.compile(r"\bceleron\s*(?:dual\s*core\s*)?(n?\d{4}|n\d{2})?\b", re.I), "intel_celeron"),
    (re.compile(r"\bpentium\s*(?:quad\s*core\s*)?(n?\d{4})?\b", re.I), "intel_pentium"),
    (re.compile(r"\bathlon\s*(?:silver|gold)?\s*(\d{4}[a-z]?)?\b", re.I), "amd_athlon"),
    (re.compile(r"\bryzen\s*(ai\s*)?([3579])\s*(?:pro\s*)?(\d{3,4}[a-z]{0,3})?\b", re.I), "amd_ryzen"),
    (re.compile(r"\bsnapdragon\s*x\s*(elite|plus)?\b", re.I), "qualcomm_snapdragon_x"),
    (re.compile(r"\bm\s*([1-5])\s*(pro|max|ultra)?\b", re.I), "apple_m"),
    (re.compile(r"\ba(\d{1,2})\s*bionic\b", re.I), "apple_a"),
]

GPU_RE = re.compile(
    r"\b(rtx\s*\d{4}\s*(?:ti)?|gtx\s*\d{3,4}\s*(?:ti)?|mx\s*\d{3}|"
    r"radeon\s*(?:\d{3,4}m?|rx\s*\d{3,4}m?)|iris\s*xe|uhd\s*graphics|arc\s*graphics)\b",
    re.I,
)

MODEL_CODE_RE = re.compile(
    r"\b([a-z]{1,3}\d{2,4}[a-z]{1,5}\d{0,4})\b|"
    r"\b(\d{2}[a-z]{1,5}\d{1,4}[a-z]{0,3})\b|"
    r"\b([a-z]{2,5}\d{3,8}[a-z]{0,5})\b|"
    r"\b(\d{2}-[a-z]{2}\d{3,5}[a-z]{2})\b|"
    r"\b([a-z]{1,3}\d{4}[a-z]{2,4}-[a-z0-9]{3,8})\b",
    re.I,
)

# Conservative laptop spec extraction. Storage-like contexts are explicitly
# excluded from RAM so values such as "512GB SSD" or "32GB storage" are not
# accidentally treated as memory.
RAM_RE = re.compile(
    r"(?<![\d.])\b(4|6|8|10|12|16|18|24|32|36|48|64|96|128)\s*gb"
    r"(?!\s*(?:ssd|hdd|nvme|emmc|ufs|storage|rom|nand|m\.2))\b"
    r"(?:\s*(?:ram|ddr\d*|lpddr\d*x?|memory|unified))?\b",
    re.I,
)
STORAGE_RE = re.compile(
    r"\b(\d{1,4}(?:\.\d+)?)\s*(gb|tb)\s*"
    r"(?:ssd|nvme|emmc|hdd|storage|rom|nand|ufs|m\.2)?\b",
    re.I,
)
SCREEN_RE = re.compile(
    r"\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|inches|\")\b|\b(\d{2}(?:\.\d{1,2})?)\s*cm\b",
    re.I,
)
GEN_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*gen(?:eration)?\b", re.I)

FAMILY_PATTERNS = [
    r"(ideapad\s+slim\s*\d+|ideapad\s*\d+|thinkpad\s+[a-z]\d+|thinkbook\s+\d+|loq\s+\d+|legion\s+\d+|yoga\s+slim\s*\d+|yoga\s+\d+)",
    r"(vivobook\s*(?:go\s*)?\d+|expertbook\s*p\d+|zenbook\s*(?:duo\s*)?\d+|proart\s+\w+|rog\s+\w+|tuf\s*(?:gaming\s*)?[af]\d+)",
    r"(inspiron\s+\d+|xps\s+\d+|latitude\s+\d+|vostro\s+\d+|alienware\s+\w+|dc\s*\d{5})",
    r"(pavilion\s*(?:plus\s*)?\d+|omen\s+\d+|victus\s+\d+|envy\s+\d+|elitebook\s+\d+|omnibook\s+\d+|spectre\s+\w+)",
    r"(aspire\s*(?:lite\s*)?\d*|nitro\s*(?:v\s*)?\d+|predator\s+\w+|swift\s*(?:go\s*)?\w+)",
    r"(macbook\s+(?:air|pro)\s*(?:m\d)?)",
    r"(galaxy\s+book\s*\d+)",
    r"(surface\s+(?:pro|laptop|book)\s*\d*)",
    r"(jiobook\s*\d*)",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha1_text(text: str, length: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


def ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")


def compact_space(text: str) -> str:
    return _MULTISPC.sub(" ", (text or "").strip())


def detect_category(query: str) -> tuple[str, str]:
    from mayabu.domain.categories.registry import CATEGORY_PREFIX, detect_category_result

    result = detect_category_result(query=query or "", title=query or "")
    category = result.category
    prefix = CATEGORY_PREFIX.get(category)
    if prefix:
        return prefix, category
    fallback = re.sub(r"[^A-Z0-9]", "", (query or "PROD").upper())[:6] or "PROD"
    return fallback, fallback.lower()


def parse_price(raw: Any, *, category: str | None = None) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL", "COMPARE"}:
        return None
    text = text.replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", re.sub(r"[^\d.]", " ", text))
    if not m:
        return None
    try:
        value = float(m.group(0))
    except ValueError:
        return None
    if category:
        from mayabu.domain.categories.registry import price_bounds_for

        lo, hi = price_bounds_for(category)
        if value < lo or value > hi:
            return None
    return value

def parse_discount(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw)
    if text.strip().upper() in {"N/A", "NA", "NONE", "NULL", "COMPARE"}:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def normalize_url(url: str) -> str:
    if not url or url == "N/A":
        return ""
    parts = urlsplit(url.strip())
    keep = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lk = key.lower()
        if lk in TRACKING_KEYS or lk.startswith("utm_"):
            continue
        keep.append((key, value))
    path = re.sub(r"/+", "/", parts.path or "").rstrip("/")
    return urlunsplit((
        (parts.scheme or "https").lower(),
        parts.netloc.lower(),
        path,
        urlencode(keep, doseq=True),
        "",
    )).rstrip("/")


def extract_native_id(platform: str, url: str, product_id: str | None = None) -> Optional[str]:
    platform = canonical_platform(platform)
    if product_id:
        pid = str(product_id)
        marker = product_source_abbrev(platform)
        if marker and marker in pid:
            tail = pid.split(marker, 1)[-1]
            if tail and not re.fullmatch(r"0+\d*", tail):
                return tail.upper()
    if not url or url == "N/A":
        return None
    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if platform == "amazon" or "amazon." in host:
        m = re.search(r"/dp/([A-Za-z0-9]{10})", path)
        return m.group(1).upper() if m else None
    if platform == "flipkart" or "flipkart." in host:
        pid = query.get("pid")
        if pid:
            return pid.upper()
        m = re.search(r"/p/(ITM[A-Za-z0-9]+)", path, re.I)
        return m.group(1).upper() if m else None
    if platform == "croma" or "croma." in host:
        m = re.search(r"/p/(\d{4,12})(?:$|/|\?)", path)
        return m.group(1) if m else None
    if platform == "reliancedigital" or "reliancedigital." in host:
        m = re.search(r"/p/(\d{4,12})(?:$|/|\?)", path)
        if m:
            return m.group(1)
        # Reliance frequently stores the stable SKU as the final slug number.
        m = re.search(r"-(\d{6,12})(?:$|\?)", path)
        return m.group(1) if m else None
    if platform == "vijaysales" or "vijaysales." in host:
        m = re.search(r"/p/(?:P?\d+/)?(\d{4,12})", path, re.I)
        return m.group(1) if m else None
    if platform == "jiomart" or "jiomart." in host:
        m = re.search(r"/(\d{6,12})(?:$|\?)", path)
        if m:
            return m.group(1)
        m = re.search(r"/product/[^/]+-(\d{5,12})(?:$|\?)", path, re.I)
        return m.group(1) if m else None
    if platform == "poorvika" or "poorvika." in host:
        m = re.search(r"/([a-z0-9][a-z0-9\-]{4,120})/p(?:$|\?|/)", path, re.I)
        if m:
            return m.group(1).upper()
        return None
    if platform == "bajajelectronics" or "bajajelectronics." in host:
        m = re.search(r"bajajelectronics\.com/([a-z0-9][a-z0-9\-]{3,160})(?:$|\?)", url, re.I)
        if m:
            slug = m.group(1).lower()
            if slug not in {"search", "cart", "login", "category", "categories", "brands"}:
                return slug.upper()
        return None
    return None


def canonical_platform(source: str) -> str:
    return canonical_platform_slug(source)


def listing_id(platform: str, native_id: str | None, url: str, title: str = "") -> str:
    platform = canonical_platform(platform)
    if native_id:
        return f"{platform}:{str(native_id).upper()}"
    norm_url = normalize_url(url)
    if norm_url:
        return f"{platform}:url:{sha1_text(norm_url, 18)}"
    return f"{platform}:title:{sha1_text(normalise_title(title), 18)}"


def product_source_id(category_prefix: str, platform: str, native_id: str | None, counter: int) -> str:
    abbrev = product_source_abbrev(platform)
    suffix = str(native_id).upper() if native_id else f"{counter:04d}"
    return f"{category_prefix}{abbrev}{suffix}"


def normalise_title(title: str) -> str:
    t = ascii_fold(title or "").lower()
    t = t.replace("&", " and ")
    t = _SYMS.sub(" ", t)
    t = _NOISE.sub(" ", t)
    return compact_space(t)


def title_tokens(title: str) -> set[str]:
    return {tok for tok in normalise_title(title).split() if len(tok) >= 2}


def resolve_brand(title: str) -> Optional[str]:
    tl = ascii_fold(title or "").lower()
    for alias in sorted(BRAND_ALIASES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(alias) + r"\b", tl):
            return BRAND_ALIASES[alias]
    for brand in BRANDS:
        if re.search(r"\b" + re.escape(brand) + r"\b", tl):
            return brand
    return None


def _to_storage_gb(value: str, unit: str) -> int:
    number = float(value)
    return int(number * 1024) if unit.lower() == "tb" else int(number)


def normalize_specs(specs: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize extracted specs to stable types used by matching/search."""
    out = dict(specs or {})
    for key in (
        "ram_gb",
        "storage_gb",
        "generation",
        "star_rating",
        "rpm",
        "refresh_rate_hz",
        "battery_mah",
        "camera_mp",
    ):
        value = out.get(key)
        if value is None or value == "":
            if key in out:
                out[key] = None
            continue
        try:
            out[key] = int(float(value))
        except (TypeError, ValueError):
            out[key] = None
    for key in (
        "screen_inch",
        "display_size_inch",
        "screen_size_inch",
        "capacity_l",
        "capacity_kg",
        "battery_hours",
        "megapixels",
    ):
        value = out.get(key)
        if value is not None and value != "":
            try:
                out[key] = round(float(value), 1)
            except (TypeError, ValueError):
                out[key] = None
    for key in ("model_codes", "cpu_models"):
        value = out.get(key)
        if value is None:
            out[key] = []
        elif isinstance(value, (list, tuple, set)):
            out[key] = sorted(
                {
                    str(v).strip().upper() if key == "model_codes" else str(v).strip().lower()
                    for v in value
                    if str(v).strip()
                }
            )
        else:
            text = str(value).strip()
            out[key] = [text.upper() if key == "model_codes" else text.lower()] if text else []
    for key in (
        "brand",
        "category",
        "family",
        "cpu_series",
        "gpu",
        "chipset",
        "network_generation",
        "panel_type",
        "resolution",
        "smart_platform",
        "door_type",
        "frost_type",
        "compressor_type",
        "load_type",
        "automation_type",
        "form_factor",
        "connectivity",
        "codec",
        "bluetooth_version",
        "camera_type",
        "sensor_format",
        "mount",
        "kit_lens",
        "color",
        "series",
    ):
        if out.get(key) is not None:
            out[key] = str(out[key]).strip().lower() or None
    if "anc" in out and out["anc"] is not None:
        out["anc"] = bool(out["anc"])
    if "body_only" in out and out["body_only"] is not None:
        out["body_only"] = bool(out["body_only"])
    return out

def extract_specs(title: str, category: str = "laptop") -> dict[str, Any]:
    """Dispatch to category adapters; laptop behavior remains the production baseline."""
    from mayabu.domain.categories.registry import extract_category_specs

    return extract_category_specs(title, category=category)


def looks_like_real_product(title: str, category: str) -> bool:
    from mayabu.domain.identity_quality import has_sufficient_product_identity

    t = (title or "").lower()
    if not t or len(t) < 3:
        return False
    if category == "accessory":
        return False
    if any(term in t for term in JUNK_TITLE_TERMS):
        return False
    if not has_sufficient_product_identity(title, category):
        return False
    if category == "laptop":
        if any(term in t for term in LAPTOP_POSITIVE_TERMS):
            return True
        # Many retailers omit the word "laptop" but still list brand + RAM/CPU.
        if resolve_brand(title) and (
            re.search(r"\b\d{1,2}\s*gb\b", t)
            or re.search(r"\b(i[3579]|ryzen|celeron|pentium|core\s*ultra)\b", t)
        ):
            return True
        return False
    return True

def normalize_raw_listing(raw: dict[str, Any], platform_hint: str | None = None, query: str = "", observed_at: str | None = None) -> Optional[dict[str, Any]]:
    from mayabu.domain.categories.registry import CATEGORY_PREFIX, detect_category_result

    platform = canonical_platform(platform_hint or raw.get("platform") or raw.get("source") or "unknown")
    title = compact_space(str(raw.get("title") or ""))
    detection = detect_category_result(
        query=query or str(raw.get("query") or ""),
        title=title,
        breadcrumbs=str(raw.get("breadcrumbs") or ""),
        url=str(raw.get("link") or raw.get("url") or raw.get("product_url") or ""),
        structured_category=str(raw.get("structured_category") or raw.get("category") or ""),
    )
    category = detection.category
    prefix = CATEGORY_PREFIX.get(category) or "UNK"
    if category == "accessory" or not looks_like_real_product(title, category):
        return None
    url = raw.get("link") or raw.get("url") or raw.get("product_url") or ""
    norm_url = normalize_url(str(url))
    native = raw.get("native_id") or extract_native_id(platform, str(url), raw.get("productId"))
    lid = raw.get("listing_id") or listing_id(platform, native, norm_url, title)
    # Category-aware price parse when possible
    price = raw.get("price") if "price" in raw else parse_price(raw.get("currentPrice"), category=category if category != "unknown" else None)
    mrp = raw.get("mrp") if "mrp" in raw else parse_price(raw.get("maxRetailPrice"), category=category if category != "unknown" else None)
    discount = raw.get("discount_pct") if "discount_pct" in raw else parse_discount(raw.get("discount"))
    if discount is None and price and mrp and mrp > price:
        discount = round((1.0 - float(price) / float(mrp)) * 100, 2)
    specs = normalize_specs(raw.get("specs") or extract_specs(title, category))
    return {
        "platform": platform,
        "source": platform,
        "query": query or raw.get("query") or "",
        "category": category,
        "category_confidence": detection.confidence,
        "category_evidence": list(detection.evidence),
        "category_prefix": prefix,
        "native_id": str(native).upper() if native else None,
        "listing_id": lid,
        "source_product_id": raw.get("productId") or product_source_id(prefix, platform, native, 0),
        "title": title,
        "title_norm": normalise_title(title),
        "price": float(price) if price is not None else None,
        "mrp": float(mrp) if mrp is not None else None,
        "discount_pct": float(discount) if discount is not None else None,
        "currency": str(raw.get("currency") or "INR").upper(),
        "url": norm_url or str(url or ""),
        "image": raw.get("image") or raw.get("image_url") or "",
        "scraped_at": observed_at or raw.get("scraped_at") or utc_now(),
        "specs": specs,
        "raw": raw,
    }


def read_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(p)


def stable_observation_id(listing_id_value: str, observed_at: str, price: Optional[float], mrp: Optional[float]) -> str:
    day_key = (observed_at or utc_now())[:19]
    return sha1_text(f"{listing_id_value}|{day_key}|{price}|{mrp}", 24)


def iter_json_records(paths: Iterable[str | None]) -> Iterable[dict[str, Any]]:
    for path in paths:
        if not path:
            continue
        data = read_json(path, default=[])
        if isinstance(data, dict) and "records" in data:
            records = data.get("records") or []
        elif isinstance(data, list):
            records = data
        else:
            records = []
        for rec in records:
            if isinstance(rec, dict):
                yield rec
