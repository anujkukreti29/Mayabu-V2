"""Product-type classification for match gating (body vs accessory, etc.)."""

from __future__ import annotations

import re
from typing import Literal

ProductType = Literal[
    "product",
    "accessory",
    "camera_body",
    "camera_kit",
    "camera_lens",
    "camera_accessory",
    "phone_accessory",
    "audio_accessory",
    "tv_accessory",
    "appliance_accessory",
    "unknown",
]

_CAMERA_ACCESSORY = re.compile(
    r"\b("
    r"silicon(?:e)?\s+(?:cover|case)|"
    r"protective\s+(?:cover|case)|"
    r"(?:camera\s+)?(?:case|cover|bag|strap|tripod|gimbal|filter|lens\s+cap|battery(?:\s+grip)?|"
    r"charger|memory\s+card|sd\s+card|cage|mount|cleaning\s+kit)"
    r")\b",
    re.I,
)
_CAMERA_KIT = re.compile(r"\b(kit|with\s+\d{2,3}\s*[-–]\s*\d{2,3}\s*mm|18-55|18-45|18-150|rf-s)\b", re.I)
_CAMERA_BODY = re.compile(r"\b(body\s+only|body\b|mirrorless|dslr)\b", re.I)
_CAMERA_LENS = re.compile(r"\b(lens\s+only|prime\s+lens|zoom\s+lens|telephoto\s+lens|ef-s|rf-s\s*\d)\b", re.I)

_PHONE_ACCESSORY = re.compile(
    r"\b(case|cover|tempered\s+glass|screen\s+(?:guard|protector)|charger|cable|holder|back\s+cover)\b",
    re.I,
)
_AUDIO_ACCESSORY = re.compile(
    r"\b("
    r"replacement\s+(?:case|ear\s*tips?)|"
    r"ear\s*tips?|"
    r"charging\s+case|"
    r"ear\s*(?:cushions?|pads?)|"
    r"headphone\s+(?:cable|cord|stand)|"
    r"sound\s*bars?|"
    r"home\s+theat(?:re|er)|"
    r"silicon(?:e)?\s+(?:case|cover)|"
    r"(?:case|cover)\s+(?:for|compatible\s+with)\s+(?:galaxy\s+buds|airpods|buds|wf-)|"
    r"earbuds?\s+for\s+(?:samsung|apple|oneplus|galaxy)|"
    r"protective\s+(?:case|cover)\s+for"
    r")\b",
    re.I,
)
_TV_ACCESSORY = re.compile(r"\b(remote|wall\s+mount|tv\s+stand|tv\s+unit)\b", re.I)
_APPLIANCE_ACCESSORY = re.compile(
    r"\b((?:fridge|refrigerator|washing[\s-]*machine)\s+(?:stand|cover|base|trolley|mat))\b",
    re.I,
)


def classify_product_type(title: str | None, *, category: str | None = None) -> ProductType:
    text = str(title or "")
    cat = (category or "").lower()
    if _APPLIANCE_ACCESSORY.search(text):
        return "appliance_accessory"
    if cat in {"tws", "headphones"} and _AUDIO_ACCESSORY.search(text):
        return "audio_accessory"
    if cat == "television" and _TV_ACCESSORY.search(text):
        return "tv_accessory"
    if cat == "smartphone" and _PHONE_ACCESSORY.search(text):
        return "phone_accessory"
    # Camera heuristics: only for camera category, or brand/camera cues when category
    # is unset. Never reclassify explicit non-camera categories (Sony TWS "Quick Charge").
    camera_context = cat == "camera" or (
        cat in {"", "unknown", "accessory"}
        and re.search(r"\b(canon|sony|nikon|fujifilm|eos|alpha|mirrorless|dslr)\b", text, re.I)
    )
    if camera_context:
        if _CAMERA_ACCESSORY.search(text) and not re.search(
            r"\b(mirrorless\s+camera|dslr\s+camera|camera\s+with|earbuds?|headphones?|tws|buds)\b",
            text,
            re.I,
        ):
            return "camera_accessory"
        if _CAMERA_LENS.search(text) and not re.search(r"\b(camera|body|kit)\b", text, re.I):
            return "camera_lens"
        if _CAMERA_KIT.search(text):
            return "camera_kit"
        if _CAMERA_BODY.search(text):
            return "camera_body"
    if cat == "accessory":
        return "accessory"
    return "product"


_COMPATIBLE: dict[ProductType, set[ProductType]] = {
    "product": {"product", "camera_body", "camera_kit", "unknown"},
    "camera_body": {"camera_body", "product"},
    "camera_kit": {"camera_kit", "product"},
    "camera_lens": {"camera_lens"},
    "camera_accessory": {"camera_accessory"},
    "phone_accessory": {"phone_accessory"},
    "audio_accessory": {"audio_accessory"},
    "tv_accessory": {"tv_accessory"},
    "appliance_accessory": {"appliance_accessory"},
    "accessory": {"accessory"},
    "unknown": {"product", "camera_body", "camera_kit", "unknown"},
}


def product_types_compatible(left: ProductType, right: ProductType) -> bool:
    if left == right:
        return True
    return right in _COMPATIBLE.get(left, set()) or left in _COMPATIBLE.get(right, set())


__all__ = [
    "ProductType",
    "classify_product_type",
    "product_types_compatible",
]
