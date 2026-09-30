"""Regression tests for backend hardening correctness fixes."""

from __future__ import annotations

from mayabu.domain.categories.base import (
    cpu_models_compatible,
    is_weak_series_model_code,
)
from mayabu.domain.categories.laptop import LaptopAdapter
from mayabu.domain.categories.washing_machine import WashingMachineAdapter
from mayabu.domain.matching import assess_product_match
from mayabu.platforms.coverage import public_offer_allowed


def test_cpu_prefix_compatibility() -> None:
    assert cpu_models_compatible(["intel_core_i:5"], ["intel_core_i:5:13420h"])
    assert cpu_models_compatible(["intel_core_i:5:13420h"], ["intel_core_i:5"])
    assert not cpu_models_compatible(
        ["intel_core_i:5:13420h"], ["intel_core_i:5:13450hx"]
    )
    assert not cpu_models_compatible(["apple_m:4"], ["apple_m:4:pro"])
    assert cpu_models_compatible(["apple_m:4:pro"], ["apple_m:4:pro"])


def test_weak_series_model_codes() -> None:
    assert is_weak_series_model_code("15IRX9")
    assert is_weak_series_model_code("14IRU8")
    assert not is_weak_series_model_code("15-FA2197TX")
    assert not is_weak_series_model_code("FWT1310BG")
    assert not is_weak_series_model_code("SM-S921B")


def test_washer_dual_capacity_prefers_wash_kg() -> None:
    adapter = WashingMachineAdapter()
    slash = adapter.extract_specs(
        "LG WashTower 13 kg/10 kg Fully Automatic Front Load Washer Dryer FWT1310BG"
    )
    dash = adapter.extract_specs(
        "LG 13-10 kg Fully Automatic Front Loading Washing Machine FWT1310BG"
    )
    assert slash["capacity_kg"] == 13.0
    assert slash["dry_capacity_kg"] == 10.0
    assert dash["capacity_kg"] == 13.0
    assert dash["dry_capacity_kg"] == 10.0
    assert slash["load_type"] == "front_load"
    assert dash["load_type"] == "front_load"


def test_laptop_hard_conflict_uses_cpu_prefix_and_gpu() -> None:
    adapter = LaptopAdapter()
    assert not adapter.hard_conflicts(
        {"model_codes": ["15-FA2197TX"], "cpu_models": ["intel_core_i:5"], "gpu": "rtx3050", "ram_gb": 16},
        {"model_codes": ["15-FA2197TX"], "cpu_models": ["intel_core_i:5:13420h"], "gpu": "rtx3050", "ram_gb": 16},
    )
    assert "gpu" in adapter.hard_conflicts(
        {"model_codes": ["15IRX9"], "cpu_models": ["intel_core_i:5"], "gpu": "rtx3050"},
        {"model_codes": ["15IRX9"], "cpu_models": ["intel_core_i:5:13450hx"], "gpu": "rtx4050"},
    )


def test_victus_cpu_prefix_merges() -> None:
    left = {
        "title": "HP Victus 15-fa2197TX Intel Core i5 13th Gen 16GB 512GB RTX 3050",
        "category": "laptop",
        "specs": {
            "brand": "hp",
            "model_codes": ["15-FA2197TX"],
            "cpu_models": ["intel_core_i:5"],
            "gpu": "rtx3050",
            "ram_gb": 16,
            "storage_gb": 512,
            "screen_inch": 15.6,
            "family": "victus_15",
        },
    }
    right = {
        "title": "HP Victus 15 15-fa2197TX Intel Core i5-13420H 16GB 512GB RTX 3050",
        "category": "laptop",
        "specs": {
            "brand": "hp",
            "model_codes": ["15-FA2197TX"],
            "cpu_models": ["intel_core_i:5:13420h"],
            "gpu": "rtx3050",
            "ram_gb": 16,
            "storage_gb": 512,
            "screen_inch": 15.6,
            "family": "victus_15",
        },
    }
    assessment = assess_product_match(left, right)
    assert assessment.relation == "exact"
    assert assessment.merge_allowed is True


def test_weak_series_gpu_does_not_exact_merge() -> None:
    left = {
        "title": "Lenovo LOQ 15IRX9 RTX 3050",
        "category": "laptop",
        "specs": {
            "brand": "lenovo",
            "model_codes": ["15IRX9"],
            "cpu_models": ["intel_core_i:5"],
            "gpu": "rtx3050",
            "ram_gb": 16,
            "storage_gb": 512,
            "screen_inch": 15.6,
            "family": "loq_15",
        },
    }
    right = {
        "title": "Lenovo LOQ 15IRX9 RTX 4050",
        "category": "laptop",
        "specs": {
            "brand": "lenovo",
            "model_codes": ["15IRX9"],
            "cpu_models": ["intel_core_i:5:13450hx"],
            "gpu": "rtx4050",
            "ram_gb": 16,
            "storage_gb": 512,
            "screen_inch": 15.6,
            "family": "loq_15",
        },
    }
    assessment = assess_product_match(left, right)
    assert assessment.merge_allowed is False
    assert assessment.relation in {"variant", "conflict", "related"}


def test_public_offer_gating_matrix() -> None:
    assert public_offer_allowed("vijaysales", "laptop") is True
    assert public_offer_allowed("vijaysales", "tws") is False
    assert public_offer_allowed("poorvika", "smartphone") is True
    assert public_offer_allowed("poorvika", "television") is False
    assert public_offer_allowed("jiomart", "laptop") is False
    assert public_offer_allowed("amazon", "camera") is True
