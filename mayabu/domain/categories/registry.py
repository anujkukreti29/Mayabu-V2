"""Category adapter registry and detection helpers.

UNKNOWN stays UNKNOWN — never fall back to laptop parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from mayabu.domain.categories.camera import CameraAdapter
from mayabu.domain.categories.headphones import HeadphonesAdapter
from mayabu.domain.categories.laptop import LaptopAdapter
from mayabu.domain.categories.refrigerator import RefrigeratorAdapter
from mayabu.domain.categories.smartphone import SmartphoneAdapter
from mayabu.domain.categories.television import TelevisionAdapter
from mayabu.domain.categories.tws import TwsAdapter
from mayabu.domain.categories.washing_machine import WashingMachineAdapter

CategoryConfidence = Literal["high", "medium", "low", "unknown"]

_LAPTOP = LaptopAdapter()
_SMARTPHONE = SmartphoneAdapter()
_TELEVISION = TelevisionAdapter()
_REFRIGERATOR = RefrigeratorAdapter()
_WASHING = WashingMachineAdapter()
_TWS = TwsAdapter()
_HEADPHONES = HeadphonesAdapter()
_CAMERA = CameraAdapter()

_ADAPTERS = {
    "laptop": _LAPTOP,
    "smartphone": _SMARTPHONE,
    "television": _TELEVISION,
    "refrigerator": _REFRIGERATOR,
    "washing_machine": _WASHING,
    "tws": _TWS,
    "headphones": _HEADPHONES,
    "camera": _CAMERA,
    "audio": _HEADPHONES,
}

CATEGORY_PREFIX = {
    "laptop": "LAP",
    "smartphone": "SMARTPH",
    "television": "TV",
    "refrigerator": "FRIDGE",
    "washing_machine": "WASH",
    "tws": "TWS",
    "headphones": "AUDIO",
    "audio": "AUDIO",
    "camera": "CAM",
    "tablet": "TAB",
    "wearable": "WEAR",
    "air_conditioner": "AC",
    "accessory": "ACC",
    "unknown": "UNK",
}

# Word-boundary accessory patterns — avoid naive "tv" ⊂ "tv stand" parent merges.
ACCESSORY_REJECT_RE = re.compile(
    r"("
    r"\blaptop\s+(bag|sleeve|backpack|case|stand|cooler|cooling\s+pad|charger|adapter)\b|"
    r"\b(notebook|macbook)\s+(bag|sleeve|case|stand|cover)\b|"
    r"\b(phone|mobile|smartphone)\s+(case|cover|tempered\s+glass|screen\s+(?:guard|protector)|charger|cable|holder)\b|"
    r"\b(camera\s+)?lens\s+protector\b|"
    r"\blens\s+protector\s+for\b|"
    r"\btempered\s+glass\b|"
    r"\bscreen\s+protector\b|"
    r"\bback\s+cover\s+for\b|"
    r"\bclear\s+case\s+for\b|"
    r"\bprotector\s+for\s+(iphone|galaxy|pixel|oneplus|18\s+pro|16\s+pro|15\s+pro)\b|"
    r"\btv\s+(stand|mount|wall\s+mount|unit|cover|remote)\b|"
    r"\btelevision\s+(stand|mount|cover|remote)\b|"
    r"\bwall\s+mount\b.*\b(tv|television)\b|"
    r"\b(refrigerator|fridge)\s+(cover|stand|base|guard|mat)\b|"
    r"\bwashing[\s-]*machine\s+(stand|cover|base|trolley)\b|"
    r"\bcamera\s+(lens|bag|strap|tripod|filter|battery|charger|memory\s+card|cage|mount|gimbal|cleaning\s+kit)\b|"
    r"\b(lens\s+only|prime\s+lens|zoom\s+lens|camera\s+flash|lens\s+cap)\b|"
    r"\b(memory\s+card|sd\s+card|tripod|gimbal)\b|"
    r"\b(silicon|silicone|protective)\s+(camera\s+)?(case|cover)\b|"
    r"\b(camera\s+)?(case|cover)\s+(compatible\s+)?for\s+(canon|sony|nikon|fujifilm|olympus)\b|"
    r"\b(bag|strap|tripod|filter|battery\s+grip)\s+for\s+(canon|sony|nikon|eos)\b|"
    # TWS / headphone accessories (not primary audio products).
    r"\b(earbud|ear\s*bud|tws|buds?)\s+(case|tips|ear\s*tips|charging\s+case|replacement|cover|pouch)\b|"
    r"\b(replacement|spare)\s+(charging\s+)?case\b|"
    r"\b(charging|carry|protective|silicone|silicon)\s+case\s+for\b|"
    r"\bcase\s+for\s+(samsung|sony|apple|galaxy|airpods|buds|earbuds?|tws|headphones?|canon|nikon)\b|"
    r"\b(earbuds?|headphones?|ear\s*buds?)\s+for\s+(samsung|sony|apple|galaxy|airpods|buds)\b|"
    r"\breplacement\s+ear\s*tips?\b|"
    r"\bear\s*tips\b|"
    r"\bear\s*(cushions?|pads?)\b|"
    r"\b(silicone|silicon|protective)\s+(cover|case)\s+(for|compatible)\b|"
    r"\breplacement\s+(cable|cord|wire)\b|"
    r"\bheadphone\s+(cable|cord|wire|stand|case|pouch|adapter|dongle)\b|"
    r"\bearphone\s+(cable|cord|case)\b"
    r")",
    re.I,
)

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(laptop|notebook|ultrabook|chromebook|macbook)\b", re.I), "laptop"),
    (re.compile(r"\b(smartphone|iphone|android\s*phone|mobile\s*phone)\b", re.I), "smartphone"),
    # Common Indian retail phone titles omit the word "phone" (Galaxy S24, A37, F07...).
    (
        re.compile(
            r"\b("
            r"galaxy\s+[a-z]?\d{1,2}|"
            r"galaxy\s+z\s*\w+|"
            r"pixel\s*\d{1,2}|"
            r"redmi\s*(?:note\s*)?\d{1,2}|"
            r"poco\s*[a-z]?\d{1,2}|"
            r"oneplus\s*(?:nord\s*)?\d|"
            r"nothing\s*phone|"
            r"moto\s*[a-z]?\d+"
            r")\b",
            re.I,
        ),
        "smartphone",
    ),
    (re.compile(r"\b(true\s*wireless|tws|earbuds|airpods|galaxy\s*buds)\b", re.I), "tws"),
    (re.compile(r"\b(headphones?|over[\s-]?ear|on[\s-]?ear|neckband|earphones?)\b", re.I), "headphones"),
    # Soundbars are audio — never television (even when title says "for TV").
    (re.compile(r"\b(sound\s*bars?|soundbars?)\b", re.I), "headphones"),
    (re.compile(r"\b(television|smart\s*tv|oled\s*tv|qled\s*tv|led\s*tv)\b", re.I), "television"),
    # Bare "TV" token — exclude "for TV" / "TV sound" speaker phrasing via _match_rule.
    (re.compile(r"(?<![a-z])tvs?(?![a-z])", re.I), "television"),
    (re.compile(r"\b(refrigerator|fridge)\b", re.I), "refrigerator"),
    (re.compile(r"\b(washing\s*machine|washer)\b", re.I), "washing_machine"),
    (
        re.compile(
            r"\b("
            r"mirrorless|dslr|action\s*camera|digital\s*camera|"
            r"ilce[\s-]?\d+|eos\s*r\d*|alpha\s*\d+|sony\s*a\d+"
            r")\b",
            re.I,
        ),
        "camera",
    ),
    (re.compile(r"\b(tablet|ipad)\b", re.I), "tablet"),
    (re.compile(r"\b(smartwatch|fitness\s*band)\b", re.I), "wearable"),
    (re.compile(r"\b(air\s*conditioner|split\s*ac|window\s*ac)\b", re.I), "air_conditioner"),
]

# Party/Bluetooth speakers often mention "TV Sound Booster" and trip the bare TV rule.
_SPEAKER_NOT_TV_RE = re.compile(
    r"\b("
    r"party\s*speaker|bluetooth\s*speaker|wireless\s*speaker|tower\s*speaker|"
    r"portable\s*speaker|srs[\s-]?ult|home\s*theat(?:re|er)|sound\s*bar|"
    r"soundbars?"
    r")\b",
    re.I,
)
_REAL_TV_SIGNAL_RE = re.compile(
    r"\b("
    r"\d{2,3}\s*(?:inch|cm)\b|"
    r"(?:oled|qled|mini[\s-]?led|led|lcd)\s*(?:smart\s*)?tv|"
    r"smart\s*tv|"
    r"television|"
    r"bravia|"
    r"uhd\s*tv|"
    r"4k\s*tv"
    r")\b",
    re.I,
)


def _match_rule(text: str) -> str | None:
    if not text:
        return None
    # Speakers / soundbars that mention TV must not become television.
    if _SPEAKER_NOT_TV_RE.search(text) and not _REAL_TV_SIGNAL_RE.search(text):
        if re.search(r"\bsound\s*bars?\b|\bsoundbars?\b", text, re.I):
            return "headphones"
        return "unknown"
    for pattern, category in _RULES:
        if pattern.search(text):
            if category == "television" and _SPEAKER_NOT_TV_RE.search(text):
                if not _REAL_TV_SIGNAL_RE.search(text):
                    return "unknown"
            return category
    # Screen-size + panel/UHD cues without the literal word "TV".
    if re.search(r"\b\d{2,3}\s*(?:inch|cm)\b", text, re.I) and re.search(
        r"\b(oled|qled|mini[\s-]?led|uhd|4k|smart\s*tizen|led\s*smart)\b",
        text,
        re.I,
    ):
        if not _SPEAKER_NOT_TV_RE.search(text):
            return "television"
    if re.search(r"\b(phone|mobile)\b", text) and not re.search(
        r"\b(case|cover|tempered|protector|charger|cable)\b", text
    ):
        return "smartphone"
    return None


@dataclass(frozen=True, slots=True)
class CategoryDetection:
    category: str
    confidence: CategoryConfidence
    evidence: tuple[str, ...]


def normalize_category_name(category: str | None) -> str:
    raw = (category or "").strip().lower().replace(" ", "_").replace("-", "_")
    if raw == "audio":
        return "audio"
    return raw or "unknown"


def get_adapter(category: str | None):
    key = normalize_category_name(category)
    if key in {"unknown", "accessory"}:
        return None
    return _ADAPTERS.get(key)


def detect_category_result(
    *,
    query: str = "",
    title: str = "",
    breadcrumbs: str = "",
    url: str = "",
    structured_category: str = "",
) -> CategoryDetection:
    """Deterministic category detection with confidence and accessory rejection."""
    structured = normalize_category_name(structured_category)
    breadcrumb_l = (breadcrumbs or "").lower()
    title_l = (title or "").lower()
    query_l = (query or "").lower()
    url_l = (url or "").lower()

    # Accessories: check title/breadcrumbs first (strongest product evidence).
    for source, label in (
        (title_l, "title"),
        (breadcrumb_l, "breadcrumb"),
        (query_l, "query"),
        (url_l, "url"),
    ):
        if source and ACCESSORY_REJECT_RE.search(source):
            return CategoryDetection("accessory", "high", (f"accessory:{label}",))

    evidence: list[str] = []

    if structured and structured not in {"unknown", "accessory"}:
        if structured in _ADAPTERS or structured in CATEGORY_PREFIX:
            evidence.append("structured_category")
            crumb_cat = _match_rule(breadcrumb_l) if breadcrumb_l else None
            if crumb_cat == structured:
                evidence.append("breadcrumb")
                return CategoryDetection(structured, "high", tuple(evidence))
            title_cat = _match_rule(title_l) if title_l else None
            if title_cat and title_cat != structured:
                # Retailer breadcrumbs sometimes label speakers under TV; trust title.
                if structured == "television" and _SPEAKER_NOT_TV_RE.search(title_l or ""):
                    if not _REAL_TV_SIGNAL_RE.search(title_l or ""):
                        resolved = title_cat if title_cat != "unknown" else "unknown"
                        return CategoryDetection(
                            resolved,
                            "high",
                            ("title_speaker_not_tv", "structured_rejected"),
                        )
                return CategoryDetection(structured, "medium", tuple(evidence + ["title_conflict"]))
            conf: CategoryConfidence = "high" if structured in _ADAPTERS else "medium"
            return CategoryDetection(structured, conf, tuple(evidence))

    crumb_cat = _match_rule(breadcrumb_l) if breadcrumb_l else None
    if crumb_cat:
        evidence.append("breadcrumb")
        title_cat = _match_rule(title_l) if title_l else None
        if title_cat == crumb_cat:
            evidence.append("title")
            return CategoryDetection(crumb_cat, "high", tuple(evidence))
        return CategoryDetection(crumb_cat, "medium", tuple(evidence))

    title_cat = _match_rule(title_l) if title_l else None
    if title_cat:
        evidence.append("title")
        query_cat = _match_rule(query_l) if query_l else None
        if query_cat == title_cat:
            evidence.append("query")
            return CategoryDetection(title_cat, "high", tuple(evidence))
        return CategoryDetection(title_cat, "medium", tuple(evidence))

    query_cat = _match_rule(query_l) if query_l else None
    if query_cat:
        # Query alone is weak for product classification (search intent ≠ listing).
        return CategoryDetection(query_cat, "low", ("query",))

    url_cat = _match_rule(url_l) if url_l else None
    if url_cat:
        return CategoryDetection(url_cat, "low", ("url",))

    return CategoryDetection("unknown", "unknown", ())


def detect_category_from_evidence(
    *,
    query: str = "",
    title: str = "",
    breadcrumbs: str = "",
    url: str = "",
    structured_category: str = "",
) -> str:
    return detect_category_result(
        query=query,
        title=title,
        breadcrumbs=breadcrumbs,
        url=url,
        structured_category=structured_category,
    ).category


def extract_generic_specs(title: str) -> dict[str, Any]:
    """Safe metadata only — brand + model codes. No laptop RAM/CPU parsing."""
    from mayabu_common import MODEL_CODE_RE, ascii_fold, resolve_brand

    text = ascii_fold(title or "")
    brand = resolve_brand(text)
    model_codes: set[str] = set()
    for m in MODEL_CODE_RE.finditer(text):
        val = next((g for g in m.groups() if g), "")
        val = val.upper().replace(" ", "")
        if len(val) >= 5:
            model_codes.add(val)
    return {
        "brand": brand,
        "category": "unknown",
        "family": None,
        "model_codes": sorted(model_codes),
    }


def extract_category_specs(
    title: str,
    category: str = "laptop",
    *,
    breadcrumbs: str = "",
    url: str = "",
) -> dict[str, Any]:
    normalized = normalize_category_name(category)
    if normalized in {"unknown", "accessory"} or get_adapter(normalized) is None:
        specs = extract_generic_specs(title)
        specs["category"] = normalized if normalized in {"unknown", "accessory"} else "unknown"
        return specs
    adapter = get_adapter(normalized)
    assert adapter is not None
    specs = adapter.extract_specs(title, breadcrumbs=breadcrumbs, url=url)
    specs["category"] = (
        "audio" if normalized == "audio" else adapter.name
    )
    return specs


def price_bounds_for(category: str | None) -> tuple[int, int]:
    adapter = get_adapter(category)
    if adapter is None:
        return (100, 2_000_000)
    return adapter.price_bounds()


def hard_conflicts(category: str | None, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    adapter = get_adapter(category)
    if adapter is None:
        return []
    return adapter.hard_conflicts(left, right)
