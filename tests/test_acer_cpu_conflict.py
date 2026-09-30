"""Acer ALG Core5 vs Core7 must hard-conflict (no silent exact merge)."""

from __future__ import annotations

from mayabu.domain.categories.laptop import LaptopAdapter
from mayabu.domain.matching import assess_product_match


def test_acer_core5_vs_core7_hard_conflict() -> None:
    adapter = LaptopAdapter()
    core5 = adapter.extract_specs(
        "Acer ALG, Intel Core5-210H Processor, NVIDIA GeForceRTX 3050-4GB DDR6,"
        "16GB RAM/512GB SSD, FHD 15.6\", AL15G-53, Gaming Laptop"
    )
    core7 = adapter.extract_specs(
        "Acer ALG, Intel Core7-240H Processor, NVIDIA GeForce RTX 3050-6GB DDR6,"
        "16GB RAM, 512GB SSD, FHD 15.6\", Gaming Laptop"
    )
    assert core5.get("cpu_models")
    assert core7.get("cpu_models")
    assert "cpu_models" in adapter.hard_conflicts(core5, core7)

    left = {
        "title": "Acer ALG Core5-210H 16GB 512GB RTX 3050 AL15G-53",
        "category": "laptop",
        "specs": core5,
    }
    right = {
        "title": "Acer ALG Core7-240H 16GB 512GB RTX 3050",
        "category": "laptop",
        "specs": core7,
    }
    assessment = assess_product_match(left, right)
    assert assessment.merge_allowed is False
    assert assessment.relation != "exact"


def test_acer_core5_vs_i5_13420h_hard_conflict() -> None:
    adapter = LaptopAdapter()
    core5 = adapter.extract_specs("Acer ALG Intel Core5-210H 16GB 512GB RTX 3050 AL15G-53")
    i5 = adapter.extract_specs("Acer ALG 13th Gen Intel Core i5-13420H 16GB 512GB RTX 3050")
    assert "cpu_models" in adapter.hard_conflicts(core5, i5)


def test_core_i5_sku_after_generation_is_a_hard_conflict() -> None:
    adapter = LaptopAdapter()
    loq = adapter.extract_specs(
        "Lenovo LOQ Intel Core i5 12th Gen 12450H - (16 GB/512 GB SSD/Windows 11 Home/6 GB Graphics)"
    )
    ideapad = adapter.extract_specs(
        "Lenovo IdeaPad Slim 3 Intel Core i5 13th Gen 13420H - (16 GB/512 GB SSD/Windows 11 Home)"
    )
    assert "12450h" in (loq.get("cpu_series") or "")
    assert "13420h" in (ideapad.get("cpu_series") or "")
    reasons = set(adapter.hard_conflicts(loq, ideapad))
    assert "cpu_models" in reasons
    assert "family" in reasons
    assessment = assess_product_match(
        {"title": "LOQ", "category": "laptop", "specs": loq},
        {"title": "IdeaPad", "category": "laptop", "canonical_title": "IdeaPad", "specs": ideapad},
    )
    assert assessment.merge_allowed is False
