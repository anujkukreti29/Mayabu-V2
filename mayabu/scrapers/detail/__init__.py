"""Direct product detail-page ingestion."""

from .models import DetailProduct
from .registry import detect_platform, scrape_product_detail

__all__ = ["DetailProduct", "detect_platform", "scrape_product_detail"]
