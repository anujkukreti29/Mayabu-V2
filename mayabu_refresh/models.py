from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

PageStatus = Literal["success", "partial", "failed", "blocked", "captcha", "not_found", "unknown"]
StockStatus = Literal["in_stock", "out_of_stock", "coming_soon", "unknown"]


@dataclass(slots=True)
class RefreshResult:
    """Internal result from a product-detail price refresh scraper.

    Public/CLI output is intentionally minimal: current_price, mrp and
    discount_percent only. Extra fields remain internal for DB compatibility and
    diagnostics, but refresh scrapers should not scrape title/image/stock in the
    MVP price-refresh path.
    """

    current_price: int | None = None
    mrp: int | None = None
    discount_percent: float | None = None

    # Internal compatibility/diagnostic fields. Hidden from as_dict().
    title: str | None = None
    effective_price: int | None = None
    currency: str = "INR"
    stock_status: StockStatus = "unknown"
    stock_text: str | None = None
    stock_reason: str | None = None
    stock_confidence: str | None = None
    page_status: PageStatus = "unknown"
    warnings: list[str] = field(default_factory=list)
    raw_price_text: str | None = None
    raw_mrp_text: str | None = None
    raw_effective_price_text: str | None = None
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def as_dict(self) -> dict[str, Any]:
        """Clean price-refresh output used by run_refresh_price.py and callers."""
        return {
            "current_price": self.current_price,
            "mrp": self.mrp,
            "discount_percent": self.discount_percent,
        }

    def diagnostics_dict(self) -> dict[str, Any]:
        """Internal details for logs/admin diagnostics, not public product data."""
        return asdict(self)

    @classmethod
    def failed(cls, message: str, page_status: PageStatus = "failed") -> "RefreshResult":
        return cls(page_status=page_status, warnings=[message])
