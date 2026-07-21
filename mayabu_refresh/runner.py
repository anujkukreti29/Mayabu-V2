from __future__ import annotations

from pathlib import Path

from mayabu_common import canonical_platform
from mayabu_refresh.amazon import scrape_amazon_refresh
from mayabu_refresh.croma import scrape_croma_refresh
from mayabu_refresh.flipkart import scrape_flipkart_refresh
from mayabu_refresh.models import RefreshResult
from mayabu_refresh.reliancedigital import scrape_reliancedigital_refresh


async def run_refresh_scraper(
    platform: str,
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
) -> RefreshResult:
    platform = canonical_platform(platform)
    if platform == "amazon":
        return await scrape_amazon_refresh(url, headless=headless, debug=debug, artifact_dir=artifact_dir)
    if platform == "flipkart":
        return await scrape_flipkart_refresh(url, headless=headless, debug=debug, artifact_dir=artifact_dir)
    if platform == "croma":
        return await scrape_croma_refresh(url, headless=headless, debug=debug, artifact_dir=artifact_dir)
    if platform == "reliancedigital":
        return await scrape_reliancedigital_refresh(url, headless=headless, debug=debug, artifact_dir=artifact_dir)
    raise ValueError(f"Unsupported refresh platform: {platform}")
