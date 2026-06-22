"""
Basic application startup tests to ensure the modular components work together.
"""

import os
from unittest.mock import patch

import pytest


def test_main_imports_correctly():
    """Test that the main module can be imported without errors."""
    try:
        import engineering_service

        assert hasattr(engineering_service, "main")
    except ImportError as e:
        pytest.fail(f"Failed to import engineering_service: {e}")


def test_core_bootstrap_imports():
    """Test that core bootstrap module imports correctly."""
    try:
        from core.bootstrap import lifespan, logger

        assert logger is not None
        assert lifespan is not None
    except ImportError as e:
        pytest.fail(f"Failed to import from core.bootstrap: {e}")


def test_services_imports():
    """Test that service modules import correctly."""
    try:
        from services.cache_service import get_study_cache
        from services.study_service import execute_study_logic

        assert execute_study_logic is not None
        assert get_study_cache is not None
    except ImportError as e:
        pytest.fail(f"Failed to import from services: {e}")


def test_api_routes_imports():
    """Test that API routes module imports correctly."""
    try:
        from api.routes import app

        assert app is not None
    except ImportError as e:
        pytest.fail(f"Failed to import from api.routes: {e}")


def test_etap_adapter_imports():
    """Test that ETAP adapter module imports correctly."""
    try:
        from etap_integration.etap_adapter import ETAPAdapter

        assert ETAPAdapter is not None
    except ImportError as e:
        # This might fail if pywin32 is not available on non-Windows platforms
        # which is expected behavior
        if os.name == "nt":  # Windows
            pytest.fail(f"Failed to import from etap_integration.etap_adapter: {e}")
        else:
            # On non-Windows, this import failure is expected
            pass


def test_environment_variables():
    """Test that environment variables are handled correctly."""
    # Test default values
    assert os.environ.get("USE_ETAP", "false").lower() in ["true", "false"]
    assert os.environ.get("PRIVACY_MODE", "false").lower() in ["true", "false"]

    # Test setting values
    os.environ["TEST_VAR"] = "test_value"
    assert os.environ["TEST_VAR"] == "test_value"

    # Clean up
    if "TEST_VAR" in os.environ:
        del os.environ["TEST_VAR"]
