
"""
SCADA Data Model - Real-Time Grid State
=========================================
Implements telemetry inputs, breaker status, real-time measurements,
and SCADA communication model for ADMS integration.

Reference: IEC 61850 Communication Standard, IEC 61970 CIM
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np


# ============================================================
# MEASUREMENT TYPES
# ============================================================

class MeasurementType(Enum):
    VOLTAGE_MAGNITUDE = "voltage_magnitude"
    VOLTAGE_ANGLE = "voltage_angle"
    CURRENT_MAGNITUDE = "current_magnitude"
    CURRENT_ANGLE = "current_angle"
    ACTIVE_POWER = "active_power"
    REACTIVE_POWER = "reactive_power"
    FREQUENCY = "frequency"
    BREAKER_STATUS = "breaker_status"
    TAP_POSITION = "tap_position"
    TEMPERATURE = "temperature"


class QualityFlag(Enum):
    GOOD = "good"
    QUESTIONABLE = "questionable"
    INVALID = "invalid"
    MISSING = "missing"


@dataclass
class Measurement:
    """Single SCADA measurement point."""
    measurement_id: str
    measurement_type: MeasurementType
    element_id: str  # Bus, line, transformer ID
    value: float
    timestamp: float = field(default_factory=time.time)
    quality: QualityFlag = QualityFlag.GOOD
    confidence: float = 1.0  # 0.0 to 1.0

    def is_valid(self) -> bool:
        return self.quality in (QualityFlag.GOOD, QualityFlag.QUESTIONABLE)

    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    def to_dict(self) -> dict:
        return {
            "measurement_id": self.measurement_id,
            "measurement_type": self.measurement_type.value,
            "element_id": self.element_id,
            "value": self.value,
            "timestamp": self.timestamp,
            "quality": self.quality.value,
            "confidence": self.confidence
        }


# ============================================================
# BREAKER / SWITCH MODEL
# ============================================================

class SwitchStatus(Enum):
    CLOSED = "closed"
    OPEN = "open"
    TRIPPED = "tripped"  # Fault-triggered opening
    LOCKED_OUT = "locked_out"  # Manual lockout after trip


@dataclass
class SwitchDevice:
    """Circuit breaker or disconnect switch model."""
    device_id: str
    from_element: str  # Bus or node ID
    to_element: str    # Bus or node ID
    status: SwitchStatus = SwitchStatus.CLOSED
    rated_current: float = 1000.0  # Amps
    trip_count: int = 0
    last_operation_time: Optional[float] = None
    protection_enabled: bool = True
    auto_reclosing_enabled: bool = True
    auto_reclosing_attempts: int = 0
    max_reclosing_attempts: int = 3

    def is_conducting(self) -> bool:
        return self.status == SwitchStatus.CLOSED

    def operate(self, new_status: SwitchStatus) -> bool:
        """Operate the switch device. Returns True if operation successful."""
        if self.status == SwitchStatus.LOCKED_OUT and new_status != SwitchStatus.CLOSED:
            return False  # Cannot operate a locked-out device
        self.status = new_status
        self.last_operation_time = time.time()
        if new_status == SwitchStatus.TRIPPED:
            self.trip_count += 1
        return True

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "from_element": self.from_element,
            "to_element": self.to_element,
            "status": self.status.value,
            "rated_current": self.rated_current,
            "trip_count": self.trip_count,
            "protection_enabled": self.protection_enabled,
            "auto_reclosing_enabled": self.auto_reclosing_enabled
        }


# ============================================================
# SCADA MEASUREMENT DATABASE
# ============================================================

class SCADADatabase:
    """
    SCADA measurement database with real-time state tracking.
    Supports telemetry inputs, breaker status, and measurement history.
    """

    def __init__(self, measurement_ttl_seconds: float = 300.0):
        """
        Initialize SCADA database.

        Parameters:
        measurement_ttl_seconds: Time-to-live for measurements (default 5 min).
        """
        self.measurements: Dict[str, Measurement] = {}
        self.switch_devices: Dict[str, SwitchDevice] = {}
        self.measurement_ttl = measurement_ttl_seconds
        self.measurement_history: Dict[str, List[Measurement]] = {}
        self.max_history_per_point = 1000

    # --- Measurement Management ---

    def add_measurement(self, measurement: Measurement) -> None:
        """Add or update a measurement."""
        mid = measurement.measurement_id
        self.measurements[mid] = measurement
        # Store history
        if mid not in self.measurement_history:
            self.measurement_history[mid] = []
        self.measurement_history[mid].append(measurement)
        if len(self.measurement_history[mid]) > self.max_history_per_point:
            self.measurement_history[mid] = self.measurement_history[mid][-self.max_history_per_point:]

    def get_measurement(self, measurement_id: str) -> Optional[Measurement]:
        return self.measurements.get(measurement_id)

    def get_measurements_for_element(self, element_id: str) -> List[Measurement]:
        """Get all measurements for a given element."""
        return [m for m in self.measurements.values() if m.element_id == element_id]

    def get_measurements_by_type(self, mtype: MeasurementType) -> List[Measurement]:
        """Get all measurements of a given type."""
        return [m for m in self.measurements.values() if m.measurement_type == mtype]

    def get_latest_voltage(self, bus_id: str) -> Optional[float]:
        """Get latest voltage magnitude for a bus."""
        for m in self.measurements.values():
            if m.element_id == bus_id and m.measurement_type == MeasurementType.VOLTAGE_MAGNITUDE:
                if m.is_valid() and m.age_seconds() < self.measurement_ttl:
                    return m.value
        return None

    def get_latest_power(self, element_id: str) -> Optional[Tuple[float, float]]:
        """Get latest P, Q for an element."""
        p, q = None, None
        for m in self.measurements.values():
            if m.element_id == element_id:
                if m.measurement_type == MeasurementType.ACTIVE_POWER and m.is_valid():
                    p = m.value
                elif m.measurement_type == MeasurementType.REACTIVE_POWER and m.is_valid():
                    q = m.value
        if p is not None and q is not None:
            return (p, q)
        return None

    def get_expired_measurements(self) -> List[Measurement]:
        """Get measurements that have exceeded TTL."""
        return [m for m in self.measurements.values() if m.age_seconds() > self.measurement_ttl]

    def clean_expired(self) -> int:
        """Remove expired measurements. Returns count removed."""
        expired = self.get_expired_measurements()
        for m in expired:
            del self.measurements[m.measurement_id]
        return len(expired)

    # --- Switch Device Management ---

    def add_switch_device(self, device: SwitchDevice) -> None:
        self.switch_devices[device.device_id] = device

    def get_switch_device(self, device_id: str) -> Optional[SwitchDevice]:
        return self.switch_devices.get(device_id)

    def operate_switch(self, device_id: str, new_status: SwitchStatus) -> bool:
        """Operate a switch device."""
        device = self.switch_devices.get(device_id)
        if device:
            return device.operate(new_status)
        return False

    def get_open_switches(self) -> List[SwitchDevice]:
        return [s for s in self.switch_devices.values() if not s.is_conducting()]

    def get_closed_switches(self) -> List[SwitchDevice]:
        return [s for s in self.switch_devices.values() if s.is_conducting()]

    def get_switches_between(self, element1: str, element2: str) -> List[SwitchDevice]:
        """Get all switches between two elements."""
        results = []
        for s in self.switch_devices.values():
            if (s.from_element == element1 and s.to_element == element2) or \
               (s.from_element == element2 and s.to_element == element1):
                results.append(s)
        return results

    # --- Real-Time State Vectors ---

    def get_voltage_state_vector(self, bus_ids: List[str]) -> np.ndarray:
        """
        Get voltage state vector for given buses.
        Returns complex voltage array. Missing data = 1.0∠0.
        """
        voltages = []
        for bus_id in bus_ids:
            vmag = self.get_latest_voltage(bus_id)
            if vmag is None:
                vmag = 1.0
            # Try to get angle
            vang = 0.0
            for m in self.measurements.values():
                if m.element_id == bus_id and m.measurement_type == MeasurementType.VOLTAGE_ANGLE:
                    if m.is_valid():
                        vang = m.value
                    break
            voltages.append(complex(vmag * np.cos(np.radians(vang)), vmag * np.sin(np.radians(vang))))
        return np.array(voltages)

    def get_power_injection_vector(self, bus_ids: List[str]) -> np.ndarray:
        """
        Get power injection vector for given buses.
        Returns complex power array. Missing data = 0+0j.
        """
        injections = []
        for bus_id in bus_ids:
            pq = self.get_latest_power(bus_id)
            if pq:
                injections.append(complex(pq[0], pq[1]))
            else:
                injections.append(complex(0, 0))
        return np.array(injections)

    def get_topology_switching_state(self) -> Dict[str, bool]:
        """Get current switching state as dict of device_id -> is_closed."""
        return {did: dev.is_conducting() for did, dev in self.switch_devices.items()}

    # --- Statistics ---

    def get_statistics(self) -> dict:
        """Get SCADA database statistics."""
        type_counts = {}
        for mtype in MeasurementType:
            type_counts[mtype.value] = len(self.get_measurements_by_type(mtype))
        return {
            "total_measurements": len(self.measurements),
            "total_switch_devices": len(self.switch_devices),
            "open_switches": len(self.get_open_switches()),
            "closed_switches": len(self.get_closed_switches()),
            "expired_measurements": len(self.get_expired_measurements()),
            "measurements_by_type": type_counts,
            "history_points": sum(len(h) for h in self.measurement_history.values())
        }
