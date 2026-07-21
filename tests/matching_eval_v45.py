"""Tiny v4.5 matching sanity checks.

This is not the final 200-500 pair labeled set. It is a fast local guardrail for
Mayabu's new matching behavior: obvious conflicts still reject, while strong
same-product/no-model-code cases now enter review instead of being forced into a
new duplicate cluster.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mayabu_catalog import MATCH_THRESHOLD, REVIEW_THRESHOLD, score_product_match


def _listing(title: str, specs: dict) -> dict:
    return {"title": title, "title_norm": title.lower(), "category": specs.get("category", "laptop"), "specs": specs}


def _product(title: str, specs: dict) -> dict:
    return {"canonical_title": title, "title_norm": title.lower(), "category": specs.get("category", "laptop"), "specs": specs}


def test_no_model_code_strong_text_goes_to_review() -> None:
    listing = _listing(
        "HP Victus 15 Intel Core i5 13th Gen 16GB 512GB RTX 3050 Laptop",
        {"category": "laptop", "brand": "hp", "ram_gb": 16, "storage_gb": 512},
    )
    product = _product(
        "HP Victus 15 i5 13th Gen Gaming Laptop 16GB RAM 512GB SSD RTX 3050",
        {"category": "laptop", "brand": "hp", "ram_gb": 16, "storage_gb": 512},
    )
    score, evidence = score_product_match(listing, product)
    assert REVIEW_THRESHOLD <= score < MATCH_THRESHOLD, (score, evidence)
    assert evidence.get("weak_identity_review") is True, evidence


def test_storage_conflict_rejects_even_when_title_is_similar() -> None:
    listing = _listing(
        "Apple iPhone 15 128GB Black",
        {"category": "smartphone", "brand": "apple", "family": "iphone_15", "storage_gb": 128},
    )
    product = _product(
        "Apple iPhone 15 256GB Black",
        {"category": "smartphone", "brand": "apple", "family": "iphone_15", "storage_gb": 256},
    )
    score, evidence = score_product_match(listing, product)
    assert score < 0, (score, evidence)
    assert "storage" in evidence.get("reject", []), evidence


def main() -> None:
    test_no_model_code_strong_text_goes_to_review()
    test_storage_conflict_rejects_even_when_title_is_similar()
    print("Mayabu v4.5 matching sanity checks passed")


if __name__ == "__main__":
    main()
