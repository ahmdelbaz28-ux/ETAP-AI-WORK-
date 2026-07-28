import json
import os

# Ensure target directory exists
os.makedirs("core", exist_ok=True)

# Content for extra_metrics.py
extra_metrics_content = """# Additional Prometheus metrics for alerting

from prometheus_client import Counter, Histogram, Gauge

# Request error counter
REQUEST_ERRORS_TOTAL = Counter(
    "request_errors_total",
    "Total HTTP request errors",
    ["method", "route"],
)

# Request latency histogram (seconds)
REQUEST_LATENCY_SECONDS = Histogram(
    "request_latency_seconds",
    "Request latency seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Cache hit/miss counters
CACHE_HITS_TOTAL = Counter(
    "cache_hits_total",
    "Cache hits",
)

CACHE_MISSES_TOTAL = Counter(
    "cache_misses_total",
    "Cache misses",
)

# Availability gauges
SCADA_AVAILABLE = Gauge(
    "scada_available",
    "SCADA availability (1=up, 0=down)",
)

DIGITAL_TWIN_AVAILABLE = Gauge(
    "digital_twin_available",
    "Digital Twin availability (1=up, 0=down)",
)
"""

# Write the file
with open(os.path.join("core", "extra_metrics.py"), "w", encoding="utf-8") as f:
    f.write(extra_metrics_content)

# Output JSON
print(json.dumps({"created": True, "path": "core/extra_metrics.py"}))
