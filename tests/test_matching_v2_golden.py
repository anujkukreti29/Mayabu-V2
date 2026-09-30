"""Matching V2 golden-set regression tests."""

from __future__ import annotations

from mayabu.domain.matching import assess_product_match
from mayabu.domain.matching_golden import golden_pairs
from mayabu.domain.matching_noise import strip_matching_noise
from mayabu.domain.categories.registry import detect_category_result


def _as_listing(pair: dict, side: str) -> dict:
    node = pair[side]
    return {
        "title": node["title"],
        "category": pair["category"],
        "specs": {**node.get("specs", {}), "category": pair["category"]},
    }


def test_golden_pairs_no_false_exact() -> None:
    false_exact = []
    misses = []
    for pair in golden_pairs():
        left = _as_listing(pair, "left")
        right = _as_listing(pair, "right")
        assessment = assess_product_match(left, right)
        expected = pair["expected"]
        if expected != "exact" and assessment.relation == "exact" and assessment.merge_allowed:
            false_exact.append((pair["id"], assessment.relation, assessment.evidence))
        if expected == "exact" and not (assessment.relation == "exact" and assessment.merge_allowed):
            misses.append((pair["id"], assessment.relation, assessment.score, assessment.evidence.get("identity_rule")))
        if expected in {"variant", "conflict"} and assessment.merge_allowed:
            false_exact.append((pair["id"], f"merged_on_{expected}", assessment.evidence))
    assert not false_exact, false_exact
    # Exact recall on curated set should be strong; allow documenting misses.
    assert len(misses) <= 2, misses


def test_marketing_noise_stripped() -> None:
    cleaned = strip_matching_noise(
        "Sony WH-1000XM5 Wireless Headphones Best Seller No Cost EMI Free Delivery"
    )
    assert "best seller" not in cleaned.lower()
    assert "emi" not in cleaned.lower()
    assert "WH-1000XM5" in cleaned or "WH" in cleaned


def test_golden_pairs_cover_all_public_categories() -> None:
    categories = {pair["category"] for pair in golden_pairs()}
    required = {
        "smartphone",
        "laptop",
        "television",
        "refrigerator",
        "washing_machine",
        "camera",
        "headphones",
        "tws",
    }
    assert required <= categories
    assert len(golden_pairs()) >= 100


def test_golden_benchmark_metrics_zero_false_exact() -> None:
    from mayabu.domain.matching_golden import score_golden

    report = score_golden()
    required = {
        "smartphone",
        "laptop",
        "television",
        "refrigerator",
        "washing_machine",
        "camera",
        "headphones",
        "tws",
    }
    assert report["sample_count"] >= 100
    assert report["false_exact_merges"] == 0
    assert report["exact_precision"] == 1.0
    assert report["scope"] == "curated_benchmark_only"
    assert report["variant_correctness"] == 1.0
    assert report["conflict_correctness"] == 1.0
    assert required <= set(report["category_counts"])


def test_camera_lens_accessory_not_camera() -> None:
    det = detect_category_result(title="Canon EF 50mm f/1.8 STM camera lens")
    assert det.category == "accessory"


def test_camera_body_detection() -> None:
    det = detect_category_result(title="Sony Alpha ILCE-7M4 Mirrorless Camera Body Only")
    assert det.category == "camera"


def test_candidate_soft_bound_constant() -> None:
    from mayabu.domain import matching

    assert matching._MAX_CANDIDATE_SOFT_BOUND <= 128
