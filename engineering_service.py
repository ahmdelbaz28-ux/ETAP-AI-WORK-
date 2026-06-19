"""
Main entry point for the Engineering Service.
This file now serves as the main application runner, delegating to the modular components.
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from uvicorn import run

from core.bootstrap import lifespan, logger
from api.routes import app as api_app  # Import the configured API app


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
        api_app,
        host=host,
        port=port,
        log_level="info",
        reload=os.environ.get("ENVIRONMENT", "development").lower() == "development"
    )


if __name__ == "__main__":
    main()