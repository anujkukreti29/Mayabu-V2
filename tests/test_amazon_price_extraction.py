"""Unit tests for Amazon buybox selling-price helpers (no live network)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from mayabu.scrapers.detail.registry import _amazon_selling_price, _numeric


def test_numeric_parses_offscreen_rupee() -> None:
    assert _numeric("₹49,899.00") == 49899.0
    assert _numeric("49899") == 49899.0


def test_amazon_selling_price_prefers_price_to_pay() -> None:
    page = AsyncMock()

    async def query_selector(sel: str):
        if "priceToPay" in sel and "a-offscreen" in sel:
            return SimpleNamespace(
                inner_text=AsyncMock(return_value="₹49,899.00"),
                get_attribute=AsyncMock(return_value=None),
            )
        if "basisPrice" in sel or "a-text-price" in sel:
            return SimpleNamespace(
                inner_text=AsyncMock(return_value="₹72,990.00"),
                get_attribute=AsyncMock(return_value=None),
            )
        return None

    page.query_selector = AsyncMock(side_effect=query_selector)
    sell, mrp = asyncio.run(_amazon_selling_price(page))
    assert sell == 49899.0
    assert mrp == 72990.0


def test_amazon_selling_price_whole_fraction_fallback() -> None:
    page = AsyncMock()

    async def query_selector(sel: str):
        if "a-offscreen" in sel:
            return None
        if "a-price-whole" in sel:
            return SimpleNamespace(inner_text=AsyncMock(return_value="59,580"))
        if "a-price-fraction" in sel:
            return SimpleNamespace(inner_text=AsyncMock(return_value="00"))
        return None

    page.query_selector = AsyncMock(side_effect=query_selector)
    sell, _mrp = asyncio.run(_amazon_selling_price(page))
    assert sell == 59580.0
