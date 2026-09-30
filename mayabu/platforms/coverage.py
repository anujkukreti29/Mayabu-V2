"""Authoritative platform × category readiness for Mayabu.

Configured/enabled platforms are distinct from category readiness and from
temporary health (circuit breaker / scrape outcomes).

Readiness states (authoritative for ingestion & public offers):
  production   — scheduled normally; quality-gated catalog ingestion
  experimental — health/testing only; production ingestion off
  disabled     — no scheduled ingestion
  blocked      — no scheduled ingestion; health backoff applies
  unsupported  — retailer does not usefully sell / not scheduled

Legacy aliases accepted in comparisons:
  supported → production
  partial   → production (quality notes may still say incomplete)
  unavailable → unsupported
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReadinessStatus = Literal[
    "production",
    "experimental",
    "disabled",
    "blocked",
    "unsupported",
]

# Backward-compatible union used by older call sites / health reports.
CoverageStatus = Literal[
    "production",
    "experimental",
    "disabled",
    "blocked",
    "unsupported",
    "supported",  # alias of production
    "partial",  # alias of production (incomplete assortment notes)
    "unavailable",  # alias of unsupported
]

PlatformTier = Literal[
    "production",
    "partially_production",
    "experimental",
    "non_production",
]

CATALOG_CATEGORIES: tuple[str, ...] = (
    "laptop",
    "smartphone",
    "television",
    "refrigerator",
    "washing_machine",
    "tws",
    "headphones",
    "camera",
)

# Platforms that are fully or mostly production for catalog activation.
PRODUCTION_PLATFORMS: tuple[str, ...] = (
    "amazon",
    "flipkart",
    "croma",
    "reliancedigital",
)
EXPERIMENTAL_PLATFORMS: tuple[str, ...] = ("vijaysales", "poorvika")
NON_PRODUCTION_PLATFORMS: tuple[str, ...] = ("jiomart", "bajajelectronics")
ALL_TRACKED_PLATFORMS: tuple[str, ...] = (
    *PRODUCTION_PLATFORMS,
    *EXPERIMENTAL_PLATFORMS,
    *NON_PRODUCTION_PLATFORMS,
)

MIN_USABLE_RECORDS = 3
MIN_VALID_PRICE_RATE = 0.50
MIN_CATEGORY_CONFIDENCE_RATE = 0.40
MAX_DUPLICATE_RATE = 0.35


@dataclass(frozen=True, slots=True)
class CoverageCell:
    platform: str
    category: str
    status: CoverageStatus
    notes: str = ""
    ingestion_enabled: bool = False

    @property
    def readiness(self) -> ReadinessStatus:
        return normalize_readiness(self.status)


def normalize_readiness(status: str) -> ReadinessStatus:
    s = (status or "").strip().lower()
    if s in {"production", "supported", "partial"}:
        return "production"
    if s == "experimental":
        return "experimental"
    if s == "disabled":
        return "disabled"
    if s == "blocked":
        return "blocked"
    return "unsupported"


_MATRIX: dict[tuple[str, str], CoverageCell] = {}


def _cell(
    platform: str,
    category: str,
    status: CoverageStatus,
    *,
    notes: str = "",
    ingestion_enabled: bool | None = None,
) -> CoverageCell:
    readiness = normalize_readiness(status)
    enabled = ingestion_enabled
    if enabled is None:
        enabled = readiness == "production"
    # Canonicalize stored status to the five authoritative values.
    canonical: CoverageStatus = readiness
    return CoverageCell(
        platform=platform,
        category=category,
        status=canonical,
        notes=notes,
        ingestion_enabled=bool(enabled),
    )


def _seed() -> None:
    if _MATRIX:
        return

    for cat, status, notes in (
        ("laptop", "production", "Primary baseline vertical"),
        ("smartphone", "production", "Strong mobile catalog"),
        ("television", "production", "Broad TV assortment"),
        ("refrigerator", "production", "Sold; discovery noisier than laptop/phone"),
        ("washing_machine", "production", "Sold; accessory noise common"),
        ("tws", "production", "Strong earbuds catalog"),
        ("headphones", "production", "Strong headphone catalog"),
        ("camera", "production", "OPERATIONAL LIMITED: body/kit safety ok; density/gallery/challenge not READY for promotion"),
    ):
        _MATRIX[("amazon", cat)] = _cell("amazon", cat, status, notes=notes)

    for cat, status, notes in (
        ("laptop", "production", "Primary baseline vertical"),
        ("smartphone", "production", "Strong mobile catalog"),
        ("television", "production", "Broad TV assortment"),
        ("refrigerator", "production", "Sold via large appliances"),
        ("washing_machine", "production", "Sold via large appliances"),
        ("tws", "production", "Strong earbuds catalog"),
        ("headphones", "production", "Strong headphone catalog"),
        ("camera", "production", "Camera SKUs with body/kit identity rules"),
    ):
        _MATRIX[("flipkart", cat)] = _cell("flipkart", cat, status, notes=notes)

    for cat, status, notes in (
        ("laptop", "production", "Strong computing aisle"),
        ("smartphone", "production", "Core category"),
        ("television", "production", "Core category"),
        ("refrigerator", "production", "Strong appliance aisle"),
        ("washing_machine", "production", "Strong appliance aisle"),
        ("tws", "production", "Audio aisle"),
        ("headphones", "production", "Audio aisle"),
        ("camera", "production", "Carried; body/kit matching enforced"),
    ):
        _MATRIX[("croma", cat)] = _cell("croma", cat, status, notes=notes)

    for cat, status, notes in (
        ("laptop", "production", "Strong computing aisle"),
        ("smartphone", "production", "Core category"),
        ("television", "production", "Core category"),
        ("refrigerator", "production", "Strong appliance aisle"),
        ("washing_machine", "production", "Strong appliance aisle"),
        ("tws", "production", "Audio present; SKU density varies"),
        ("headphones", "production", "Audio present; SKU density varies"),
        ("camera", "production", "Carried; volume varies"),
    ):
        _MATRIX[("reliancedigital", cat)] = _cell(
            "reliancedigital", cat, status, notes=notes
        )

    # Vijay Sales — category-level; production cells set after repeated live gates.
    # Defaults experimental; promote selectively via set_coverage / seed updates.
    vs_production = {
        "laptop": "Repeated /c/laptops PLP: priced+imaged+native ID; category accuracy high",
        "smartphone": "Repeated /c/mobiles PLP passed price/image/category gates",
        "television": "/c/televisions PLP passed bounded live gate",
        "refrigerator": "/c/refrigerators PLP strong; brand-query price intermittency monitored",
        "washing_machine": "Repeated /c/washing-machines PLP passed gates",
        "camera": "/c/camera PLP yields cameras with prices; Instax unknown-category noise tolerated",
    }
    vs_notes = {
        "laptop": vs_production["laptop"],
        "smartphone": vs_production["smartphone"],
        "television": vs_production["television"],
        "refrigerator": vs_production["refrigerator"],
        "washing_machine": vs_production["washing_machine"],
        "tws": "No clean dedicated TWS PLP; earphones/neckbands mapped separately",
        "headphones": "Cross-sell pollution historically; keep experimental until audio filter proven stable",
        "camera": vs_production["camera"],
    }
    for cat in CATALOG_CATEGORIES:
        if cat in vs_production:
            _MATRIX[("vijaysales", cat)] = _cell(
                "vijaysales",
                cat,
                "production",
                notes=vs_notes[cat],
                ingestion_enabled=True,
            )
        else:
            _MATRIX[("vijaysales", cat)] = _cell(
                "vijaysales",
                cat,
                "experimental",
                notes=vs_notes.get(cat, "Experimental"),
                ingestion_enabled=False,
            )

    # Poorvika — promote laptop/smartphone only after repeated PIM gates.
    pv_production = {
        "laptop": "Repeated /laptops/page + PIM group JSON; titles/images/prices",
        "smartphone": "Repeated /mobile-and-accessories/page + PIM; priced+imaged",
    }
    pv_notes = {
        "laptop": pv_production["laptop"],
        "smartphone": pv_production["smartphone"],
        "television": "Coarse /tv-audio mix — experimental despite occasional clean samples",
        "refrigerator": "Coarse /home-appliances mix",
        "washing_machine": "Coarse /home-appliances mix",
        "tws": "Coarse /tv-audio mix",
        "headphones": "Coarse /tv-audio mix",
        "camera": "Coarse /smart-technology mixes wearables",
    }
    for cat in CATALOG_CATEGORIES:
        if cat in pv_production:
            _MATRIX[("poorvika", cat)] = _cell(
                "poorvika",
                cat,
                "production",
                notes=pv_notes[cat],
                ingestion_enabled=True,
            )
        else:
            _MATRIX[("poorvika", cat)] = _cell(
                "poorvika",
                cat,
                "experimental",
                notes=pv_notes.get(cat, "Experimental"),
                ingestion_enabled=False,
            )

    for platform in NON_PRODUCTION_PLATFORMS:
        for cat in CATALOG_CATEGORIES:
            status: CoverageStatus = (
                "blocked" if platform == "bajajelectronics" else "disabled"
            )
            _MATRIX[(platform, cat)] = _cell(
                platform,
                cat,
                status,
                notes=(
                    "Bot challenge / blocked"
                    if platform == "bajajelectronics"
                    else "No reliable public product payload (Algolia shell / empty discovery)"
                ),
                ingestion_enabled=False,
            )


def promote_category(
    platform: str,
    category: str,
    *,
    notes: str | None = None,
) -> CoverageCell:
    """Mark a platform×category as production (ingestion enabled). Test/seed helper."""
    _seed()
    cell = _cell(
        platform,
        category,
        "production",
        notes=notes or get_coverage(platform, category).notes,
        ingestion_enabled=True,
    )
    _MATRIX[(platform, category)] = cell
    return cell


def demote_category(
    platform: str,
    category: str,
    status: CoverageStatus = "experimental",
    *,
    notes: str | None = None,
) -> CoverageCell:
    _seed()
    cell = _cell(
        platform,
        category,
        status,
        notes=notes or get_coverage(platform, category).notes,
        ingestion_enabled=False,
    )
    _MATRIX[(platform, category)] = cell
    return cell


def platform_tier(platform: str) -> PlatformTier:
    _seed()
    cells = [get_coverage(platform, c) for c in CATALOG_CATEGORIES]
    prod = sum(1 for c in cells if c.readiness == "production")
    if prod == len(CATALOG_CATEGORIES):
        return "production"
    if prod > 0:
        return "partially_production"
    if platform in EXPERIMENTAL_PLATFORMS:
        return "experimental"
    return "non_production"


def get_coverage(platform: str, category: str) -> CoverageCell:
    _seed()
    key = (platform, category)
    if key in _MATRIX:
        return _MATRIX[key]
    return CoverageCell(
        platform=platform,
        category=category,
        status="unsupported",
        notes="Not in catalog activation matrix",
        ingestion_enabled=False,
    )


def coverage_matrix(
    *,
    platforms: tuple[str, ...] | None = None,
    categories: tuple[str, ...] | None = None,
) -> list[CoverageCell]:
    _seed()
    plats = platforms or PRODUCTION_PLATFORMS
    cats = categories or CATALOG_CATEGORIES
    return [get_coverage(p, c) for p in plats for c in cats]


def full_coverage_matrix() -> list[CoverageCell]:
    return coverage_matrix(platforms=ALL_TRACKED_PLATFORMS)


def ingestion_enabled(platform: str, category: str) -> bool:
    return get_coverage(platform, category).ingestion_enabled


def discovery_allowed(platform: str, category: str) -> bool:
    """Production discovery/scheduling allowed for this pair."""
    cell = get_coverage(platform, category)
    return cell.ingestion_enabled and cell.readiness == "production"


def public_offer_allowed(platform: str, category: str) -> bool:
    """Whether offers from this pair may surface in public best-price/search."""
    return discovery_allowed(platform, category)


def task_allowed(platform: str, category: str | None, task_type: str) -> bool:
    """Scheduler gate combining readiness with task type.

    Refresh of known listings requires production category when category known.
    Discovery requires production category inferred from query/metadata.
    Experimental/disabled/blocked/unsupported pairs are denied for production work.
    """
    if category:
        cell = get_coverage(platform, category)
        if cell.readiness in {"disabled", "blocked", "unsupported"}:
            return False
        if cell.readiness == "experimental":
            return False
        if not cell.ingestion_enabled:
            return False
        return True
    # Unknown category: allow only for fully-production platforms' refresh of
    # already-ingested listings is handled by caller passing category from listing.
    if platform in PRODUCTION_PLATFORMS:
        return str(task_type).startswith("refresh")
    return False


def production_category_targets() -> dict[str, tuple[str, ...]]:
    """Categories enabled for production ingestion per platform (any tracked)."""
    _seed()
    out: dict[str, list[str]] = {}
    for cell in full_coverage_matrix():
        if cell.ingestion_enabled:
            out.setdefault(cell.platform, []).append(cell.category)
    return {k: tuple(v) for k, v in out.items()}


def production_discovery_pairs() -> list[tuple[str, str]]:
    """(platform, category) pairs eligible for scheduled discovery."""
    return [
        (cell.platform, cell.category)
        for cell in full_coverage_matrix()
        if cell.ingestion_enabled and cell.readiness == "production"
    ]


def smoke_probe_queries() -> list[tuple[str, str, str]]:
    return [
        ("amazon", "laptop", "laptop"),
        ("amazon", "smartphone", "samsung galaxy s24"),
        ("amazon", "television", "samsung 55 inch tv"),
        ("amazon", "tws", "samsung galaxy buds"),
        ("flipkart", "laptop", "laptop"),
        ("flipkart", "smartphone", "iphone 15"),
        ("flipkart", "television", "lg oled tv"),
        ("flipkart", "tws", "oneplus buds"),
        ("croma", "laptop", "laptop"),
        ("croma", "smartphone", "oneplus smartphone"),
        ("croma", "television", "sony bravia"),
        ("croma", "refrigerator", "lg 260l refrigerator"),
        ("croma", "washing_machine", "lg 8kg front load"),
        ("croma", "tws", "boat tws"),
        ("croma", "headphones", "sony headphones"),
        ("reliancedigital", "laptop", "laptop"),
        ("reliancedigital", "smartphone", "samsung galaxy"),
        ("reliancedigital", "television", "sony bravia"),
        ("reliancedigital", "refrigerator", "samsung double door refrigerator"),
        ("reliancedigital", "washing_machine", "samsung top load washing machine"),
        ("amazon", "camera", "sony alpha mirrorless"),
        ("croma", "camera", "canon mirrorless"),
        ("vijaysales", "laptop", "laptop"),
        ("vijaysales", "refrigerator", "refrigerator"),
        ("vijaysales", "washing_machine", "washing machine"),
        ("vijaysales", "camera", "camera"),
        ("poorvika", "laptop", "laptop"),
        ("poorvika", "smartphone", "smartphone"),
    ]


def meets_coverage_thresholds(
    *,
    discovered: int,
    accepted: int,
    valid_price_rate: float,
    category_confidence_rate: float,
    duplicate_rate: float,
) -> bool:
    if discovered < MIN_USABLE_RECORDS or accepted < MIN_USABLE_RECORDS:
        return False
    if valid_price_rate < MIN_VALID_PRICE_RATE:
        return False
    if category_confidence_rate < MIN_CATEGORY_CONFIDENCE_RATE:
        return False
    if duplicate_rate > MAX_DUPLICATE_RATE:
        return False
    return True


def reset_coverage_matrix_for_tests() -> None:
    """Clear seeded matrix so tests can re-seed after promotions."""
    _MATRIX.clear()


__all__ = [
    "ALL_TRACKED_PLATFORMS",
    "CATALOG_CATEGORIES",
    "CoverageCell",
    "CoverageStatus",
    "EXPERIMENTAL_PLATFORMS",
    "MAX_DUPLICATE_RATE",
    "MIN_CATEGORY_CONFIDENCE_RATE",
    "MIN_USABLE_RECORDS",
    "MIN_VALID_PRICE_RATE",
    "NON_PRODUCTION_PLATFORMS",
    "PRODUCTION_PLATFORMS",
    "PlatformTier",
    "ReadinessStatus",
    "coverage_matrix",
    "demote_category",
    "discovery_allowed",
    "full_coverage_matrix",
    "get_coverage",
    "ingestion_enabled",
    "meets_coverage_thresholds",
    "normalize_readiness",
    "platform_tier",
    "production_category_targets",
    "production_discovery_pairs",
    "promote_category",
    "public_offer_allowed",
    "reset_coverage_matrix_for_tests",
    "smoke_probe_queries",
    "task_allowed",
]
