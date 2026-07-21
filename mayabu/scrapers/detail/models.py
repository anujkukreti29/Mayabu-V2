from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

DetailStatus = Literal["success", "partial", "blocked", "not_found", "failed"]


@dataclass(slots=True)
class DetailProduct:
    platform: str
    url: str
    canonical_url: str
    title: str | None = None
    native_id: str | None = None
    current_price: float | None = None
    mrp: float | None = None
    currency: str = "INR"
    image_url: str | None = None
    availability: str | None = None
    seller_name: str | None = None
    rating: float | None = None
    review_count: int | None = None
    specs: dict[str, Any] = field(default_factory=dict)
    status: DetailStatus = "failed"
    warnings: list[str] = field(default_factory=list)
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_raw_listing(self, query: str | None = None) -> dict[str, Any]:
        discount = None
        if self.current_price and self.mrp and self.mrp > self.current_price:
            discount = round((1 - self.current_price / self.mrp) * 100, 2)
        return {
            "platform": self.platform,
            "source": self.platform,
            "query": query or self.title or "laptop",
            "title": self.title,
            "link": self.canonical_url or self.url,
            "native_id": self.native_id,
            "currentPrice": self.current_price,
            "maxRetailPrice": self.mrp,
            "price": self.current_price,
            "mrp": self.mrp,
            "discount_pct": discount,
            "currency": self.currency,
            "image": self.image_url,
            "seller_name": self.seller_name,
            "stock_status": self.availability,
            "specs": self.specs,
            "scraped_at": self.scraped_at,
            "detail_evidence": self.evidence,
        }
