"""In-process singleflight for identical cache-miss work (stampede mitigation)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class SingleFlight:
    """Coalesce concurrent callers for the same key onto one producer."""

    def __init__(self, *, recent_ttl_seconds: float = 1.0) -> None:
        self._lock = threading.Lock()
        self._inflight: dict[str, dict[str, Any]] = {}
        self._recent: dict[str, tuple[float, Any, BaseException | None]] = {}
        self._recent_ttl = max(0.05, float(recent_ttl_seconds))

    def do(self, key: str, producer: Callable[[], T]) -> T:
        now = time.monotonic()
        with self._lock:
            recent = self._recent.get(key)
            if recent and recent[0] > now:
                if recent[2] is not None:
                    raise recent[2]
                return recent[1]  # type: ignore[return-value]

            state = self._inflight.get(key)
            if state is None:
                state = {
                    "event": threading.Event(),
                    "box": [],
                    "err": [],
                    "waiters": 1,
                }
                self._inflight[key] = state
                owner = True
            else:
                state["waiters"] += 1
                owner = False

        event: threading.Event = state["event"]
        box: list[Any] = state["box"]
        err: list[BaseException] = state["err"]

        try:
            if owner:
                try:
                    result = producer()
                    box.append(result)
                    with self._lock:
                        self._recent[key] = (time.monotonic() + self._recent_ttl, result, None)
                    return result
                except BaseException as exc:  # noqa: BLE001
                    err.append(exc)
                    with self._lock:
                        self._recent[key] = (time.monotonic() + self._recent_ttl, None, exc)
                    raise
                finally:
                    event.set()
            if not event.wait(timeout=30):
                return producer()
            if err:
                raise err[0]
            if box:
                return box[0]
            return producer()
        finally:
            with self._lock:
                state["waiters"] -= 1
                if state["waiters"] <= 0:
                    self._inflight.pop(key, None)
                # Opportunistic prune of expired recent entries.
                expired = [k for k, (exp, _, _) in self._recent.items() if exp <= time.monotonic()]
                for stale in expired[:32]:
                    self._recent.pop(stale, None)


_SEARCH_SINGLEFLIGHT = SingleFlight()


def search_singleflight() -> SingleFlight:
    return _SEARCH_SINGLEFLIGHT
