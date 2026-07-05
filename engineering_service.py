"""
Main entry point for the Engineering Service.
This file now serves as the main application runner, delegating to the modular components.

MEDIUM #17 (AhmedETAP_Error_Report_AR.pdf):
`api/routes.py` is the CANONICAL FastAPI entry point for this service.
This file (`engineering_service.py`) is a thin runner that imports
`api.routes:app` and runs it via uvicorn. The historical duplicate
FastAPI app in `api/refactored_service.py` is kept ONLY as a fallback
for the `engineering-service` Docker image (Dockerfile.engineering-service)
which still references it directly. New code should never create another
FastAPI() instance — extend `api/routes.py` or attach routers to it.
"""

import logging
import os

# Defensive import: ensure `trace` is available even if a middleware or downstream
# module references `trace.SpanKind.SERVER` directly. This prevents NameError at
# request time when OpenTelemetry tracing is wired into FastAPI middleware.
# See: FIXES_APPLIED.md (2026-06-28 — Vercel Build Fix + Cross-Platform Auto-Sync)
from opentelemetry import trace  # noqa: F401 — re-exported for downstream use
from uvicorn import run

from core.bootstrap import logger

# SECURITY: install secret-redaction filter on the root logger BEFORE any
# application code runs. This catches accidental logging of credentials
# (API keys, JWT tokens, TOTP secrets, connection-string passwords) and
# replaces them with [REDACTED-*] markers before they reach log handlers.
# Filter is enabled by default; disable via AUDIT_LOG_REDACT_SECRETS=false.
try:
    from security.log_redaction import install_globally as _install_redaction

    _install_redaction()
except ImportError:
    # security module may not be importable in stripped-down deployments
    # (e.g. HF Space minimal requirements). Skip silently.
    pass


def main():
    """
    Main entry point for the Engineering Service.
    Creates and runs the FastAPI application with proper configuration.
    """
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Determine if we should use ETAP functionality
    use_etap = os.environ.get("USE_ETAP", "false").lower() == "true"

    if use_etap:
        logger.info("ETAP integration enabled via USE_ETAP environment variable")
    else:
        logger.info("ETAP integration disabled - using native engine only")

    # Start the API server
    port = int(os.environ.get("ENGINEERING_SERVICE_PORT", os.environ.get("PORT", 8000)))
    host = os.environ.get("ENGINEERING_SERVICE_HOST", os.environ.get("HOST", "0.0.0.0"))

    logger.info("Starting Engineering Service on %s:%s", host, port)

    # Run the application
    run(
        "api.routes:app",
        host=host,
        port=port,
        log_level="info",
        reload=os.environ.get("ENVIRONMENT", "development").lower() == "development",
    )


if __name__ == "__main__":
    main()
