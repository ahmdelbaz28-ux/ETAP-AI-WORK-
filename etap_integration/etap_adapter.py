"""
ETAP Adapter module for the Engineering Service.
Provides a common interface for ETAP integration with optional functionality.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from core.bootstrap import logger

# ─── Unified types (single source of truth) ─────────────────────────────
# ETAPStudyType + ETAPResult are now defined in unified_etap_types.py
# to eliminate the 3-way duplication.
# See: PRODUCTION_PLAN/02_DUPLICATION_REPORT.md Cluster #1
from etap_integration.unified_etap_types import ETAPResult, ETAPStudyType


class ETAPAdapter(ABC):
    """Abstract base class for ETAP adapters."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if ETAP provider is available."""
        pass

    @abstractmethod
    def execute_study(
        self, project_path: str, study_type: ETAPStudyType, parameters: dict[str, Any] | None = None,
    ) -> ETAPResult:
        """Execute a study via ETAP."""
        pass


class ETAPProviderAdapter(ETAPAdapter):
    """Concrete implementation of ETAP adapter using COM automation."""

    def __init__(self):
        self._available = False
        self._provider = None

        # Check if ETAP functionality is enabled via environment variable
        self.use_etap = os.getenv("USE_ETAP", "false").lower() == "true"

        if self.use_etap:
            try:
                # Try to import ETAP COM provider
                from .etap_provider import get_etap_provider

                # SonarCloud python:S5864: get_etap_provider() already returns
                # a fully-initialised IEtapProvider INSTANCE — do NOT call it
                # again. The previous `get_etap_provider()()` raised TypeError
                # at runtime, which was silently swallowed by the except below,
                # disabling ETAP integration whenever USE_ETAP=true.
                self._provider = get_etap_provider()
                self._available = self._provider.is_available() if self._provider else False
            except ImportError as e:
                logger.warning(f"ETAP provider not available: {e}")
                self._available = False
            except Exception:
                logger.exception("Error initializing ETAP provider: ")
                self._available = False
        else:
            logger.info("ETAP functionality disabled via USE_ETAP environment variable")

    def is_available(self) -> bool:
        """Check if ETAP provider is available."""
        return self._available

    def execute_study(
        self, project_path: str, study_type: ETAPStudyType, parameters: dict[str, Any] | None = None,
    ) -> ETAPResult:
        """Execute a study via ETAP provider."""
        if not self.use_etap:
            return ETAPResult(
                success=False,
                data={},
                errors=["ETAP functionality is disabled via USE_ETAP environment variable"],
                execution_time=0.0,
            )

        if not self._available:
            return ETAPResult(
                success=False,
                data={},
                errors=["ETAP provider is not available"],
                execution_time=0.0,
            )

        try:
            # Execute study via the provider
            result = self._provider.execute_study(project_path, study_type)
            return result
        except Exception as e:
            logger.exception("Error executing ETAP study: ")
            return ETAPResult(success=False, data={}, errors=[str(e)], execution_time=0.0)


class MockETAPAdapter(ETAPAdapter):
    """Mock implementation for testing when ETAP is not available."""

    def __init__(self):
        self.use_etap = os.getenv("USE_ETAP", "false").lower() == "true"
        self._available = self.use_etap  # Available only if enabled

    def is_available(self) -> bool:
        """Check if mock ETAP provider is available."""
        return self._available

    def execute_study(
        self, project_path: str, study_type: ETAPStudyType, parameters: dict[str, Any] | None = None,
    ) -> ETAPResult:
        """Mock execution of a study."""
        if not self.use_etap:
            return ETAPResult(
                success=False,
                data={},
                errors=["ETAP functionality is disabled via USE_ETAP environment variable"],
                execution_time=0.0,
            )

        # Simulate a successful study execution with mock data
        mock_data = {
            "study_type": study_type.value,
            "project_path": project_path,
            "status": "completed",
            "mock_result": True,
        }

        if parameters:
            mock_data["parameters_used"] = parameters

        logger.info(f"Mock ETAP study executed: {study_type.value} on {project_path}")

        return ETAPResult(
            success=True,
            data=mock_data,
            warnings=["This is a mock result - not connected to actual ETAP"],
            execution_time=0.1,  # Simulated execution time
        )


def get_etap_adapter() -> ETAPAdapter:
    """Factory function to get the appropriate ETAP adapter based on environment."""
    # Check if we should use mock adapter for testing
    use_mock = os.getenv("USE_MOCK_ETAP", "false").lower() == "true"

    if use_mock:
        return MockETAPAdapter()
    else:
        return ETAPProviderAdapter()


# Backward compatibility with existing code
def get_etap_provider():
    """Legacy function for backward compatibility."""
    return get_etap_adapter
