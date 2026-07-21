"""Mayabu product-detail refresh scrapers.

Refresh scrapers open known product-detail URLs and return a common,
minimal pricing schema. Discovery/search scrapers remain separate.
"""

from mayabu_refresh.models import RefreshResult
from mayabu_refresh.runner import run_refresh_scraper

__all__ = ["RefreshResult", "run_refresh_scraper"]
