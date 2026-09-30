"""Platform × category health observations (bounded cardinality).

Tracks health for known platforms against the bounded catalog category set —
not unconstrained free-text labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from mayabu.platforms.coverage import (
    CATALOG_CATEGORIES,
    MIN_USABLE_RECORDS,
    PRODUCTION_PLATFORMS,
    get_coverage,
    meets_coverage_thresholds,
)

HealthStatus = Literal["healthy", "degraded", "partial", "empty", "blocked", "failed", "unsupported"]


@dataclass(frozen=True, slots=True)
class PlatformCategoryHealth:
    platform: str
    category: str
    status: HealthStatus
    discovered: int = 0
    accepted: int = 0
    degraded: int = 0
    rejected: int = 0
    valid_price_rate: float = 0.0
    valid_image_rate: float = 0.0
    unknown_category_rate: float = 0.0
    category_confidence_rate: float = 0.0
    duplicate_rate: float = 0.0
    reasons: tuple[str, ...] = ()
    coverage_status: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "category": self.category,
            "status": self.status,
            "discovered": self.discovered,
            "accepted": self.accepted,
            "degraded": self.degraded,
            "rejected": self.rejected,
            "valid_price_rate": round(self.valid_price_rate, 3),
            "valid_image_rate": round(self.valid_image_rate, 3),
            "unknown_category_rate": round(self.unknown_category_rate, 3),
            "category_confidence_rate": round(self.category_confidence_rate, 3),
            "duplicate_rate": round(self.duplicate_rate, 3),
            "reasons": list(self.reasons),
            "coverage_status": self.coverage_status,
        }


def score_platform_category_health(
    *,
    platform: str,
    category: str,
    discovered: int,
    accepted: int,
    degraded: int,
    rejected: int,
    valid_price_rate: float,
    valid_image_rate: float = 0.0,
    unknown_category_rate: float = 0.0,
    category_confidence_rate: float = 0.0,
    duplicate_rate: float = 0.0,
    scrape_status: str | None = None,
) -> PlatformCategoryHealth:
    coverage = get_coverage(platform, category)
    reasons: list[str] = []

    if scrape_status == "blocked":
        return PlatformCategoryHealth(
            platform=platform,
            category=category,
            status="blocked",
            discovered=discovered,
            accepted=accepted,
            degraded=degraded,
            rejected=rejected,
            valid_price_rate=valid_price_rate,
            valid_image_rate=valid_image_rate,
            unknown_category_rate=unknown_category_rate,
            category_confidence_rate=category_confidence_rate,
            duplicate_rate=duplicate_rate,
            reasons=("scrape_blocked",),
            coverage_status=coverage.status,
        )

    if coverage.status in {"unavailable", "disabled", "blocked", "unsupported"}:
        return PlatformCategoryHealth(
            platform=platform,
            category=category,
            status="unsupported",
            discovered=discovered,
            accepted=accepted,
            degraded=degraded,
            rejected=rejected,
            valid_price_rate=valid_price_rate,
            valid_image_rate=valid_image_rate,
            unknown_category_rate=unknown_category_rate,
            category_confidence_rate=category_confidence_rate,
            duplicate_rate=duplicate_rate,
            reasons=(f"coverage_{coverage.status}",),
            coverage_status=coverage.status,
        )

    if discovered == 0 or scrape_status == "empty":
        status: HealthStatus = "empty"
        reasons.append("no_products")
    elif meets_coverage_thresholds(
        discovered=discovered,
        accepted=accepted,
        valid_price_rate=valid_price_rate,
        category_confidence_rate=category_confidence_rate or (1.0 - unknown_category_rate),
        duplicate_rate=duplicate_rate,
    ):
        status = "healthy"
    elif accepted >= 1 and discovered >= 1:
        status = "partial" if accepted < MIN_USABLE_RECORDS else "degraded"
        if accepted < MIN_USABLE_RECORDS:
            reasons.append("below_min_usable_records")
        if valid_price_rate < 0.5:
            reasons.append("low_valid_price_rate")
        if unknown_category_rate > 0.4:
            reasons.append("high_unknown_category_rate")
    elif scrape_status == "failed":
        status = "failed"
        reasons.append("scrape_failed")
    else:
        status = "degraded"
        reasons.append("weak_extraction")

    return PlatformCategoryHealth(
        platform=platform,
        category=category,
        status=status,
        discovered=discovered,
        accepted=accepted,
        degraded=degraded,
        rejected=rejected,
        valid_price_rate=valid_price_rate,
        valid_image_rate=valid_image_rate,
        unknown_category_rate=unknown_category_rate,
        category_confidence_rate=category_confidence_rate,
        duplicate_rate=duplicate_rate,
        reasons=tuple(reasons),
        coverage_status=coverage.status,
    )


def bounded_health_keys(
    platforms: tuple[str, ...] = PRODUCTION_PLATFORMS,
    categories: tuple[str, ...] = CATALOG_CATEGORIES,
) -> list[tuple[str, str]]:
    """Explicit bounded (platform, category) keys — avoid metric explosion."""
    return [(p, c) for p in platforms for c in categories]


__all__ = [
    "HealthStatus",
    "PlatformCategoryHealth",
    "bounded_health_keys",
    "score_platform_category_health",
]
