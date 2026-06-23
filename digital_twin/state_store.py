"""
State Store - Versioned State Management for Digital Twin
=========================================================
Implements immutable state snapshots with version tracking,
rollback support, and state diff computation.

The state store holds the unified digital twin state across all layers:
  - GIS Spatial State
  - Electrical Model State
  - ADMS Operational State
  - Simulation Results State
"""

from __future__ import annotations

import copy
import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Tuple

import numpy as np


class StateLayer(Enum):
    """Layers of the digital twin state."""

    GIS = "gis"
    ELECTRICAL = "electrical"
    ADMS = "adms"
    SIMULATION = "simulation"


@dataclass
class BusState:
    """Electrical state of a single bus."""

    bus_id: str
    voltage_magnitude: float = 1.0
    voltage_angle: float = 0.0
    load_power: complex = complex(0, 0)
    generation_power: complex = complex(0, 0)
    bus_type: str = "pq"

    @property
    def voltage(self) -> complex:
        return self.voltage_magnitude * np.exp(1j * self.voltage_angle)

    def to_dict(self) -> dict:
        return {
            "bus_id": self.bus_id,
            "voltage_magnitude": self.voltage_magnitude,
            "voltage_angle": self.voltage_angle,
            "load_power_real": self.load_power.real,
            "load_power_imag": self.load_power.imag,
            "generation_power_real": self.generation_power.real,
            "generation_power_imag": self.generation_power.imag,
            "bus_type": self.bus_type,
        }


@dataclass
class SwitchState:
    """Operational state of a single switch."""

    switch_id: str
    is_closed: bool = True
    from_bus: str = ""
    to_bus: str = ""
    trip_count: int = 0

    def to_dict(self) -> dict:
        return {
            "switch_id": self.switch_id,
            "is_closed": self.is_closed,
            "from_bus": self.from_bus,
            "to_bus": self.to_bus,
            "trip_count": self.trip_count,
        }


@dataclass
class TopologyState:
    """Current topology state derived from switching."""

    connected_components: List[List[str]] = field(default_factory=list)
    energized_buses: List[str] = field(default_factory=list)
    de_energized_buses: List[str] = field(default_factory=list)
    section_buses: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "connected_components": self.connected_components,
            "energized_buses": self.energized_buses,
            "de_energized_buses": self.de_energized_buses,
            "section_buses": self.section_buses,
        }


@dataclass
class GISAssetState:
    """GIS state reference for a single asset."""

    asset_id: str
    asset_type: str = ""
    electrical_id: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    zone_id: str = ""

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "electrical_id": self.electrical_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "zone_id": self.zone_id,
        }


@dataclass
class SimulationResults:
    """Results from engineering simulations."""

    load_flow_converged: bool = False
    load_flow_iterations: int = 0
    load_flow_bus_voltages: Dict[str, complex] = field(default_factory=dict)
    state_estimation_converged: bool = False
    state_estimation_bad_data: int = 0
    fault_currents: Dict[str, complex] = field(default_factory=dict)
    arc_flash_incident_energy: Dict[str, float] = field(default_factory=dict)
    protection_coordination_ok: bool = False

    def to_dict(self) -> dict:
        lf_voltages = {}
        for k, v in self.load_flow_bus_voltages.items():
            lf_voltages[str(k)] = {"mag": abs(v), "angle_deg": float(np.degrees(np.angle(v)))}
        fault_cur = {}
        for k, v in self.fault_currents.items():
            fault_cur[str(k)] = {"mag": abs(v), "angle_deg": float(np.degrees(np.angle(v)))}
        return {
            "load_flow_converged": self.load_flow_converged,
            "load_flow_iterations": self.load_flow_iterations,
            "load_flow_bus_voltages": lf_voltages,
            "state_estimation_converged": self.state_estimation_converged,
            "state_estimation_bad_data": self.state_estimation_bad_data,
            "fault_currents": fault_cur,
            "arc_flash_incident_energy": self.arc_flash_incident_energy,
            "protection_coordination_ok": self.protection_coordination_ok,
        }


