"""Unit tests for Price Watch validation and popular-search privacy thresholds."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mayabu.api.wishlist_routes import WatchBody
from mayabu.domain.price_watch import update_watch


def test_watch_body_rejects_non_positive_and_huge_targets() -> None:
    with pytest.raises(ValidationError):
        WatchBody(target_price=0, notify_on_drop=True)
    with pytest.raises(ValidationError):
        WatchBody(target_price=-10, notify_on_drop=True)
    with pytest.raises(ValidationError):
        WatchBody(target_price=10_000_001, notify_on_drop=False)
    ok = WatchBody(target_price=49_999.5, notify_on_drop=False)
    assert ok.target_price == 49_999.5


def test_update_watch_rejects_out_of_range_before_db() -> None:
    with pytest.raises(ValueError, match="target_price_out_of_range"):
        update_watch("user", "product", target_price=0, notify_on_drop=True)
    with pytest.raises(ValueError, match="target_price_out_of_range"):
        update_watch("user", "product", target_price=20_000_000, notify_on_drop=False)


def test_popular_search_sql_requires_aggregate_threshold() -> None:
    import inspect

    from mayabu.search import search_repository as repo

    source = inspect.getsource(repo.popular_search_queries)
    assert "count(*) >= 5" in source
    assert ">= 3" in source
    assert "between 2 and 80" in source
    assert "password|otp|token" in source
