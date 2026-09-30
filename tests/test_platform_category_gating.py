"""Platform × category scheduler/readiness gating tests."""

from __future__ import annotations

from mayabu.platforms.coverage import (
    demote_category,
    discovery_allowed,
    get_coverage,
    ingestion_enabled,
    promote_category,
    public_offer_allowed,
    reset_coverage_matrix_for_tests,
    task_allowed,
)


def setup_function() -> None:
    reset_coverage_matrix_for_tests()


def teardown_function() -> None:
    reset_coverage_matrix_for_tests()


def test_amazon_production_tasks_unaffected() -> None:
    assert discovery_allowed("amazon", "laptop") is True
    assert task_allowed("amazon", "laptop", "discovery") is True
    assert public_offer_allowed("amazon", "smartphone") is True


def test_vijaysales_headphones_experimental_denied() -> None:
    assert get_coverage("vijaysales", "headphones").status == "experimental"
    assert ingestion_enabled("vijaysales", "headphones") is False
    assert discovery_allowed("vijaysales", "headphones") is False
    assert task_allowed("vijaysales", "headphones", "discovery") is False


def test_vijaysales_laptop_production_allowed() -> None:
    assert get_coverage("vijaysales", "laptop").status == "production"
    assert discovery_allowed("vijaysales", "laptop") is True
    assert task_allowed("vijaysales", "laptop", "discovery") is True


def test_vijaysales_laptop_promotable() -> None:
    demote_category("vijaysales", "camera", "experimental")
    promote_category("vijaysales", "camera", notes="live gate passed")
    assert get_coverage("vijaysales", "camera").status == "production"
    assert discovery_allowed("vijaysales", "camera") is True
    assert task_allowed("vijaysales", "camera", "discovery") is True


def test_poorvika_tv_experimental_denied() -> None:
    assert get_coverage("poorvika", "television").status == "experimental"
    assert discovery_allowed("poorvika", "television") is False
    assert task_allowed("poorvika", "television", "discovery") is False


def test_poorvika_smartphone_production_allowed() -> None:
    assert get_coverage("poorvika", "smartphone").status == "production"
    assert discovery_allowed("poorvika", "smartphone") is True
    assert task_allowed("poorvika", "smartphone", "discovery") is True


def test_poorvika_smartphone_promotable() -> None:
    demote_category("poorvika", "laptop", "experimental")
    promote_category("poorvika", "laptop", notes="PIM laptop gate")
    assert discovery_allowed("poorvika", "laptop") is True
    assert task_allowed("poorvika", "laptop", "discovery") is True


def test_jiomart_disabled_denied() -> None:
    assert get_coverage("jiomart", "laptop").status == "disabled"
    assert discovery_allowed("jiomart", "laptop") is False
    assert task_allowed("jiomart", "smartphone", "discovery") is False


def test_bajaj_blocked_denied() -> None:
    assert get_coverage("bajajelectronics", "laptop").status == "blocked"
    assert discovery_allowed("bajajelectronics", "laptop") is False
    assert task_allowed("bajajelectronics", "television", "refresh_listing") is False
