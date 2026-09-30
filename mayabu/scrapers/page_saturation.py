"""Natural pagination stops for healthy retailer discovery.

The emergency page ceiling is a safety limit. Discovery is expected to stop
earlier: empty page, retailer last page, a repeated page, or three pages that
add no new retailer-native listing ids.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field

EMERGENCY_PAGE = 40
NO_NEW_PAGE_LIMIT = 3
DEEP_PLATFORMS = frozenset({"flipkart", "reliancedigital"})

_RUN: contextvars.ContextVar["PageRun | None"] = contextvars.ContextVar(
    "mayabu_page_run", default=None
)


@dataclass
class PageRun:
    pages_fetched: int = 0
    last_page: int = 0
    new_ids: int = 0
    duplicate_ids: int = 0
    consecutive_no_new: int = 0
    stop_reason: str = ""
    seen: set[str] = field(default_factory=set)
    previous_page: frozenset[str] | None = None

    def as_dict(self) -> dict[str, int | str]:
        return {
            "pages_fetched": self.pages_fetched,
            "last_page": self.last_page,
            "new_ids": self.new_ids,
            "duplicate_ids": self.duplicate_ids,
            "consecutive_no_new": self.consecutive_no_new,
            "stop_reason": self.stop_reason,
        }


def begin_page_run() -> PageRun:
    run = PageRun()
    _RUN.set(run)
    return run


def current_page_run() -> PageRun | None:
    return _RUN.get()


def mark_stop(reason: str) -> str:
    run = _RUN.get()
    if run is not None and reason and not run.stop_reason:
        run.stop_reason = reason
    return reason


def observe_page(page_no: int, native_ids: list[str]) -> str | None:
    """Record one fetched page. Return a stop reason when pagination should end."""
    run = _RUN.get()
    if run is None:
        run = begin_page_run()
    ids = [str(item).strip() for item in native_ids if str(item or "").strip()]
    run.pages_fetched += 1
    run.last_page = int(page_no)
    if not ids:
        run.consecutive_no_new += 1
        run.stop_reason = "empty_page"
        return run.stop_reason
    page_set = frozenset(ids)
    if run.previous_page is not None and page_set == run.previous_page:
        run.stop_reason = "repeated_page"
        return run.stop_reason
    fresh = [item for item in ids if item not in run.seen]
    run.duplicate_ids += len(ids) - len(fresh)
    run.new_ids += len(fresh)
    run.seen.update(fresh)
    run.previous_page = page_set
    if fresh:
        run.consecutive_no_new = 0
    else:
        run.consecutive_no_new += 1
        if run.consecutive_no_new >= NO_NEW_PAGE_LIMIT:
            run.stop_reason = "consecutive_no_new"
            return run.stop_reason
    if int(page_no) >= EMERGENCY_PAGE:
        run.stop_reason = "emergency_ceiling"
        return run.stop_reason
    return None


def finish_page_run() -> PageRun | None:
    run = _RUN.get()
    if run is not None and run.pages_fetched and not run.stop_reason:
        run.stop_reason = "page_budget"
    return run


def natural_stop(reason: str) -> bool:
    return reason in {
        "empty_page",
        "repeated_page",
        "consecutive_no_new",
        "retailer_last_page",
        "emergency_ceiling",
        "end_of_results",
    }


def ids_from_records(platform: str, records: list[dict]) -> list[str]:
    from mayabu_common import extract_native_id

    found: list[str] = []
    for raw in records or []:
        if not isinstance(raw, dict):
            continue
        native = str(raw.get("native_id") or raw.get("productId") or raw.get("pid") or "").strip()
        url = str(raw.get("link") or raw.get("url") or raw.get("listing_url") or "")
        if not native and url:
            native = extract_native_id(platform, url, None) or ""
        if not native and url:
            native = url.split("?")[0]
        if native:
            found.append(native)
    return found
