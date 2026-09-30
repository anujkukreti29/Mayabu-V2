from mayabu.scheduler.discovery_cursor import MAX_ROTATION_PAGE, start_page_from_metadata
from mayabu.scrapers.page_saturation import (
    EMERGENCY_PAGE,
    NO_NEW_PAGE_LIMIT,
    begin_page_run,
    current_page_run,
    natural_stop,
    observe_page,
)


def test_resume_past_the_old_page_eight_ceiling() -> None:
    assert EMERGENCY_PAGE == MAX_ROTATION_PAGE
    assert EMERGENCY_PAGE >= 30
    assert start_page_from_metadata({"cursor": {"last_page": 8}}) == 9
    assert start_page_from_metadata({"cursor": {"last_page": 17}}) == 18
    assert start_page_from_metadata({"cursor": {"last_page": EMERGENCY_PAGE}}) == 1


def test_three_pages_with_no_new_native_ids_stop() -> None:
    begin_page_run()
    assert observe_page(1, ["a", "b"]) is None
    assert observe_page(2, ["a"]) is None
    assert observe_page(3, ["b"]) is None
    assert observe_page(4, ["a", "b"]) == "consecutive_no_new"
    assert NO_NEW_PAGE_LIMIT == 3


def test_repeated_page_and_empty_page_stop() -> None:
    begin_page_run()
    assert observe_page(1, ["a"]) is None
    assert observe_page(2, ["a"]) == "repeated_page"
    begin_page_run()
    assert observe_page(9, []) == "empty_page"
    assert natural_stop("empty_page")
    assert natural_stop("retailer_last_page")
    assert natural_stop("page_budget") is False


def test_emergency_ceiling_stops_on_that_page() -> None:
    run = begin_page_run()
    reason = observe_page(EMERGENCY_PAGE, ["fresh-id"])
    assert reason == "emergency_ceiling"
    assert run.last_page == EMERGENCY_PAGE


def test_tracker_counts_new_and_duplicate_ids() -> None:
    begin_page_run()
    observe_page(1, ["a", "b"])
    observe_page(2, ["b", "c"])
    run = current_page_run()
    assert run is not None
    assert run.new_ids == 3
    assert run.duplicate_ids == 1
