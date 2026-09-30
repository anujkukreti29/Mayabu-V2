from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from mayabu_common import canonical_platform
from mayabu_refresh.amazon import scrape_amazon_refresh
from mayabu_refresh.bajajelectronics import scrape_bajajelectronics_refresh
from mayabu_refresh.croma import scrape_croma_refresh
from mayabu_refresh.flipkart import scrape_flipkart_refresh
from mayabu_refresh.jiomart import scrape_jiomart_refresh
from mayabu_refresh.models import RefreshResult
from mayabu_refresh.poorvika import scrape_poorvika_refresh
from mayabu_refresh.reliancedigital import scrape_reliancedigital_refresh
from mayabu_refresh.vijaysales import scrape_vijaysales_refresh

RefreshFn = Callable[..., Awaitable[RefreshResult]]

_REFRESH: dict[str, RefreshFn] = {
    "amazon": scrape_amazon_refresh,
    "flipkart": scrape_flipkart_refresh,
    "croma": scrape_croma_refresh,
    "reliancedigital": scrape_reliancedigital_refresh,
    "vijaysales": scrape_vijaysales_refresh,
    "jiomart": scrape_jiomart_refresh,
    "poorvika": scrape_poorvika_refresh,
    "bajajelectronics": scrape_bajajelectronics_refresh,
}


async def run_refresh_scraper(
    platform: str,
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
) -> RefreshResult:
    platform = canonical_platform(platform)
    scraper = _REFRESH.get(platform)
    if scraper is None:
        raise ValueError(f"Unsupported refresh platform: {platform}")
    return await scraper(url, headless=headless, debug=debug, artifact_dir=artifact_dir)
