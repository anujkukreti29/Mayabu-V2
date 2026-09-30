"""Shared constants for the Mayabu backend."""

from __future__ import annotations

from mayabu.platforms.registry import platform_slugs

SUPPORTED_PLATFORMS = tuple(sorted(platform_slugs(enabled_only=True)))
# Public search remains laptop-first; ingestion accepts broader categories.
SUPPORTED_CATEGORIES = (
    "laptop",
    "smartphone",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
    "camera",
)
DEFAULT_CURRENCY = "INR"
MIN_LAPTOP_PRICE = 5_000
MAX_LAPTOP_PRICE = 600_000
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 50
