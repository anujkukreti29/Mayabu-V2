"""Authoritative Mayabu retail platform registry.

ONE scraper implementation per platform. Category understanding lives in
normalizers/matchers, not duplicated platform scrapers.

Adding a ninth retailer should primarily mean:
1. one registry entry
2. discovery + refresh modules
3. optional detail selector fallbacks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class PlatformInfo:
    slug: str
    display_name: str
    hosts: tuple[str, ...]
    base_url: str
    enabled: bool = True
    discovery_cap: int = 1
    search_path_template: str = "/search/{query}"
    product_link_pattern: str = r"/p/"
    native_id_patterns: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


_PLATFORMS: tuple[PlatformInfo, ...] = (
    PlatformInfo(
        slug="amazon",
        display_name="Amazon India",
        hosts=("amazon.in", "www.amazon.in"),
        base_url="https://www.amazon.in",
        discovery_cap=1,
        search_path_template="/s?k={query}&page={page}",
        product_link_pattern=r"/(?:dp|gp/product)/[A-Za-z0-9]{10}",
        native_id_patterns=(r"/dp/([A-Za-z0-9]{10})",),
        aliases=("amazonindia", "amzn"),
    ),
    PlatformInfo(
        slug="flipkart",
        display_name="Flipkart",
        hosts=("flipkart.com", "www.flipkart.com"),
        base_url="https://www.flipkart.com",
        discovery_cap=2,
        search_path_template="/search?q={query}&page={page}",
        product_link_pattern=r"/p/|pid=",
        native_id_patterns=(r"[?&]pid=([A-Za-z0-9]+)", r"/p/(ITM[A-Za-z0-9]+)"),
    ),
    PlatformInfo(
        slug="croma",
        display_name="Croma",
        hosts=("croma.com", "www.croma.com"),
        base_url="https://www.croma.com",
        discovery_cap=1,
        search_path_template="/search/?q={query}",
        product_link_pattern=r"/p/\d{4,12}",
        native_id_patterns=(r"/p/(\d{4,12})",),
    ),
    PlatformInfo(
        slug="reliancedigital",
        display_name="Reliance Digital",
        hosts=("reliancedigital.in", "www.reliancedigital.in"),
        base_url="https://www.reliancedigital.in",
        discovery_cap=1,
        search_path_template="/search?q={query}",
        product_link_pattern=r"/p/|/product/",
        native_id_patterns=(r"/p/(\d{4,12})", r"-(\d{6,12})(?:$|\?)"),
        aliases=("reliance", "reliance_digital"),
    ),
    PlatformInfo(
        slug="vijaysales",
        display_name="Vijay Sales",
        hosts=("vijaysales.com", "www.vijaysales.com"),
        base_url="https://www.vijaysales.com",
        discovery_cap=1,
        search_path_template="/search?q={query}&page={page}",
        product_link_pattern=r"/p/(?:P?\d+/)?\d+",
        native_id_patterns=(r"/p/(?:P?\d+/)?(\d{4,12})", r"/p/P?(\d{4,12})"),
        aliases=("vijay_sales", "vijay"),
    ),
    PlatformInfo(
        slug="jiomart",
        display_name="JioMart",
        hosts=("jiomart.com", "www.jiomart.com"),
        base_url="https://www.jiomart.com",
        discovery_cap=1,
        search_path_template="/search/{query}",
        product_link_pattern=r"/p/|/product/",
        native_id_patterns=(r"/(\d{6,12})(?:$|\?)", r"/product/[^/]+-(\d{5,12})(?:$|\?)"),
        aliases=("jio_mart", "jio"),
    ),
    PlatformInfo(
        slug="poorvika",
        display_name="Poorvika",
        hosts=("poorvika.com", "www.poorvika.com"),
        base_url="https://www.poorvika.com",
        discovery_cap=1,
        search_path_template="/search?q={query}",
        product_link_pattern=r"/p(?:$|\?|/)",
        native_id_patterns=(r"/([a-z0-9\-]+)/p(?:$|\?)",),
        aliases=("poorvikamobiles",),
    ),
    PlatformInfo(
        slug="bajajelectronics",
        display_name="Bajaj Electronics",
        hosts=("bajajelectronics.com", "www.bajajelectronics.com"),
        base_url="https://www.bajajelectronics.com",
        discovery_cap=1,
        search_path_template="/search?q={query}",
        product_link_pattern=r"^https?://(?:www\.)?bajajelectronics\.com/[a-z0-9\-]+$",
        native_id_patterns=(r"bajajelectronics\.com/([a-z0-9\-]+)(?:$|\?)",),
        aliases=("bajaj_electronics", "bajaj"),
    ),
)

_BY_SLUG: dict[str, PlatformInfo] = {p.slug: p for p in _PLATFORMS}
_ALIAS_TO_SLUG: dict[str, str] = {}
for _platform in _PLATFORMS:
    _ALIAS_TO_SLUG[_platform.slug] = _platform.slug
    for _alias in _platform.aliases:
        _ALIAS_TO_SLUG[_alias.replace(" ", "").replace("-", "").lower()] = _platform.slug


def all_platforms(*, enabled_only: bool = True) -> tuple[PlatformInfo, ...]:
    if enabled_only:
        return tuple(p for p in _PLATFORMS if p.enabled)
    return _PLATFORMS


def platform_slugs(*, enabled_only: bool = True) -> frozenset[str]:
    return frozenset(p.slug for p in all_platforms(enabled_only=enabled_only))


def get_platform(slug: str) -> PlatformInfo | None:
    return _BY_SLUG.get(canonical_platform_slug(slug))


def canonical_platform_slug(source: str) -> str:
    raw = (source or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if not raw:
        return "unknown"
    return _ALIAS_TO_SLUG.get(raw, raw if raw in _BY_SLUG else raw)


def display_name(slug: str) -> str:
    info = get_platform(slug)
    return info.display_name if info else slug


def platform_hosts() -> dict[str, tuple[str, ...]]:
    return {p.slug: p.hosts for p in all_platforms(enabled_only=False)}


def product_source_abbrev(slug: str) -> str:
    mapping = {
        "amazon": "AMAZON",
        "flipkart": "FLIPKART",
        "croma": "CROMA",
        "reliancedigital": "RELIANCE",
        "vijaysales": "VIJAY",
        "jiomart": "JIO",
        "poorvika": "POORVIKA",
        "bajajelectronics": "BAJAJ",
    }
    return mapping.get(canonical_platform_slug(slug), canonical_platform_slug(slug).upper()[:8])


def iter_enabled_slugs() -> Iterable[str]:
    return (p.slug for p in all_platforms(enabled_only=True))


# Stable exports used across the codebase.
PLATFORMS = platform_slugs(enabled_only=True)
PLATFORM_HOSTS = platform_hosts()
SUPPORTED_PLATFORMS = PLATFORMS
