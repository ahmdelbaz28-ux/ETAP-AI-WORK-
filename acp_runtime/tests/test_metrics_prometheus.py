"""Unit tests for the Prometheus text format rendering in metrics.py.

Covers:
    * Counter formatting (HELP, TYPE, value)
    * Gauge formatting
    * Histogram formatting (buckets, +Inf, sum, count)
    * Metric name sanitization (dots, dashes, invalid chars)
    * Empty snapshot returns empty string
"""
from __future__ import annotations

import pytest
from acp.observability.metrics import (
    InMemoryMetricsRegistry,
    _format_labels,
    _labels_key,
    _sanitize_metric_name,
    _validate_label_name,
    _validate_labels,
    to_openmetrics,
    to_prometheus,
)


class TestValidateLabelName:
    def test_valid_names(self):
        for name in ("a", "A", "_", "_foo", "foo", "foo_bar", "foo_123", "FooBar"):
            _validate_label_name(name)  # should not raise

    def test_empty_name(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: ''"):
            _validate_label_name("")

    def test_starting_with_digit(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: '123'"):
            _validate_label_name("123")
        with pytest.raises(ValueError, match="Invalid Prometheus label name: '1foo'"):
            _validate_label_name("1foo")

    def test_containing_dot(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'foo.bar'"):
            _validate_label_name("foo.bar")

    def test_containing_dash(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'foo-bar'"):
            _validate_label_name("foo-bar")

    def test_containing_space(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'foo bar'"):
            _validate_label_name("foo bar")

    def test_containing_special_char(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'foo@bar'"):
            _validate_label_name("foo@bar")

    def test_validate_labels_with_invalid_key(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'foo-bar'"):
            _validate_labels({"foo-bar": "baz"})

    def test_validate_labels_empty(self):
        _validate_labels(None)  # should not raise
        _validate_labels({})  # should not raise

    def test_validate_labels_valid(self):
        _validate_labels({"transport": "stdio", "env": "prod"})  # should not raise

    def test_validate_labels_mixed_valid_invalid(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'bad-key'"):
            _validate_labels({"valid": "yes", "bad-key": "no"})


class TestMetricLabelValidationIntegration:
    def test_counter_rejects_invalid_label(self):
        from acp.observability.metrics import Counter
        c = Counter("c1")
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'bad-name'"):
            c.inc(labels={"bad-name": "x"})

    def test_gauge_rejects_invalid_label(self):
        from acp.observability.metrics import Gauge
        g = Gauge("g1")
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'bad.name'"):
            g.set(5, labels={"bad.name": "x"})
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'bad.inc'"):
            g.inc(1, labels={"bad.inc": "x"})
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'bad.dec'"):
            g.dec(1, labels={"bad.dec": "x"})

    def test_histogram_rejects_invalid_label(self):
        from acp.observability.metrics import Histogram
        h = Histogram("h1")
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'bad name'"):
            h.observe(1, labels={"bad name": "x"})

    def test_registry_rejects_invalid_default_labels(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'bad-name'"):
            InMemoryMetricsRegistry(default_labels={"bad-name": "x"})

    def test_non_ascii_first_char_rejected(self):
        with pytest.raises(ValueError, match="Invalid Prometheus label name: 'ñame'"):
            _validate_label_name("ñame")


class TestLabelsKey:
    def test_empty_labels(self):
        assert _labels_key(None) == frozenset()
        assert _labels_key({}) == frozenset()

    def test_consistency(self):
        # Dict ordering should not matter
        assert _labels_key({"b": "2", "a": "1"}) == _labels_key({"a": "1", "b": "2"})

    def test_distinct_keys(self):
        assert _labels_key({"a": "1"}) != _labels_key({"a": "2"})
        assert _labels_key({"a": "1"}) != _labels_key({"b": "1"})


class TestFormatLabels:
    def test_empty(self):
        assert _format_labels({}) == ""

    def test_single(self):
        assert _format_labels({"transport": "stdio"}) == '{transport="stdio"}'

    def test_multiple_sorted(self):
        assert _format_labels({"b": "2", "a": "1"}) == '{a="1",b="2"}'

    def test_escapes_quotes(self):
        assert _format_labels({"transport": 'std"io'}) == '{transport="std\\"io"}'

    def test_escapes_backslash(self):
        assert _format_labels({"transport": "std\\io"}) == '{transport="std\\\\io"}'


class TestDefaultLabels:
    def test_registry_default_labels(self):
        reg = InMemoryMetricsRegistry(default_labels={"transport": "stdio"})
        c = reg.get_or_create_counter("test.calls")
        c.inc(5)
        snap = reg.snapshot()
        assert snap["counters"]["test.calls"]["values"][0]["labels"] == {"transport": "stdio"}

    def test_registry_default_labels_overridden(self):
        reg = InMemoryMetricsRegistry(default_labels={"transport": "stdio", "env": "prod"})
        c = reg.get_or_create_counter("test.calls")
        c.inc(3, labels={"transport": "uds"})
        snap = reg.snapshot()
        assert snap["counters"]["test.calls"]["values"][0]["labels"] == {"transport": "uds", "env": "prod"}

    def test_registry_default_labels_prometheus(self):
        reg = InMemoryMetricsRegistry(default_labels={"transport": "stdio"})
        c = reg.get_or_create_counter("test.calls")
        c.inc(7)
        text = reg.prometheus()
        assert 'test_calls{transport="stdio"} 7' in text

    def test_registry_default_labels_histogram(self):
        reg = InMemoryMetricsRegistry(default_labels={"transport": "stdio"})
        h = reg.get_or_create_histogram("test.latency")
        h.observe(10)
        text = reg.prometheus()
        assert 'test_latency_bucket{le="1",transport="stdio"}' in text
        assert 'test_latency_sum{transport="stdio"}' in text
        assert 'test_latency_count{transport="stdio"}' in text


class TestSanitizeMetricName:
    def test_dot_to_underscore(self):
        assert _sanitize_metric_name("acp.runtime.calls") == "acp_runtime_calls"

    def test_dash_to_underscore(self):
        assert _sanitize_metric_name("my-metric") == "my_metric"

    def test_invalid_chars_removed(self):
        assert _sanitize_metric_name("metric@home!") == "metric_home_"

    def test_leading_digit_underscore(self):
        assert _sanitize_metric_name("123metric") == "_123metric"

    def test_empty_name(self):
        assert _sanitize_metric_name("") == "_"


class TestToPrometheus:
    def test_counter(self):
        snapshot = {
            "counters": {
                "test.calls": {"name": "test.calls", "type": "counter", "values": [{"labels": {}, "value": 5}], "description": "Test counter"}
            }
        }
        text = to_prometheus(snapshot)
        assert "# HELP test_calls Test counter" in text
        assert "# TYPE test_calls counter" in text
        assert "test_calls 5" in text

    def test_gauge(self):
        snapshot = {
            "gauges": {
                "test.active": {"name": "test.active", "type": "gauge", "values": [{"labels": {}, "value": 7.5}], "description": "Active gauge"}
            }
        }
        text = to_prometheus(snapshot)
        assert "# HELP test_active Active gauge" in text
        assert "# TYPE test_active gauge" in text
        assert "test_active 7.5" in text

    def test_histogram(self):
        snapshot = {
            "histograms": {
                "test.latency": {
                    "name": "test.latency",
                    "type": "histogram",
                    "description": "Latency histogram",
                    "values": [
                        {
                            "labels": {},
                            "buckets": [
                                {"le": 1, "count": 0},
                                {"le": 5, "count": 1},
                                {"le": 10, "count": 1},
                                {"le": "+Inf", "count": 1},
                            ],
                            "sum": 15.0,
                            "count": 3,
                        }
                    ],
                }
            }
        }
        text = to_prometheus(snapshot)
        assert "# HELP test_latency Latency histogram" in text
        assert "# TYPE test_latency histogram" in text
        # Cumulative counts: 0, 1, 2, 3
        assert 'test_latency_bucket{le="1"} 0' in text
        assert 'test_latency_bucket{le="5"} 1' in text
        assert 'test_latency_bucket{le="10"} 2' in text
        assert 'test_latency_bucket{le="+Inf"} 3' in text
        assert "test_latency_sum 15.0" in text
        assert "test_latency_count 3" in text

    def test_multiple_metrics(self):
        snapshot = {
            "counters": {"a.count": {"name": "a.count", "type": "counter", "values": [{"labels": {}, "value": 1}], "description": "A"}},
            "gauges": {"b.gauge": {"name": "b.gauge", "type": "gauge", "values": [{"labels": {}, "value": 2}], "description": "B"}},
            "histograms": {
                "c.hist": {"name": "c.hist", "type": "histogram", "description": "C", "values": [{"labels": {}, "buckets": [{"le": "+Inf", "count": 0}], "sum": 0.0, "count": 0}]}
            },
        }
        text = to_prometheus(snapshot)
        assert "a_count 1" in text
        assert "b_gauge 2" in text
        assert "c_hist" in text

    def test_empty_snapshot(self):
        assert to_prometheus({}) == ""
        assert to_prometheus({"counters": {}, "gauges": {}, "histograms": {}}) == ""

    def test_no_description(self):
        snapshot = {
            "counters": {"foo": {"name": "foo", "type": "counter", "values": [{"labels": {}, "value": 1}], "description": ""}}
        }
        text = to_prometheus(snapshot)
        assert "# HELP foo " in text

    def test_counter_with_labels(self):
        snapshot = {
            "counters": {
                "test.calls": {"name": "test.calls", "type": "counter", "values": [
                    {"labels": {}, "value": 3},
                    {"labels": {"transport": "stdio"}, "value": 5},
                    {"labels": {"transport": "uds"}, "value": 2},
                ], "description": "Test counter"}
            }
        }
        text = to_prometheus(snapshot)
        assert "test_calls 3" in text
        assert 'test_calls{transport="stdio"} 5' in text
        assert 'test_calls{transport="uds"} 2' in text

    def test_histogram_with_labels(self):
        snapshot = {
            "histograms": {
                "test.latency": {
                    "name": "test.latency",
                    "type": "histogram",
                    "description": "Latency histogram",
                    "values": [
                        {
                            "labels": {"transport": "stdio"},
                            "buckets": [
                                {"le": 1, "count": 0},
                                {"le": 5, "count": 1},
                                {"le": "+Inf", "count": 1},
                            ],
                            "sum": 10.0,
                            "count": 2,
                        },
                    ],
                }
            }
        }
        text = to_prometheus(snapshot)
        # _format_labels sorts keys alphabetically, so le comes before transport
        assert 'test_latency_bucket{le="1",transport="stdio"} 0' in text
        assert 'test_latency_bucket{le="5",transport="stdio"} 1' in text
        assert 'test_latency_bucket{le="+Inf",transport="stdio"} 2' in text
        assert 'test_latency_sum{transport="stdio"} 10.0' in text
        assert 'test_latency_count{transport="stdio"} 2' in text

    def test_gauge_with_labels(self):
        snapshot = {
            "gauges": {
                "test.active": {"name": "test.active", "type": "gauge", "values": [
                    {"labels": {}, "value": 7.0},
                    {"labels": {"transport": "websocket"}, "value": 3.0},
                ], "description": "Active gauge"}
            }
        }
        text = to_prometheus(snapshot)
        assert "test_active 7.0" in text
        assert 'test_active{transport="websocket"} 3.0' in text


class TestToOpenMetrics:
    def test_counter(self):
        snapshot = {
            "counters": {
                "test.calls": {"name": "test.calls", "type": "counter", "values": [{"labels": {}, "value": 5}], "description": "Test counter"}
            }
        }
        text = to_openmetrics(snapshot)
        assert "# HELP test_calls Test counter" in text
        assert "# TYPE test_calls counter" in text
        assert "test_calls 5" in text
        assert "# EOF" in text

    def test_gauge(self):
        snapshot = {
            "gauges": {
                "test.active": {"name": "test.active", "type": "gauge", "values": [{"labels": {}, "value": 7.5}], "description": "Active gauge"}
            }
        }
        text = to_openmetrics(snapshot)
        assert "# HELP test_active Active gauge" in text
        assert "# TYPE test_active gauge" in text
        assert "test_active 7.5" in text
        assert "# EOF" in text

    def test_histogram_cumulative(self):
        snapshot = {
            "histograms": {
                "test.latency": {
                    "name": "test.latency",
                    "type": "histogram",
                    "description": "Latency histogram",
                    "values": [
                        {
                            "labels": {},
                            "buckets": [
                                {"le": 1, "count": 0},
                                {"le": 5, "count": 1},
                                {"le": 10, "count": 1},
                                {"le": "+Inf", "count": 1},
                            ],
                            "sum": 15.0,
                            "count": 3,
                        }
                    ],
                }
            }
        }
        text = to_openmetrics(snapshot)
        assert "# HELP test_latency Latency histogram" in text
        assert "# TYPE test_latency histogram" in text
        # Cumulative counts
        assert 'test_latency_bucket{le="1"} 0' in text
        assert 'test_latency_bucket{le="5"} 1' in text
        assert 'test_latency_bucket{le="10"} 2' in text
        assert 'test_latency_bucket{le="+Inf"} 3' in text
        assert "test_latency_sum 15.0" in text
        assert "test_latency_count 3" in text
        assert "# EOF" in text

    def test_empty_snapshot(self):
        assert "# EOF" in to_openmetrics({})
        assert "# EOF" in to_openmetrics({"counters": {}, "gauges": {}, "histograms": {}})

    def test_eof_is_last_line(self):
        text = to_openmetrics({"counters": {"a": {"name": "a", "type": "counter", "values": [{"labels": {}, "value": 1}], "description": ""}}})
        assert text.rstrip().endswith("# EOF")
