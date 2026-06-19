القد"""
ETAP Provider Interface
=======================
Abstracts the ETAP execution layer to support both local COM (Windows)
and remote API-based (Linux) execution.
"""

import logging
import os
import sys
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

class ETAPStudyType(Enum):
    LOAD_FLOW = "LOAD_FLOW"
    SHORT_CIRCUIT = "SHORT_CIRCUIT"
    ARC_FLASH = "ARC_FLASH"
    HARMONIC_ANALYSIS = "HARMONIC_ANALYSIS"
    OPTIMAL_POWER_FLOW = "OPTIMAL_POWER_FLOW"
    MOTOR_STARTING = "MOTOR_STARTING"
    PROTECTION_COORDINATION = "PROTECTION_COORDINATION"

class ETAPResult:
    def __init__(self, success: bool, data: Dict[str, Any], warnings: List[str], errors: List[str], execution_time: float = 0.0):
        self.success = success
        self.data = data
        self.warnings = warnings
        self.errors = errors
        self.execution_time = execution_time

class IEtapProvider(ABC):
    @abstractmethod
    def execute_study(self, project_path: str, study_type: ETAPStudyType, visible: bool = False) -> ETAPResult:
        """
        Execute a study on the configured ETAP backend.

        Concrete providers (Local, Remote, Mock, Null) must override.
        """
        ...

    def is_available(self) -> bool:
        """
        Return True if the underlying ETAP backend is reachable.

        Default returns False (no backend wired up).  Concrete providers
        override to probe their backend (COM Dispatch, /health endpoint,
        etc.).
        """
        return False

class LocalEtapProvider(IEtapProvider):
    """Windows-only provider using direct COM automation."""
    def __init__(self):
        # Check if ETAP functionality is enabled via environment variable
        self.use_etap = os.getenv('USE_ETAP', 'false').lower() == 'true'
        
        if not self.use_etap:
            self._available = False
            logger.info("Local ETAP provider disabled via USE_ETAP environment variable")
        else:
            self._available = sys.platform == "win32"
            if self._available:
                try:
                    from etap_integration.etap_com import ETAPAutomation  # noqa: F401
                except ImportError:
                    self._available = False
                    logger.warning("etap_com module not found or pywin32 missing")

    def is_available(self) -> bool:
        return self._available

    def execute_study(self, project_path: str, study_type: ETAPStudyType, visible: bool = False) -> ETAPResult:
        if not self._available:
            return ETAPResult(False, {}, [], ["Local ETAP automation not available or disabled"], 0.0)

        import time

        from etap_integration.etap_com import ETAPAutomation
        from etap_integration.etap_com import ETAPStudyType as ComStudyType

        # Map provider enum to COM enum
        com_study_type = ComStudyType[study_type.name]

        start_time = time.time()
        try:
            with ETAPAutomation(visible=visible) as etap:
                project = etap.open_project(project_path)
                if not project:
                    return ETAPResult(False, {}, [], [f"Failed to open project: {project_path}"], time.time() - start_time)

                result = project.run_study(com_study_type)
                return ETAPResult(
                    result.success,
                    result.data,
                    result.warnings,
                    result.errors,
                    time.time() - start_time
                )
        except Exception as e:
            return ETAPResult(False, {}, [], [str(e)], time.time() - start_time)

