"""Bounded multi-product comparison endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Query

from mayabu.api.serializers import serialize_product
from mayabu.search.category_registry import get_search_category
from mayabu.search.search_repository import get_products_by_ids, get_public_offer_counts

router = APIRouter(prefix="/api", tags=["compare"])

MAX_COMPARE_IDS = 4


def _parse_ids(raw: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for part in (raw or "").split(","):
        pid = part.strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
        if len(out) >= MAX_COMPARE_IDS:
            break
    return out


def _serialize_compare_row(row: dict, offer_count: int) -> dict:
    payload = serialize_product(row)
    specs = payload.get("specs") if isinstance(payload.get("specs"), dict) else {}
    payload["family"] = row.get("family") or specs.get("family")
    codes = specs.get("model_codes")
    payload["model_codes"] = codes if isinstance(codes, list) else []
    payload["offer_count"] = int(offer_count or payload.get("platform_count") or 0)
    return payload


@router.get("/compare")
def compare_products(
    ids: str = Query(default="", description="Comma-separated product IDs (max 4)"),
) -> dict:
    requested = _parse_ids(ids)
    if not requested:
        return {
            "products": [],
            "category": None,
            "requested_ids": [],
            "missing_ids": [],
            "skipped": [],
            "warnings": [],
        }

    rows_by_id = get_products_by_ids(requested)
    offer_counts = get_public_offer_counts(list(rows_by_id.keys()))

    products: list[dict] = []
    skipped: list[dict] = []
    missing_ids: list[str] = []
    category: str | None = None
    warnings: list[str] = []

    for pid in requested:
        row = rows_by_id.get(pid)
        if not row:
            missing_ids.append(pid)
            continue
        cat = str(row.get("category") or "").lower()
        info = get_search_category(cat)
        if not info or not info.public_search_enabled:
            skipped.append({"id": pid, "reason": "unsupported_category"})
            continue
        if category is None:
            category = cat
        elif cat != category:
            skipped.append({"id": pid, "reason": "category_mismatch", "category": cat})
            warnings.append("category_mismatch")
            continue
        products.append(_serialize_compare_row(row, offer_counts.get(pid, 0)))

    # Deduplicate warning labels.
    warnings = sorted(set(warnings))
    return {
        "products": products,
        "category": category,
        "requested_ids": requested,
        "missing_ids": missing_ids,
        "skipped": skipped,
        "warnings": warnings,
    }


__all__ = ["MAX_COMPARE_IDS", "router"]
