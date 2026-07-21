"""Pure platform URL detection and validation shared by API and workers."""

from __future__ import annotations

from urllib.parse import urlsplit

from mayabu_common import normalize_url

PLATFORM_HOSTS: dict[str, tuple[str, ...]] = {
    "amazon": ("amazon.in", "www.amazon.in"),
    "flipkart": ("flipkart.com", "www.flipkart.com"),
    "croma": ("croma.com", "www.croma.com"),
    "reliancedigital": ("reliancedigital.in", "www.reliancedigital.in"),
}
SUPPORTED_PLATFORMS = frozenset(PLATFORM_HOSTS)


def detect_platform(url: str) -> str:
    parts = urlsplit((url or "").strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not host:
        raise ValueError("Product URL must be a valid http or https URL")
    for platform, hosts in PLATFORM_HOSTS.items():
        if any(host == allowed or host.endswith("." + allowed) for allowed in hosts):
            return platform
    raise ValueError("Unsupported product URL. Use Amazon India, Flipkart, Croma, or Reliance Digital.")


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
