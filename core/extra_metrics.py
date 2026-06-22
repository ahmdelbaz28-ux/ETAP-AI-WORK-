# Additional Prometheus metrics for alerting

from prometheus_client import Counter, Gauge, Histogram

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
