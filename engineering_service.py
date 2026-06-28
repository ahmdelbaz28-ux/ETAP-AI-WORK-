"""
Main entry point for the Engineering Service.
This file now serves as the main application runner, delegating to the modular components.
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

    logger.info(f"Starting Engineering Service on {host}:{port}")

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
