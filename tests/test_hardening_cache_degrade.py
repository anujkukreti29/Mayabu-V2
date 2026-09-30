"""Redis optional-cache degrade behavior."""

from __future__ import annotations

from mayabu.search.cache import Cache


def test_cache_get_returns_none_when_disabled(monkeypatch) -> None:
    cache = Cache.__new__(Cache)
    cache.enabled = False
    cache.client = None
    cache._disabled_until = 0.0
    assert cache.get_json("search:v6:anything") is None
    cache.set_json("search:v6:anything", {"ok": True}, 30)  # no-op


def test_cache_degrades_on_client_failure(monkeypatch) -> None:
    class Boom:
        def get(self, key):
            raise TimeoutError("redis timeout")

        def setex(self, *args, **kwargs):
            raise TimeoutError("redis timeout")

    cache = Cache.__new__(Cache)
    cache.enabled = True
    cache.client = Boom()
    cache._disabled_until = 0.0
    assert cache.get_json("search:v6:q") is None
    assert cache._disabled_until > 0
    # While backed off, further calls skip Redis without raising.
    assert cache.get_json("search:v6:q") is None
