"""Metrics — counters, histograms, gauges, and registry.

Design:
    * ``Counter`` — monotonically increasing value (inc / reset).
    * ``Histogram`` — records values into user-defined buckets (observe / snapshot).
    * ``Gauge`` — current value (set / inc / dec / reset).
    * ``MetricsRegistry`` — holds named metrics and provides a snapshot.
    * ``InMemoryMetricsRegistry`` — stores metrics in memory for testing.

All metric operations are atomic and thread-safe. The registry uses
``anyio.Lock`` for async-safe reads/writes.
"""
from __future__ import annotations
from typing import Any
import bisect
import threading
import re

__all__ = [
    "Counter",
    "Histogram",
    "Gauge",
    "MetricsRegistry",
    "InMemoryMetricsRegistry",
    "to_prometheus",
    "to_openmetrics",
]


def _validate_label_name(name: str) -> None:
    """Raise *ValueError* if *name* is not a valid Prometheus label name.

    Prometheus label names must match ``[a-zA-Z_][a-zA-Z0-9_]*``.
    """
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError(f"Invalid Prometheus label name: {name!r}")


def _validate_labels(labels: dict[str, str] | None) -> None:
    """Raise *ValueError* if any key in *labels* is an invalid Prometheus label name."""
    if not labels:
        return
    for key in labels:
        _validate_label_name(key)


def _labels_key(labels: dict[str, str] | None) -> frozenset:
    """Convert a labels dict into a hashable frozenset of (k, v) pairs."""
    if not labels:
        return frozenset()
    return frozenset(sorted(labels.items()))


def _format_labels(labels: dict[str, Any]) -> str:
    """Format a labels dict into a Prometheus label string.

    Returns ``{label1=\"value1\",label2=\"value2\"}`` or an empty string
    when *labels* is empty.  Escapes ``\\`` and ``\"`` in values as
    required by the Prometheus text format.
    """
    if not labels:
        return ""
    parts = []
    for k, v in sorted(labels.items()):
        s = str(v)
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'{k}="{escaped}"')
    return "{" + ",".join(parts) + "}"


# ------------------------------------------------------------------ Counter