class RemoteEtapProvider(IEtapProvider):
    """Cross-platform provider that calls a remote Windows ETAP Worker.

    Features:
    - Retry with exponential backoff
    - Circuit breaker pattern
    - Configurable timeouts
    """

    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]  # seconds - exponential backoff
    CIRCUIT_BREAKER_THRESHOLD = 5  # consecutive failures before opening
    CIRCUIT_BREAKER_RESET_SECONDS = 60  # seconds before trying again

    def __init__(self, worker_url: str, api_key: str):
        # Check if ETAP functionality is enabled via environment variable
        self.use_etap = os.getenv('USE_ETAP', 'false').lower() == 'true'
        
        if not self.use_etap:
            logger.info("Remote ETAP provider disabled via USE_ETAP environment variable")
            self.worker_url = ""
            self.api_key = ""
            return
            
        self.worker_url = worker_url.rstrip('/')
        self.api_key = api_key
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _is_circuit_open(self) -> bool:
        """Check if the circuit breaker is currently open."""
        if not self.use_etap:
            return True  # Consider circuit open if ETAP is disabled
        if self._consecutive_failures < self.CIRCUIT_BREAKER_THRESHOLD:
            return False
        if time.time() < self._circuit_open_until:
            return True
        # Circuit has expired, allow a probe request (half-open)
        logger.info("RemoteEtapProvider circuit breaker transitioning to HALF_OPEN")
        return False

    def _record_success(self) -> None:
        """Reset circuit breaker on successful call."""
        if self._consecutive_failures > 0:
            logger.info("RemoteEtapProvider circuit breaker reset to CLOSED after success")
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _record_failure(self) -> None:
        """Record a failure and open circuit if threshold exceeded."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open_until = time.time() + self.CIRCUIT_BREAKER_RESET_SECONDS
            logger.warning(
                "RemoteEtapProvider circuit breaker OPEN after %d consecutive failures. "
                "Will retry after %d seconds.",
                self._consecutive_failures, self.CIRCUIT_BREAKER_RESET_SECONDS
            )

    def is_available(self) -> bool:
        if not self.use_etap:
            return False
        try:
            response = requests.get(f"{self.worker_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def execute_study(self, project_path: str, study_type: ETAPStudyType, visible: bool = False) -> ETAPResult:
        if not self.use_etap:
            return ETAPResult(
                False, {}, [],
                ["Remote ETAP provider disabled via USE_ETAP environment variable"],
                0.0
            )
            
        # Circuit breaker check
        if self._is_circuit_open():
            return ETAPResult(
                False, {}, [],
                [f"ETAP Worker circuit breaker is OPEN after {self._consecutive_failures} consecutive failures. "
                 f"Retry after {int(self._circuit_open_until - time.time())}s."],
                0.0
            )

        payload = {
            "project_path": project_path,
            "study_type": study_type.name,
            "visible": visible
        }
        headers = {
            "X-ETAP-Worker-Key": self.api_key
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.post(f"{self.worker_url}/execute", json=payload, headers=headers, timeout=300)
                if response.status_code == 200:
                    data = response.json()
                    self._record_success()
                    return ETAPResult(
                        data['success'],
                        data['data'],
                        data['warnings'],
                        data['errors'],
                        data['execution_time']
                    )
                else:
                    last_error = f"Worker returned error {response.status_code}: {response.text}"
                    logger.warning("RemoteEtapProvider attempt %d/%d failed: %s", attempt + 1, self.MAX_RETRIES, last_error)
            except Exception as e:
                last_error = f"Failed to connect to ETAP Worker: {str(e)}"
                logger.warning("RemoteEtapProvider attempt %d/%d failed: %s", attempt + 1, self.MAX_RETRIES, last_error)

            # Apply exponential backoff between retries
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(self.RETRY_DELAYS[attempt])

        # All retries exhausted
        self._record_failure()
        return ETAPResult(False, {}, [], [last_error or "All retry attempts exhausted"], 0.0)

class MockEtapProvider(IEtapProvider):
    """Mock provider for development and testing. Returns simulated ETAP results."""

    MOCK_RESULTS = {
        ETAPStudyType.LOAD_FLOW: {
            'converged': True,
            'buses': {
                'Bus1': {'voltage_magnitude': 1.05, 'voltage_angle': 0.0, 'active_power': 50.0, 'reactive_power': 10.0},
                'Bus2': {'voltage_magnitude': 0.98, 'voltage_angle': -2.5, 'active_power': 0.0, 'reactive_power': 0.0},
                'Bus3': {'voltage_magnitude': 0.95, 'voltage_angle': -4.2, 'active_power': -80.0, 'reactive_power': -30.0},
            },
            'branches': {
                'Line1-2': {'active_power_from': 50.2, 'reactive_power_from': 10.5, 'current': 0.52},
                'Line2-3': {'active_power_from': 30.1, 'reactive_power_from': 8.2, 'current': 0.31},
            },
            'iterations': 4,
        },
        ETAPStudyType.SHORT_CIRCUIT: {
            'fault_currents': {
                'Bus1': {'three_phase_ka': 20.5, 'line_to_ground_ka': 18.2, 'line_to_line_ka': 17.7, 'double_line_to_ground_ka': 19.1},
                'Bus2': {'three_phase_ka': 15.3, 'line_to_ground_ka': 13.8, 'line_to_line_ka': 13.2, 'double_line_to_ground_ka': 14.5},
            },
            'fault_type': 'ThreePhase',
        },
        ETAPStudyType.ARC_FLASH: {
            'equipment_results': {
                'SWGR-1': {'incident_energy_cal_cm2': 8.5, 'arc_flash_boundary_mm': 1200, 'ppe_level': '2', 'arc_duration_sec': 0.5},
                'SWGR-2': {'incident_energy_cal_cm2': 3.2, 'arc_flash_boundary_mm': 600, 'ppe_level': '1', 'arc_duration_sec': 0.3},
            },
            'standard': 'IEEE 1584-2018',
        },
        ETAPStudyType.HARMONIC_ANALYSIS: {
            'converged': True,
            'buses': {
                'Bus1': {'voltage_thd_percent': 2.8, 'current_thd_percent': 4.5, 'fundamental_voltage_mag': 1.02, 'dominant_harmonic_order': 5},
                'Bus2': {'voltage_thd_percent': 3.1, 'current_thd_percent': 5.2, 'fundamental_voltage_mag': 0.98, 'dominant_harmonic_order': 7},
            },
            'standard': 'IEEE 519-2014',
            'total_harmonic_distortion_limit_percent': 5.0,
        },
        ETAPStudyType.OPTIMAL_POWER_FLOW: {
            'converged': True,
            'generators': {
                'Gen1': {'active_power_mw': 47.5, 'reactive_power_mvar': 10.5, 'cost_per_hour': 135.0},
                'Gen2': {'active_power_mw': 95.0, 'reactive_power_mvar': 21.0, 'cost_per_hour': 270.0},
            },
            'total_system_loss_mw': 2.25,
            'total_generation_cost_per_hour': 1250.50,
            'optimization_objective': 'Minimize Losses',
        },
        ETAPStudyType.MOTOR_STARTING: {
            'converged': True,
            'motors': {
                'Motor1': {'starting_current_multiplier': 6.0, 'acceleration_time_sec': 2.5, 'min_voltage_during_start_pu': 0.75, 'speed_at_end_of_start_percent': 100.0},
                'Motor2': {'starting_current_multiplier': 5.5, 'acceleration_time_sec': 3.1, 'min_voltage_during_start_pu': 0.82, 'speed_at_end_of_start_percent': 100.0},
            },
            'voltage_dip_profile': {
                'max_dip_percent': 15.0,
                'recovery_time_sec': 1.2
            },
            'starting_method': 'Across-the-Line',
        },
        ETAPStudyType.PROTECTION_COORDINATION: {
            'converged': True,
            'relay_pairs': {
                'Relay_UP_DOWN': {'upstream_relay': 'Relay_UP', 'downstream_relay': 'Relay_DOWN', 'time_difference_sec': 0.45, 'coordinated': True},
            },
            'settings': {
                'Relay_UP': {'pickup_amps': 100.0, 'time_dial': 0.5, 'curve_type': 'CO-8'},
                'Relay_DOWN': {'pickup_amps': 80.0, 'time_dial': 0.2, 'curve_type': 'CO-8'},
            },
            'fault_current_range_ka': [2.0, 5.0, 10.0, 20.0],
        },
    }

    def __init__(self):
        # Check if ETAP functionality is enabled via environment variable
        self.use_etap = os.getenv('USE_ETAP', 'false').lower() == 'true'
        if not self.use_etap:
            logger.info("Mock ETAP provider disabled via USE_ETAP environment variable")

    def is_available(self) -> bool:
        return self.use_etap

    def execute_study(self, project_path: str, study_type: ETAPStudyType, visible: bool = False) -> ETAPResult:
        if not self.use_etap:
            return ETAPResult(
                False, {}, [],
                ["Mock ETAP provider disabled via USE_ETAP environment variable"],
                0.0
            )
                
        import time
        start_time = time.time()

        mock_data = self.MOCK_RESULTS.get(study_type, {})
        return ETAPResult(
            success=True,
            data=mock_data,
            warnings=['Using MockEtapProvider - results are simulated'],
            errors=[],
            execution_time=time.time() - start_time,
        )


class NullEtapProvider(IEtapProvider):
    """Fallback provider when no ETAP is available."""
    def __init__(self):
        # Check if ETAP functionality is enabled via environment variable
        self.use_etap = os.getenv('USE_ETAP', 'false').lower() == 'true'
        if self.use_etap:
            logger.info("Null ETAP provider - ETAP is enabled but no provider available")

    def is_available(self) -> bool:
        return False

    def execute_study(self, project_path: str, study_type: ETAPStudyType, visible: bool = False) -> ETAPResult:
        if not self.use_etap:
            return ETAPResult(
                False, {}, [],
                ["ETAP functionality is disabled via USE_ETAP environment variable"],
                0.0
            )
        else:
            return ETAPResult(False, {}, [], ["No ETAP provider configured or available"], 0.0)

def get_etap_provider() -> IEtapProvider:
    """Factory method to get the appropriate provider based on environment.

    Priority:
    1. USE_ETAP=false -> NullEtapProvider (disabled)
    2. ETAP_PROVIDER=mock -> MockEtapProvider (for development/testing)
    3. ETAP_WORKER_URL + ETAP_WORKER_API_KEY -> RemoteEtapProvider
    4. Windows with pywin32 -> LocalEtapProvider
    5. Fallback -> NullEtapProvider
    """
    # Check if ETAP is explicitly disabled
    if os.getenv('USE_ETAP', 'true').lower() == 'false':
        logger.info("ETAP functionality disabled via USE_ETAP environment variable")
        return NullEtapProvider()

    provider_type = os.environ.get("ETAP_PROVIDER", "").lower()

    if provider_type == "mock":
        logger.info("Using MockEtapProvider (development mode)")
        return MockEtapProvider()

    worker_url = os.environ.get("ETAP_WORKER_URL")
    api_key = os.environ.get("ETAP_WORKER_API_KEY")

    if worker_url and api_key:
        return RemoteEtapProvider(worker_url, api_key)

    if sys.platform == "win32":
        provider = LocalEtapProvider()
        if provider.is_available():
            return provider

    return NullEtapProvider()