"""Amazon selected-variant identity helpers (no live network)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from mayabu.scrapers.detail.registry import _amazon_variant_identity


def test_amazon_variant_identity_reads_selected_color() -> None:
    page = AsyncMock()

    async def query_selector(sel: str):
        if "variation_color_name" in sel and "selection" in sel:
            return SimpleNamespace(inner_text=AsyncMock(return_value="Midnight"))
        return None

    page.query_selector = AsyncMock(side_effect=query_selector)
    result = asyncio.run(_amazon_variant_identity(page))
    assert result.get("color") == "Midnight"