class Counter:
    """Monotonically increasing counter with optional label dimensions.

    Thread-safe: uses an internal lock.
    """

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: dict[frozenset, int] = {}
        self._lock = threading.Lock()

    def inc(self, amount: int = 1, labels: dict[str, str] | None = None) -> None:
        """Increment the counter by ``amount`` (default 1).

        Parameters:
            amount: how much to add.
            labels: optional label dimensions (e.g. ``{"transport": "stdio"}``).
        """
        _validate_labels(labels)
        key = _labels_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0) + amount

    def reset(self) -> None:
        """Reset all label series to zero."""
        with self._lock:
            self._values.clear()

    @property
    def value(self) -> int:
        """Return the value for the empty label set (no labels)."""
        return self._values.get(frozenset(), 0)

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot with all label series.

        The ``values`` key holds a list of ``{"labels": {...}, "value": ...}``.
        """
        return {
            "name": self.name,
            "type": "counter",
            "values": [
                {"labels": dict(key), "value": val}
                for key, val in sorted(self._values.items())
            ],
            "description": self.description,
        }


# ------------------------------------------------------------------ Histogram

class Histogram:
    """Histogram that records values into buckets with optional label dimensions.

    Parameters:
        name: metric name.
        description: optional description.
        buckets: sorted list of upper bounds. Default is a standard set
            of latencies in milliseconds: [1, 5, 10, 25, 50, 100, 250,
            500, 1000, 2500, 5000, 10000].

    Thread-safe: uses an internal lock.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        *,
        buckets: list[float] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self._buckets = sorted(buckets or [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000])
        # Each label key gets its own bucket counts, sum, and count.
        self._values: dict[frozenset, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a value into the histogram.

        Parameters:
            value: the observation.
            labels: optional label dimensions.
        """
        _validate_labels(labels)
        key = _labels_key(labels)
        with self._lock:
            if key not in self._values:
                self._values[key] = {
                    "counts": [0] * (len(self._buckets) + 1),
                    "sum": 0.0,
                    "count": 0,
                }
            entry = self._values[key]
            idx = bisect.bisect_left(self._buckets, value)
            entry["counts"][idx] += 1
            entry["sum"] += value
            entry["count"] += 1

    def reset(self) -> None:
        """Reset all label series."""
        with self._lock:
            self._values.clear()

    @property
    def buckets(self) -> list[float]:
        return list(self._buckets)

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot with all label series.

        The ``values`` key holds a list of dicts with ``labels``,
        ``buckets``, ``sum``, and ``count``.
        """
        values = []
        for key, entry in sorted(self._values.items()):
            values.append({
                "labels": dict(key),
                "buckets": [
                    {"le": b, "count": entry["counts"][i]}
                    for i, b in enumerate(self._buckets)
                ] + [{"le": "+Inf", "count": entry["counts"][-1]}],
                "sum": entry["sum"],
                "count": entry["count"],
            })
        return {
            "name": self.name,
            "type": "histogram",
            "description": self.description,
            "values": values,
        }


# ------------------------------------------------------------------ Gauge

class Gauge:
    """Gauge that holds a current value with optional label dimensions.

    Thread-safe: uses an internal lock.
    """

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: dict[frozenset, float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Set the gauge to a specific value.

        Parameters:
            value: the new value.
            labels: optional label dimensions.
        """
        _validate_labels(labels)
        key = _labels_key(labels)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the gauge by ``amount``.

        Parameters:
            amount: how much to add.
            labels: optional label dimensions.
        """
        _validate_labels(labels)
        key = _labels_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Decrement the gauge by ``amount``.

        Parameters:
            amount: how much to subtract.
            labels: optional label dimensions.
        """
        _validate_labels(labels)
        key = _labels_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - amount

    def reset(self) -> None:
        """Reset all label series to zero."""
        with self._lock:
            self._values.clear()

    @property
    def value(self) -> float:
        """Return the value for the empty label set (no labels)."""
        return self._values.get(frozenset(), 0.0)

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot with all label series.

        The ``values`` key holds a list of ``{"labels": {...}, "value": ...}``.
        """
        return {
            "name": self.name,
            "type": "gauge",
            "values": [
                {"labels": dict(key), "value": val}
                for key, val in sorted(self._values.items())
            ],
            "description": self.description,
        }


# ------------------------------------------------------------------ MetricsRegistry (ABC)

class MetricsRegistry:
    """Abstract metrics registry.

    Subclasses must implement ``get_or_create_counter``, ``get_or_create_histogram``,
    ``get_or_create_gauge``, and ``snapshot``.
    """

    def get_or_create_counter(self, name: str, description: str = "") -> Counter:
        raise NotImplementedError

    def get_or_create_histogram(self, name: str, description: str = "", *, buckets: list[float] | None = None) -> Histogram:
        raise NotImplementedError

    def get_or_create_gauge(self, name: str, description: str = "") -> Gauge:
        raise NotImplementedError

    def snapshot(self) -> dict[str, dict[str, Any]]:
        raise NotImplementedError


# ------------------------------------------------------------------ InMemoryMetricsRegistry

def _sanitize_metric_name(name: str) -> str:
    """Convert a metric name to a valid Prometheus metric name.

    Replaces dots and dashes with underscores and strips any
    characters that are not ``[a-zA-Z0-9_:]``.
    """
    name = name.replace(".", "_").replace("-", "_")
    if not name:
        return "_"
    if not (name[0].isalpha() or name[0] == "_"):
        name = "_" + name
    return re.sub(r"[^a-zA-Z0-9_:]", "_", name)


def _render_exposition(snapshot: dict[str, dict[str, Any]]) -> list[str]:
    """Shared helper that builds exposition lines for Prometheus / OpenMetrics.

    Returns a list of lines (without the trailing ``# EOF``)."""
    lines: list[str] = []

    counters = snapshot.get("counters", {})
    for name, data in counters.items():
        prom_name = _sanitize_metric_name(name)
        desc = data.get("description", "")
        lines.append(f"# HELP {prom_name} {desc}")
        lines.append(f"# TYPE {prom_name} counter")
        for series in data.get("values", []):
            labels_str = _format_labels(series.get("labels", {}))
            lines.append(f"{prom_name}{labels_str} {series['value']}")
        lines.append("")

    histograms = snapshot.get("histograms", {})
    for name, data in histograms.items():
        prom_name = _sanitize_metric_name(name)
        desc = data.get("description", "")
        lines.append(f"# HELP {prom_name} {desc}")
        lines.append(f"# TYPE {prom_name} histogram")
        for series in data.get("values", []):
            labels = series.get("labels", {})
            labels_str = _format_labels(labels)
            cumulative = 0
            for bucket in series.get("buckets", []):
                le = bucket["le"]
                cumulative += bucket["count"]
                bucket_labels_dict = dict(labels)
                bucket_labels_dict["le"] = le
                bucket_labels = _format_labels(bucket_labels_dict)
                lines.append(f"{prom_name}_bucket{bucket_labels} {cumulative}")
            lines.append(f"{prom_name}_sum{labels_str} {series['sum']}")
            lines.append(f"{prom_name}_count{labels_str} {series['count']}")
        lines.append("")

    gauges = snapshot.get("gauges", {})
    for name, data in gauges.items():
        prom_name = _sanitize_metric_name(name)
        desc = data.get("description", "")
        lines.append(f"# HELP {prom_name} {desc}")
        lines.append(f"# TYPE {prom_name} gauge")
        for series in data.get("values", []):
            labels_str = _format_labels(series.get("labels", {}))
            lines.append(f"{prom_name}{labels_str} {series['value']}")
        lines.append("")

    return lines


def to_prometheus(snapshot: dict[str, dict[str, Any]]) -> str:
    """Render a metrics snapshot in Prometheus text exposition format.

    Parameters:
        snapshot: the dict returned by ``InMemoryMetricsRegistry.snapshot()``.

    Returns:
        A string in the Prometheus text format.
    """
    return "\n".join(_render_exposition(snapshot))


def to_openmetrics(snapshot: dict[str, dict[str, Any]]) -> str:
    """Render a metrics snapshot in OpenMetrics text format.

    OpenMetrics is the successor to the Prometheus text format.
    Key differences include:
    * ``Content-Type: application/openmetrics-text; version=1.0.0; charset=utf-8``
    * Mandatory ``# EOF`` trailer
    * ``# UNIT`` lines are optional

    Parameters:
        snapshot: the dict returned by ``InMemoryMetricsRegistry.snapshot()``.

    Returns:
        A string in the OpenMetrics text format.
    """
    lines = _render_exposition(snapshot)
    lines.append("# EOF")
    return "\n".join(lines)


class InMemoryMetricsRegistry(MetricsRegistry):
    """In-memory metrics registry for testing and development.

    Thread-safe: uses a ``threading.Lock``.

    Parameters:
        default_labels: optional label dimensions applied to every
            metric series at snapshot time (e.g.
            ``{"transport": "stdio"}``).  Explicit labels on a metric
            take precedence over defaults.
    """

    def __init__(self, default_labels: dict[str, str] | None = None) -> None:
        self._counters: dict[str, Counter] = {}
        self._histograms: dict[str, Histogram] = {}
        self._gauges: dict[str, Gauge] = {}
        self._default_labels: dict[str, str] = dict(default_labels) if default_labels else {}
        _validate_labels(self._default_labels)
        self._lock = threading.Lock()

    def get_or_create_counter(self, name: str, description: str = "") -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, description)
            return self._counters[name]

    def get_or_create_histogram(self, name: str, description: str = "", *, buckets: list[float] | None = None) -> Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, description, buckets=buckets)
            return self._histograms[name]

    def get_or_create_gauge(self, name: str, description: str = "") -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, description)
            return self._gauges[name]

    def snapshot(self) -> dict[str, dict[str, Any]]:
        snap = {
            "counters": {name: c.snapshot() for name, c in self._counters.items()},
            "histograms": {name: h.snapshot() for name, h in self._histograms.items()},
            "gauges": {name: g.snapshot() for name, g in self._gauges.items()},
        }
        # Merge default_labels into each series.  Explicit labels win.
        if self._default_labels:
            for category in ("counters", "gauges", "histograms"):
                for data in snap.get(category, {}).values():
                    for series in data.get("values", []):
                        merged = dict(self._default_labels)
                        merged.update(series.get("labels", {}))
                        series["labels"] = merged
        return snap

    def prometheus(self) -> str:
        """Return metrics in Prometheus text exposition format."""
        return to_prometheus(self.snapshot())

    def reset_all(self) -> None:
        """Reset all metrics to zero."""
        for c in self._counters.values():
            c.reset()
        for h in self._histograms.values():
            h.reset()
        for g in self._gauges.values():
            g.reset()
