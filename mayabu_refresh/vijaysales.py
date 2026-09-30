from __future__ import annotations

from pathlib import Path

from mayabu_refresh.models import RefreshResult
from mayabu_refresh.retail_common import scrape_platform_refresh

PLATFORM = "vijaysales"


async def scrape_vijaysales_refresh(
    url: str,
    *,
    headless: bool = True,
    debug: bool = False,
    artifact_dir: str | Path | None = None,
) -> RefreshResult:
    return await scrape_platform_refresh(
        PLATFORM, url, headless=headless, debug=debug, artifact_dir=artifact_dir
    )
