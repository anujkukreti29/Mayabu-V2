"""Process-local Prometheus-compatible metrics registry.

No external metrics dependency. Safe for API, worker, and scheduler processes.
Labels must stay low-cardinality (route templates, platforms, categories, status classes).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable


_ALLOWED_LABEL_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-./")


def _sanitize_label(value: str | None, *, default: str = "unknown", max_len: int = 48) -> str:
    text = str(value or default).strip() or default
    cleaned = "".join(ch if ch in _ALLOWED_LABEL_CHARS else "_" for ch in text)
    return cleaned[:max_len] or default


def _label_key(labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((k, _sanitize_label(v)) for k, v in labels.items()))


@dataclass
class _Counter:
    name: str
    help: str
    label_names: tuple[str, ...]
    values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=lambda: defaultdict(float))
    lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = _label_key({name: labels.get(name, "unknown") for name in self.label_names})
        with self.lock:
            self.values[key] += float(amount)


@dataclass
class _Gauge:
    name: str
    help: str
    label_names: tuple[str, ...]
    values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float, **labels: str) -> None:
        key = _label_key({name: labels.get(name, "unknown") for name in self.label_names})
        with self.lock:
            self.values[key] = float(value)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = _label_key({name: labels.get(name, "unknown") for name in self.label_names})
        with self.lock:
            self.values[key] = self.values.get(key, 0.0) + float(amount)

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        self.inc(-amount, **labels)


_DEFAULT_BUCKETS_MS = (
    1.0,
    2.5,
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
    5000.0,
    10000.0,
    30000.0,
)


@dataclass
class _Histogram:
    name: str
    help: str
    label_names: tuple[str, ...]
    buckets: tuple[float, ...] = _DEFAULT_BUCKETS_MS
    counts: dict[tuple[tuple[str, str], ...], list[float]] = field(default_factory=dict)
    sums: dict[tuple[tuple[str, str], ...], float] = field(default_factory=lambda: defaultdict(float))
    totals: dict[tuple[tuple[str, str], ...], float] = field(default_factory=lambda: defaultdict(float))
    lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value_ms: float, **labels: str) -> None:
        key = _label_key({name: labels.get(name, "unknown") for name in self.label_names})
        value = max(0.0, float(value_ms))
        with self.lock:
            if key not in self.counts:
                self.counts[key] = [0.0] * len(self.buckets)
            bucket_counts = self.counts[key]
            for idx, bound in enumerate(self.buckets):
                if value <= bound:
                    bucket_counts[idx] += 1.0
            self.sums[key] += value
            self.totals[key] += 1.0


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, _Counter] = {}
        self._gauges: dict[str, _Gauge] = {}
        self._histograms: dict[str, _Histogram] = {}

    def counter(self, name: str, help: str, label_names: Iterable[str] = ()) -> _Counter:
        with self._lock:
            existing = self._counters.get(name)
            if existing:
                return existing
            metric = _Counter(name=name, help=help, label_names=tuple(label_names))
            self._counters[name] = metric
            return metric

    def gauge(self, name: str, help: str, label_names: Iterable[str] = ()) -> _Gauge:
        with self._lock:
            existing = self._gauges.get(name)
            if existing:
                return existing
            metric = _Gauge(name=name, help=help, label_names=tuple(label_names))
            self._gauges[name] = metric
            return metric

    def histogram(self, name: str, help: str, label_names: Iterable[str] = ()) -> _Histogram:
        with self._lock:
            existing = self._histograms.get(name)
            if existing:
                return existing
            metric = _Histogram(name=name, help=help, label_names=tuple(label_names))
            self._histograms[name] = metric
            return metric

    def reset(self) -> None:
        """Test helper — clear all series."""
        with self._lock:
            for metric in self._counters.values():
                with metric.lock:
                    metric.values.clear()
            for metric in self._gauges.values():
                with metric.lock:
                    metric.values.clear()
            for metric in self._histograms.values():
                with metric.lock:
                    metric.counts.clear()
                    metric.sums.clear()
                    metric.totals.clear()

    def render_prometheus(self) -> str:
        lines: list[str] = []
        for metric in sorted(self._counters.values(), key=lambda m: m.name):
            lines.append(f"# HELP {metric.name} {metric.help}")
            lines.append(f"# TYPE {metric.name} counter")
            with metric.lock:
                for labels, value in sorted(metric.values.items()):
                    lines.append(f"{metric.name}{{{_format_labels(labels)}}} {value}")
        for metric in sorted(self._gauges.values(), key=lambda m: m.name):
            lines.append(f"# HELP {metric.name} {metric.help}")
            lines.append(f"# TYPE {metric.name} gauge")
            with metric.lock:
                for labels, value in sorted(metric.values.items()):
                    lines.append(f"{metric.name}{{{_format_labels(labels)}}} {value}")
        for metric in sorted(self._histograms.values(), key=lambda m: m.name):
            lines.append(f"# HELP {metric.name} {metric.help}")
            lines.append(f"# TYPE {metric.name} histogram")
            with metric.lock:
                for labels, bucket_counts in sorted(metric.counts.items()):
                    cumulative = 0.0
                    for bound, count in zip(metric.buckets, bucket_counts, strict=True):
                        cumulative += count
                        le_labels = labels + (("le", _sanitize_label(str(bound))),)
                        lines.append(f"{metric.name}_bucket{{{_format_labels(le_labels)}}} {cumulative}")
                    inf_labels = labels + (("le", "+Inf"),)
                    total = metric.totals.get(labels, 0.0)
                    lines.append(f"{metric.name}_bucket{{{_format_labels(inf_labels)}}} {total}")
                    lines.append(f"{metric.name}_sum{{{_format_labels(labels)}}} {metric.sums.get(labels, 0.0)}")
                    lines.append(f"{metric.name}_count{{{_format_labels(labels)}}} {total}")
        return "\n".join(lines) + ("\n" if lines else "")


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    return ",".join(f'{k}="{v}"' for k, v in labels)


_REGISTRY = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    return _REGISTRY


class Timer:
    """Context manager that records elapsed milliseconds into a histogram."""

    __slots__ = ("_histogram", "_labels", "_started")

    def __init__(self, histogram: _Histogram, **labels: str) -> None:
        self._histogram = histogram
        self._labels = labels
        self._started = 0.0

    def __enter__(self) -> Timer:
        self._started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed_ms = (time.perf_counter() - self._started) * 1000.0
        self._histogram.observe(elapsed_ms, **self._labels)

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._started) * 1000.0
