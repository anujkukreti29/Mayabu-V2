"""Reusable verification provider chain.

Provider order is intentionally cheap-to-expensive:
1. bounded HTTP/structured metadata,
2. existing Playwright detail refresher.

An official merchant/affiliate feed can be inserted before the HTTP provider
later without changing API, queue, worker, or persistence code.
"""

from __future__ import annotations

from dataclasses import dataclass

from mayabu.core.config import AppSettings
from mayabu.verification.lightweight import fetch_lightweight
from mayabu_db.scraper_runner import run_refresh_scraper
from mayabu_refresh.models import RefreshResult


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    result: RefreshResult
    source: str
    fallback_used: bool


async def verify_listing(platform: str, url: str, settings: AppSettings) -> VerificationOutcome:
    lightweight = await fetch_lightweight(platform, url, settings.live_verify_lightweight_timeout_seconds)
    if lightweight.current_price is not None or (
        lightweight.stock_status == "out_of_stock" and lightweight.page_status in {"success", "partial"}
    ):
        return VerificationOutcome(lightweight, "lightweight", False)

    browser = await run_refresh_scraper(platform, url, headless=True, debug=False)
    return VerificationOutcome(browser, "playwright", True)
