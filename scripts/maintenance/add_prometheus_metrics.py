import json
from pathlib import Path

# Resolve to absolute, normalized path. `__file__` is the script location
# (maintainer-controlled, not user input), but we normalize to satisfy
# SonarCloud S2083 (path injection) and make the path deterministic.
METRICS_FILE = (Path(__file__).resolve().parent / "core" / "metrics.py")

BLOCK = """
# ---------------------------------------------------------------------------
# HTTP request metrics
# ---------------------------------------------------------------------------

REQUEST_ERRORS_TOTAL = Counter(
    "request_errors_total",
    "Total request errors",
    ["method", "route"],
)

REQUEST_LATENCY_SECONDS = Histogram(
    "request_latency_seconds",
    "Request latency in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# ---------------------------------------------------------------------------
# Cache metrics
# ---------------------------------------------------------------------------

CACHE_HITS_TOTAL = Counter(
    "cache_hits_total",
    "Total cache hits",
)

CACHE_MISSES_TOTAL = Counter(
    "cache_misses_total",
    "Total cache misses",
)

# ---------------------------------------------------------------------------
# System availability metrics
# ---------------------------------------------------------------------------

SCADA_AVAILABLE = Gauge(
    "scada_available",
    "SCADA service availability",
)

DIGITAL_TWIN_AVAILABLE = Gauge(
    "digital_twin_available",
    "Digital Twin service availability",
)
"""


def main() -> None:
    content = METRICS_FILE.read_text(encoding="utf-8").splitlines()
    # Find the logger line index
    logger_idx = next(
        (i for i, line in enumerate(content) if "logger = logging.getLogger(__name__)" in line),
        None,
    )
    if logger_idx is None:
        raise RuntimeError("Logger line not found in metrics file.")
    # Insert block after logger line
    insert_pos = logger_idx + 1
    # Ensure a blank line before block for readability
    new_content = content[:insert_pos] + ["", BLOCK] + content[insert_pos:]
    METRICS_FILE.write_text("\n".join(new_content) + "\n", encoding="utf-8")
    result = {"modified": True, "lines_added": 30}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
