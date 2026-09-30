"""Pure platform URL detection and validation shared by API and workers."""

from __future__ import annotations

from urllib.parse import urlsplit

from mayabu.platforms.registry import PLATFORM_HOSTS, SUPPORTED_PLATFORMS, display_name
from mayabu_common import normalize_url

# Re-export registry maps so existing imports keep working.
__all__ = ["PLATFORM_HOSTS", "SUPPORTED_PLATFORMS", "detect_platform", "validate_product_url"]


def detect_platform(url: str) -> str:
    parts = urlsplit((url or "").strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not host:
        raise ValueError("Product URL must be a valid http or https URL")
    for platform, hosts in PLATFORM_HOSTS.items():
        if any(host == allowed or host.endswith("." + allowed) for allowed in hosts):
            return platform
    names = ", ".join(display_name(p) for p in sorted(SUPPORTED_PLATFORMS))
    raise ValueError(f"Unsupported product URL. Use one of: {names}.")


def validate_product_url(platform: str, url: str) -> str:
    platform = (platform or "").strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")
    detected = detect_platform(url)
    if detected != platform:
        raise ValueError(f"URL belongs to {detected}, not {platform}")
    normalized = normalize_url(url)
    if not normalized:
        raise ValueError("Product URL is empty after normalization")
    return normalized
