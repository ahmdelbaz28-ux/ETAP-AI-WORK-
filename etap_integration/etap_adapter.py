"""
ETAP Adapter module for the Engineering Service.
Provides a common interface for ETAP integration with optional functionality.
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum

from core.bootstrap import logger


class ETAPStudyType(Enum):
    """Enumeration of supported ETAP study types."""
    LOAD_FLOW = "load_flow"
    SHORT_CIRCUIT = "short_circuit"
    ARC_FLASH = "arc_flash"
    HARMONIC_ANALYSIS = "harmonic_analysis"
    OPTIMAL_POWER_FLOW = "optimal_power_flow"
    MOTOR_STARTING = "motor_starting"
    PROTECTION_COORDINATION = "protection_coordination"


class ETAPResult:
    """Result wrapper for ETAP operations."""
    
    def __init__(self, success: bool, data: Dict[str, Any], warnings: list = None, errors: list = None, execution_time: float = 0.0):
        self.success = success
        self.data = data
        self.warnings = warnings or []
        self.errors = errors or []
        self.execution_time = execution_time


class ETAPAdapter(ABC):
    """Abstract base class for ETAP adapters."""
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if ETAP provider is available."""
        pass
    
    @abstractmethod
    def execute_study(self, project_path: str, study_type: ETAPStudyType, parameters: Optional[Dict[str, Any]] = None) -> ETAPResult:
        """Execute a study via ETAP."""
        pass


class ETAPProviderAdapter(ETAPAdapter):
    """Concrete implementation of ETAP adapter using COM automation."""
    
    def __init__(self):
        self._available = False
        self._provider = None
        
        # Check if ETAP functionality is enabled via environment variable
        self.use_etap = os.getenv('USE_ETAP', 'false').lower() == 'true'
        
        if self.use_etap:
            try:
                # Try to import ETAP COM provider
                from .etap_provider import get_etap_provider
                self._provider = get_etap_provider()()
                self._available = self._provider.is_available() if self._provider else False
            except ImportError as e:
                logger.warning(f"ETAP provider not available: {e}")
                self._available = False
            except Exception as e:
                logger.error(f"Error initializing ETAP provider: {e}")
                self._available = False
        else:
            logger.info("ETAP functionality disabled via USE_ETAP environment variable")
    
    def is_available(self) -> bool:
        """Check if ETAP provider is available."""
        return self._available
    
    def execute_study(self, project_path: str, study_type: ETAPStudyType, parameters: Optional[Dict[str, Any]] = None) -> ETAPResult:
        """Execute a study via ETAP provider."""
        if not self.use_etap:
            return ETAPResult(
                success=False,
                data={},
                errors=["ETAP functionality is disabled via USE_ETAP environment variable"],
                execution_time=0.0
            )
        
        if not self._available:
            return ETAPResult(
                success=False,
                data={},
                errors=["ETAP provider is not available"],
                execution_time=0.0
            )
        
        try:
            # Execute study via the provider
            result = self._provider.execute_study(project_path, study_type)
            return result
        except Exception as e:
            logger.error(f"Error executing ETAP study: {e}")
            return ETAPResult(
                success=False,
                data={},
                errors=[str(e)],
                execution_time=0.0
            )


class MockETAPAdapter(ETAPAdapter):
    """Mock implementation for testing when ETAP is not available."""
    
    def __init__(self):
        self.use_etap = os.getenv('USE_ETAP', 'false').lower() == 'true'
        self._available = self.use_etap  # Available only if enabled
    
    def is_available(self) -> bool:
        """Check if mock ETAP provider is available."""
        return self._available
    
    def execute_study(self, project_path: str, study_type: ETAPStudyType, parameters: Optional[Dict[str, Any]] = None) -> ETAPResult:
        """Mock execution of a study."""
        if not self.use_etap:
            return ETAPResult(
                success=False,
                data={},
                errors=["ETAP functionality is disabled via USE_ETAP environment variable"],
                execution_time=0.0
            )
        
        # Simulate a successful study execution with mock data
        mock_data = {
            "study_type": study_type.value,
            "project_path": project_path,
            "status": "completed",
            "mock_result": True
        }
        
        if parameters:
            mock_data["parameters_used"] = parameters
        
        logger.info(f"Mock ETAP study executed: {study_type.value} on {project_path}")
        
        return ETAPResult(
            success=True,
            data=mock_data,
            warnings=["This is a mock result - not connected to actual ETAP"],
            execution_time=0.1  # Simulated execution time
        )


def get_etap_adapter() -> ETAPAdapter:
    """Factory function to get the appropriate ETAP adapter based on environment."""
    # Check if we should use mock adapter for testing
    use_mock = os.getenv('USE_MOCK_ETAP', 'false').lower() == 'true'
    
    if use_mock:
        return MockETAPAdapter()
    else:
        return ETAPProviderAdapter()


# Backward compatibility with existing code
def get_etap_provider():
    """Legacy function for backward compatibility."""
    return get_etap_adapter