@dataclass
class StateSnapshot:
    """
    Immutable snapshot of the entire digital twin state at a point in time.
    """

    version: int = 0
    timestamp: float = field(default_factory=time.time)
    simulation_time: float = 0.0

    # GIS Layer State
    gis_assets: Dict[str, GISAssetState] = field(default_factory=dict)
    gis_zones: Dict[str, str] = field(default_factory=dict)

    # Electrical Layer State
    bus_states: Dict[str, BusState] = field(default_factory=dict)
    ybus_shape: Tuple[int, int] = (0, 0)
    ybus_checksum: int = 0  # Hash of Ybus for change detection

    # ADMS Layer State
    switch_states: Dict[str, SwitchState] = field(default_factory=dict)
    topology: TopologyState = field(default_factory=TopologyState)
    scada_measurement_count: int = 0

    # Simulation Results
    simulation_results: SimulationResults = field(default_factory=SimulationResults)

    # Validation
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)

    # Metadata
    source_event: str = ""
    correlation_id: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "simulation_time": self.simulation_time,
            "gis_assets": {k: v.to_dict() for k, v in self.gis_assets.items()},
            "gis_zones": self.gis_zones,
            "bus_states": {k: v.to_dict() for k, v in self.bus_states.items()},
            "ybus_shape": list(self.ybus_shape),
            "ybus_checksum": self.ybus_checksum,
            "switch_states": {k: v.to_dict() for k, v in self.switch_states.items()},
            "topology": self.topology.to_dict(),
            "scada_measurement_count": self.scada_measurement_count,
            "simulation_results": self.simulation_results.to_dict(),
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
            "source_event": self.source_event,
            "correlation_id": self.correlation_id,
        }

    def is_layer_synced(self, layer: StateLayer) -> bool:
        """Check if a specific layer has valid state."""
        if layer == StateLayer.GIS:
            return len(self.gis_assets) > 0
        elif layer == StateLayer.ELECTRICAL:
            return len(self.bus_states) > 0 and self.ybus_shape[0] > 0
        elif layer == StateLayer.ADMS:
            return len(self.switch_states) > 0
        elif layer == StateLayer.SIMULATION:
            return (
                self.simulation_results.load_flow_converged
                or self.simulation_results.state_estimation_converged
            )
        return False

    def to_json(self) -> str:
        """Serialize snapshot to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class StateStore:
    """
    Versioned state store for the digital twin.

    Supports:
    - Immutable snapshots with version tracking
    - State rollback to any previous version
    - State diff computation between versions
    - Layer-specific state queries
    - Maximum history size with automatic pruning
    """

    def __init__(self, max_versions: int = 1000):
        self._snapshots: List[StateSnapshot] = []
        self._max_versions = max_versions
        self._current_version = 0
        self._lock = threading.Lock()

    def commit(self, snapshot: StateSnapshot) -> int:
        """
        Commit a new state snapshot.

        Returns the version number of the committed snapshot.
        """
        with self._lock:
            self._current_version += 1
            snapshot_copy = copy.deepcopy(snapshot)
            snapshot_copy.version = self._current_version
            self._snapshots.append(snapshot_copy)

            # Prune if exceeding max
            if len(self._snapshots) > self._max_versions:
                self._snapshots = self._snapshots[-self._max_versions :]

            return self._current_version

    def get_current(self) -> StateSnapshot | None:
        """Get the current (latest) state snapshot."""
        with self._lock:
            if not self._snapshots:
                return None
            ref = self._snapshots[-1]
        return copy.deepcopy(ref)

    def get_version(self, version: int) -> StateSnapshot | None:
        """Get a specific version of the state."""
        with self._lock:
            for s in self._snapshots:
                if s.version == version:
                    ref = s
                    break
            else:
                return None
        return copy.deepcopy(ref)

    def get_current_version(self) -> int:
        """Get the current version number."""
        with self._lock:
            return self._current_version

    def rollback(self, version: int) -> StateSnapshot | None:
        """
        Rollback state to a specific version.
        Removes all snapshots after the target version.
        Returns the target snapshot or None if not found.
        """
        with self._lock:
            target_idx = None
            for i, s in enumerate(self._snapshots):
                if s.version == version:
                    target_idx = i
                    break

            if target_idx is None:
                return None

            # Remove all snapshots after target
            self._snapshots = self._snapshots[: target_idx + 1]
            self._current_version = version
            # Return a deep copy to prevent external mutation of internal state.
            # Copy the reference under the lock, then deepcopy outside to
            # reduce lock contention on read-heavy paths.
            ref = self._snapshots[-1]
        return copy.deepcopy(ref)

    def diff(self, version_a: int, version_b: int) -> Dict[str, Any] | None:
        """
        Compute the diff between two state versions.

        Returns a dict describing the changes, or None if either version not found.
        """
        with self._lock:
            snap_a = self._get_version_unlocked(version_a)
            snap_b = self._get_version_unlocked(version_b)
            if not snap_a or not snap_b:
                return None
            snap_a_copy = copy.deepcopy(snap_a)
            snap_b_copy = copy.deepcopy(snap_b)

        changes = {
            "version_a": version_a,
            "version_b": version_b,
            "bus_changes": {},
            "switch_changes": {},
            "topology_changed": False,
            "simulation_changed": False,
            "validation_changed": False,
        }

        # Bus state changes
        all_bus_ids = set(snap_a_copy.bus_states.keys()) | set(snap_b_copy.bus_states.keys())
        for bid in all_bus_ids:
            ba = snap_a_copy.bus_states.get(bid)
            bb = snap_b_copy.bus_states.get(bid)
            if ba is None:
                changes["bus_changes"][bid] = {"action": "added"}
            elif bb is None:
                changes["bus_changes"][bid] = {"action": "removed"}
            elif (
                ba.voltage_magnitude != bb.voltage_magnitude
                or ba.voltage_angle != bb.voltage_angle
                or ba.load_power != bb.load_power
            ):
                changes["bus_changes"][bid] = {
                    "action": "modified",
                    "old_vm": ba.voltage_magnitude,
                    "new_vm": bb.voltage_magnitude,
                    "old_va": ba.voltage_angle,
                    "new_va": bb.voltage_angle,
                }

        # Switch state changes
        all_sw_ids = set(snap_a_copy.switch_states.keys()) | set(snap_b_copy.switch_states.keys())
        for sid in all_sw_ids:
            sa = snap_a_copy.switch_states.get(sid)
            sb = snap_b_copy.switch_states.get(sid)
            if sa is None:
                changes["switch_changes"][sid] = {"action": "added"}
            elif sb is None:
                changes["switch_changes"][sid] = {"action": "removed"}
            elif sa.is_closed != sb.is_closed:
                changes["switch_changes"][sid] = {
                    "action": "modified",
                    "old_closed": sa.is_closed,
                    "new_closed": sb.is_closed,
                }

        # Topology changed
        changes["topology_changed"] = (
            snap_a_copy.topology.energized_buses != snap_b_copy.topology.energized_buses
            or snap_a_copy.topology.de_energized_buses != snap_b_copy.topology.de_energized_buses
        )

        # Simulation changed
        changes["simulation_changed"] = (
            snap_a_copy.simulation_results.load_flow_converged
            != snap_b_copy.simulation_results.load_flow_converged
            or snap_a_copy.simulation_results.state_estimation_converged
            != snap_b_copy.simulation_results.state_estimation_converged
        )

        # Validation changed
        changes["validation_changed"] = (
            snap_a_copy.validation_passed != snap_b_copy.validation_passed
            or len(snap_a_copy.validation_errors) != len(snap_b_copy.validation_errors)
        )

        return changes

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get summary of recent state versions."""
        with self._lock:
            recent = self._snapshots[-limit:]
        return [
            {
                "version": s.version,
                "timestamp": s.timestamp,
                "simulation_time": s.simulation_time,
                "bus_count": len(s.bus_states),
                "switch_count": len(s.switch_states),
                "validation_passed": s.validation_passed,
                "source_event": s.source_event,
            }
            for s in recent
        ]

    def get_statistics(self) -> dict:
        """Get state store statistics."""
        with self._lock:
            current = self._snapshots[-1] if self._snapshots else None
            return {
                "current_version": self._current_version,
                "total_snapshots": len(self._snapshots),
                "max_versions": self._max_versions,
                "current_bus_count": len(current.bus_states) if current else 0,
                "current_switch_count": len(current.switch_states) if current else 0,
                "current_gis_asset_count": len(current.gis_assets) if current else 0,
                "current_validation_passed": current.validation_passed if current else None,
            }

    def clear(self) -> None:
        """Clear all state snapshots."""
        with self._lock:
            self._snapshots.clear()
            self._current_version = 0

    def _get_version_unlocked(self, version: int) -> StateSnapshot | None:
        """Get a specific version without acquiring lock (caller must hold lock)."""
        for s in self._snapshots:
            if s.version == version:
                return s
        return None
