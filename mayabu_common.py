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

PLATFORMS = {"amazon", "flipkart", "croma", "reliancedigital"}

CATEGORY_RULES: list[tuple[set[str], str, str]] = [
    ({"laptop", "laptops", "notebook", "notebooks", "ultrabook", "ultrabooks", "chromebook", "macbook"}, "LAP", "laptop"),
    ({"smartphone", "smartphones", "mobile", "mobiles", "phone", "phones", "iphone", "android"}, "SMARTPH", "smartphone"),
    ({"tablet", "tablets", "ipad", "android tablet"}, "TAB", "tablet"),
    ({"television", "tv", "tvs", "smart tv", "oled tv", "qled tv", "led tv"}, "TV", "television"),
    ({"headphone", "headphones", "earphone", "earphones", "earbuds", "tws", "neckband"}, "AUDIO", "audio"),
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

BRANDS = [
    "hp", "dell", "lenovo", "asus", "acer", "apple", "samsung", "msi",
    "lg", "microsoft", "toshiba", "razer", "gigabyte", "huawei", "honor",
    "infinix", "avita", "ultimus", "thomson", "chuwi", "walker", "browsebook",
    "realme", "xiaomi", "redmi", "oneplus", "motorola", "vaio", "jio", "jiobook",
    "primebook", "zebronics", "wings", "iball",
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
    "cooling pad", "adapter", "charger", "mouse", "keyboard", "screen guard",
    "skin", "sticker", "cleaning kit", "ram upgrade", "ssd enclosure",
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
    q = (query or "").lower().strip()
    for keywords, prefix, category in CATEGORY_RULES:
        if any(kw in q for kw in keywords):
            return prefix, category
    fallback = re.sub(r"[^A-Z0-9]", "", (query or "PROD").upper())[:6] or "PROD"
    return fallback, fallback.lower()


def parse_price(raw: Any) -> Optional[float]:
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
        return float(m.group(0))
    except ValueError:
        return None


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
        prefix_map = {
            "amazon": "AMAZON",
            "flipkart": "FLIPKART",
            "croma": "CROMA",
            "reliancedigital": "RELIANCE",
        }
        marker = prefix_map.get(platform)
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
    return None


def canonical_platform(source: str) -> str:
    s = (source or "").strip().lower().replace(" ", "")
    if s in {"reliance", "reliancedigital", "reliance_digital"}:
        return "reliancedigital"
    if s in {"amazon", "flipkart", "croma"}:
        return s
    return s or "unknown"


def listing_id(platform: str, native_id: str | None, url: str, title: str = "") -> str:
    platform = canonical_platform(platform)
    if native_id:
        return f"{platform}:{str(native_id).upper()}"
    norm_url = normalize_url(url)
    if norm_url:
        return f"{platform}:url:{sha1_text(norm_url, 18)}"
    return f"{platform}:title:{sha1_text(normalise_title(title), 18)}"


def product_source_id(category_prefix: str, platform: str, native_id: str | None, counter: int) -> str:
    abbrev = {
        "amazon": "AMAZON",
        "flipkart": "FLIPKART",
        "croma": "CROMA",
        "reliancedigital": "RELIANCE",
    }.get(canonical_platform(platform), platform.upper())
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
    for key in ("ram_gb", "storage_gb", "generation"):
        value = out.get(key)
        if value is None or value == "":
            out[key] = None
            continue
        try:
            out[key] = int(float(value))
        except (TypeError, ValueError):
            out[key] = None
    value = out.get("screen_inch")
    if value is not None and value != "":
        try:
            out["screen_inch"] = round(float(value), 1)
        except (TypeError, ValueError):
            out["screen_inch"] = None
    for key in ("model_codes", "cpu_models"):
        value = out.get(key)
        if value is None:
            out[key] = []
        elif isinstance(value, (list, tuple, set)):
            out[key] = sorted({str(v).strip().upper() if key == "model_codes" else str(v).strip().lower() for v in value if str(v).strip()})
        else:
            text = str(value).strip()
            out[key] = [text.upper() if key == "model_codes" else text.lower()] if text else []
    for key in ("brand", "category", "family", "cpu_series", "gpu"):
        if out.get(key) is not None:
            out[key] = str(out[key]).strip().lower() or None
    return out


def extract_specs(title: str, category: str = "laptop") -> dict[str, Any]:
    text = ascii_fold(title or "")
    tl = text.lower()
    brand = resolve_brand(text)

    ram_hits: list[int] = []
    storage_hits: list[int] = []
    for m in RAM_RE.finditer(text):
        value = int(m.group(1))
        if value in {2, 3, 4, 6, 8, 10, 12, 16, 18, 24, 32, 36, 48, 64, 96, 128}:
            # Avoid screen sizes like 16 inch accidentally marked as RAM by requiring GB token.
            ram_hits.append(value)
    ram = max(ram_hits) if ram_hits else None

    for m in STORAGE_RE.finditer(text):
        gb = _to_storage_gb(m.group(1), m.group(2))
        if gb >= 32 and gb != ram:
            storage_hits.append(gb)
    storage_gb = max(storage_hits) if storage_hits else None

    screen = None
    sm = SCREEN_RE.search(text)
    if sm:
        if sm.group(1):
            screen = round(float(sm.group(1)), 1)
        elif sm.group(2):
            screen = round(float(sm.group(2)) / 2.54, 1)

    gen = None
    gm = GEN_RE.search(text)
    if gm:
        try:
            gen = int(gm.group(1))
        except ValueError:
            gen = None

    cpu_series = None
    cpu_models: set[str] = set()
    for pattern, label in CPU_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        groups = [g for g in m.groups() if g]
        normalized_groups = [re.sub(r"\s+", "", g.lower()) for g in groups]
        cpu_series = label
        if normalized_groups:
            cpu_series = label + ":" + ":".join(normalized_groups[:2])
            cpu_models.add(":".join([label] + normalized_groups))
        break

    model_codes: set[str] = set()
    for m in MODEL_CODE_RE.finditer(text):
        val = next((g for g in m.groups() if g), "")
        val = val.upper().replace(" ", "")
        if len(val) < 5:
            continue
        # Avoid generic CPU-only codes; CPU models are handled separately.
        if re.fullmatch(r"I[3579]\d{4,5}[A-Z]*", val):
            continue
        if val.lower() in {"windows11", "office2024"}:
            continue
        model_codes.add(val)

    gpu = None
    gm2 = GPU_RE.search(text)
    if gm2:
        gpu = re.sub(r"\s+", "", gm2.group(1).lower())

    family = None
    for fp in FAMILY_PATTERNS:
        fm = re.search(fp, tl)
        if fm:
            # Avoid false family extraction from adjacent specs such as
            # "IdeaPad 16GB" or "Pavilion 15.6 inch".
            tail = tl[fm.end(1):fm.end(1) + 10]
            if re.match(r"\s*(?:\.\d+\s*)?(?:gb|tb|inch|inches|cm)\b", tail):
                continue
            family = re.sub(r"\s+", "_", fm.group(1).strip().lower())
            break

    return {
        "brand": brand,
        "category": category,
        "family": family,
        "model_codes": sorted(model_codes),
        "cpu_series": cpu_series,
        "cpu_models": sorted(cpu_models),
        "gpu": gpu,
        "ram_gb": ram,
        "storage_gb": storage_gb,
        "screen_inch": screen,
        "generation": gen,
    }


def looks_like_real_product(title: str, category: str) -> bool:
    t = (title or "").lower()
    if not t or len(t) < 5:
        return False
    if any(term in t for term in JUNK_TITLE_TERMS):
        return False
    if category == "laptop":
        return any(term in t for term in LAPTOP_POSITIVE_TERMS)
    return True


def normalize_raw_listing(raw: dict[str, Any], platform_hint: str | None = None, query: str = "", observed_at: str | None = None) -> Optional[dict[str, Any]]:
    platform = canonical_platform(platform_hint or raw.get("platform") or raw.get("source") or "unknown")
    title = compact_space(str(raw.get("title") or ""))
    prefix, category = detect_category(query or raw.get("query") or title)
    if not looks_like_real_product(title, category):
        return None
    url = raw.get("link") or raw.get("url") or raw.get("product_url") or ""
    norm_url = normalize_url(str(url))
    native = raw.get("native_id") or extract_native_id(platform, str(url), raw.get("productId"))
    lid = raw.get("listing_id") or listing_id(platform, native, norm_url, title)
    price = raw.get("price") if "price" in raw else parse_price(raw.get("currentPrice"))
    mrp = raw.get("mrp") if "mrp" in raw else parse_price(raw.get("maxRetailPrice"))
    discount = raw.get("discount_pct") if "discount_pct" in raw else parse_discount(raw.get("discount"))
    if discount is None and price and mrp and mrp > price:
        discount = round((1.0 - float(price) / float(mrp)) * 100, 2)
    specs = normalize_specs(raw.get("specs") or extract_specs(title, category))
    return {
        "platform": platform,
        "source": platform,
        "query": query or raw.get("query") or "",
        "category": category,
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
