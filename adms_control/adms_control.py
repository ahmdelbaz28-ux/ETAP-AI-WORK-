"""
ADMS Control Engine - Real-Time Distribution Management
========================================================
Implements feeder switching, load transfer, fault isolation
and service restoration (FLISR) for ADMS.

Reference: IEEE C37.118, IEC 61850, EPRI ADMS Guide
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

# ============================================================
# ADMS CONTROL TYPES
# ============================================================


class SwitchingActionType(Enum):
    CLOSE = "close"
    OPEN = "open"
    TRIP = "trip"
    LOCKOUT = "lockout"


class FLISRStage(Enum):
    FAULT_DETECTION = "fault_detection"
    FAULT_ISOLATION = "fault_isolation"
    SERVICE_RESTORATION = "service_restoration"
    COMPLETED = "completed"
    FAILED = "failed"


class ControlCommandStatus(Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class SwitchingAction:
    """Single switching action command."""

    action_id: str
    device_id: str
    action_type: SwitchingActionType
    target_status: str  # expected status after action
    timestamp: float = field(default_factory=time.time)
    status: ControlCommandStatus = ControlCommandStatus.PENDING
    reason: str = ""
    rollback_action_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "device_id": self.device_id,
            "action_type": self.action_type.value,
            "target_status": self.target_status,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "reason": self.reason,
            "rollback_action_id": self.rollback_action_id,
        }


@dataclass
class SwitchingSequence:
    """Ordered sequence of switching actions."""

    sequence_id: str
    actions: List[SwitchingAction] = field(default_factory=list)
    description: str = ""
    estimated_duration_s: float = 0.0
    created_at: float = field(default_factory=time.time)

    def add_action(self, action: SwitchingAction) -> None:
        self.actions.append(action)

    def to_dict(self) -> dict:
        return {
            "sequence_id": self.sequence_id,
            "actions": [a.to_dict() for a in self.actions],
            "description": self.description,
            "estimated_duration_s": self.estimated_duration_s,
        }


@dataclass
class FLISRResult:
    """Result of FLISR operation."""

    fault_section: Optional[str] = None
    isolated_sections: List[str] = field(default_factory=list)
    restored_sections: List[str] = field(default_factory=list)
    unrestored_sections: List[str] = field(default_factory=list)
    switching_sequence: Optional[SwitchingSequence] = None
    stage: FLISRStage = FLISRStage.FAULT_DETECTION
    customers_restored: int = 0
    customers_affected: int = 0
    restoration_time_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "fault_section": self.fault_section,
            "isolated_sections": self.isolated_sections,
            "restored_sections": self.restored_sections,
            "unrestored_sections": self.unrestored_sections,
            "stage": self.stage.value,
            "customers_restored": self.customers_restored,
            "customers_affected": self.customers_affected,
            "restoration_time_s": self.restoration_time_s,
        }


# ============================================================
# NETWORK TOPOLOGY PROCESSOR
# ============================================================


class TopologyProcessor:
    """
    Processes network topology based on switching states.
    Identifies energized/de-energized islands and connected components.
    """

    def __init__(self):
        self.bus_connections: Dict[str, Set[str]] = {}  # bus -> connected buses
        self.section_buses: Dict[str, Set[str]] = {}  # section -> bus IDs
        self.bus_section: Dict[str, str] = {}  # bus -> section ID
        self.switches: Dict[str, Tuple[str, str]] = {}  # switch_id -> (bus1, bus2)

    def add_connection(self, bus1: str, bus2: str, switch_id: str = None) -> None:
        """Add a connection between two buses."""
        if bus1 not in self.bus_connections:
            self.bus_connections[bus1] = set()
        if bus2 not in self.bus_connections:
            self.bus_connections[bus2] = set()
        self.bus_connections[bus1].add(bus2)
        self.bus_connections[bus2].add(bus1)
        if switch_id:
            self.switches[switch_id] = (bus1, bus2)

    def remove_connection(self, bus1: str, bus2: str) -> None:
        """Remove a connection between two buses."""
        if bus1 in self.bus_connections:
            self.bus_connections[bus1].discard(bus2)
        if bus2 in self.bus_connections:
            self.bus_connections[bus2].discard(bus1)

    def open_switch(self, switch_id: str) -> None:
        """Open a switch, removing the connection."""
        if switch_id in self.switches:
            bus1, bus2 = self.switches[switch_id]
            self.remove_connection(bus1, bus2)

    def close_switch(self, switch_id: str) -> None:
        """Close a switch, restoring the connection."""
        if switch_id in self.switches:
            bus1, bus2 = self.switches[switch_id]
            self.add_connection(bus1, bus2, switch_id)

    def find_connected_components(self) -> List[Set[str]]:
        """Find all connected components using BFS with O(1) deque.popleft()."""
        visited = set()
        components = []
        for bus in self.bus_connections:
            if bus not in visited:
                component = set()
                queue = deque([bus])
                while queue:
                    current = queue.popleft()
                    if current in visited:
                        continue
                    visited.add(current)
                    component.add(current)
                    for neighbor in self.bus_connections.get(current, set()):
                        if neighbor not in visited:
                            queue.append(neighbor)
                components.append(component)
        return components

    def find_path(self, start: str, end: str) -> Optional[List[str]]:
        """Find shortest path between two buses using BFS with O(1) deque.popleft()."""
        if start not in self.bus_connections or end not in self.bus_connections:
            return None
        visited = {start}
        queue = deque([(start, [start])])
        while queue:
            current, path = queue.popleft()
            if current == end:
                return path
            for neighbor in self.bus_connections.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None

    def get_switches_on_path(self, path: List[str]) -> List[str]:
        """Get all switches along a path."""
        switches = []
        for i in range(len(path) - 1):
            bus1, bus2 = path[i], path[i + 1]
            for sid, (b1, b2) in self.switches.items():
                if (b1 == bus1 and b2 == bus2) or (b1 == bus2 and b2 == bus1):
                    switches.append(sid)
        return switches

    def identify_sections(self) -> Dict[str, Set[str]]:
        """Identify network sections (connected components)."""
        components = self.find_connected_components()
        self.section_buses = {}
        self.bus_section = {}
        for idx, comp in enumerate(components):
            section_id = f"section_{idx}"
            self.section_buses[section_id] = comp
            for bus in comp:
                self.bus_section[bus] = section_id
        return self.section_buses


# ============================================================
# ADMS CONTROL ENGINE
# ============================================================


class ADMSControlEngine:
    """
    ADMS Control Engine with FLISR capability.

    Implements:
    - Feeder switching operations
    - Load transfer logic
    - Fault isolation and service restoration (FLISR)
    - Topology-aware control
    """

    def __init__(self, topology: TopologyProcessor = None):
        self.topology = topology or TopologyProcessor()
        self.switching_history: List[SwitchingSequence] = []
        self.active_flisr: Optional[FLISRResult] = None
        self.source_buses: Set[str] = set()  # Buses with generation/source
        self.feeder_roots: Dict[str, str] = {}  # feeder_id -> root_bus
        self.section_loads: Dict[str, float] = {}  # section_id -> load MW
        self.section_customers: Dict[str, int] = {}  # section_id -> customer count

    def register_source_bus(self, bus_id: str) -> None:
        """Register a bus as a source (substation feed point)."""
        self.source_buses.add(bus_id)

    def register_feeder(self, feeder_id: str, root_bus: str) -> None:
        """Register a feeder with its root bus."""
        self.feeder_roots[feeder_id] = root_bus
        self.source_buses.add(root_bus)

    def set_section_load(self, section_id: str, load_mw: float, customers: int = 0) -> None:
        """Set load and customer count for a section."""
        self.section_loads[section_id] = load_mw
        self.section_customers[section_id] = customers

    # --- Feeder Switching ---

    def create_switching_sequence(
        self, actions: List[Tuple[str, SwitchingActionType, str]], description: str = ""
    ) -> SwitchingSequence:
        """
        Create a switching sequence from a list of actions.

        Parameters:
        actions: List of (device_id, action_type, reason) tuples.
        description: Description of the switching sequence.

        Returns:
        SwitchingSequence
        """
        seq = SwitchingSequence(
            sequence_id=f"seq_{int(time.time() * 1000)}", description=description
        )
        for i, (device_id, action_type, reason) in enumerate(actions):
            action = SwitchingAction(
                action_id=f"act_{i}",
                device_id=device_id,
                action_type=action_type,
                target_status="closed" if action_type == SwitchingActionType.CLOSE else "open",
                reason=reason,
            )
            seq.add_action(action)
        return seq

    def execute_switching_sequence(self, sequence: SwitchingSequence, scada_db=None) -> bool:
        """
        Execute a switching sequence.
        If any action fails, rollback all previous actions.

        Parameters:
        sequence: SwitchingSequence to execute.
        scada_db: Optional SCADA database for status updates.

        Returns:
        True if all actions succeeded.
        """
        executed = []
        for action in sequence.actions:
            success = self._execute_single_action(action, scada_db)
            if success:
                action.status = ControlCommandStatus.EXECUTED
                executed.append(action)
            else:
                action.status = ControlCommandStatus.FAILED
                # Rollback
                for prev_action in reversed(executed):
                    self._rollback_action(prev_action, scada_db)
                    prev_action.status = ControlCommandStatus.ROLLED_BACK
                return False

        self.switching_history.append(sequence)
        return True

    def _execute_single_action(self, action: SwitchingAction, scada_db=None) -> bool:
        """Execute a single switching action on topology."""
        device_id = action.device_id
        if device_id not in self.topology.switches:
            return False

        if action.action_type in (SwitchingActionType.OPEN, SwitchingActionType.TRIP):
            self.topology.open_switch(device_id)
        elif action.action_type == SwitchingActionType.CLOSE:
            self.topology.close_switch(device_id)

        if scada_db:
            from scada_model.scada_model import SwitchStatus

            status_map = {
                SwitchingActionType.OPEN: SwitchStatus.OPEN,
                SwitchingActionType.CLOSE: SwitchStatus.CLOSED,
                SwitchingActionType.TRIP: SwitchStatus.TRIPPED,
                SwitchingActionType.LOCKOUT: SwitchStatus.LOCKED_OUT,
            }
            scada_db.operate_switch(device_id, status_map[action.action_type])

        return True

    def _rollback_action(self, action: SwitchingAction, scada_db=None) -> None:
        """Rollback a single switching action."""
        device_id = action.device_id
        if device_id not in self.topology.switches:
            return
        if action.action_type in (SwitchingActionType.OPEN, SwitchingActionType.TRIP):
            self.topology.close_switch(device_id)
        elif action.action_type == SwitchingActionType.CLOSE:
            self.topology.open_switch(device_id)

    # --- Load Transfer ---

    def plan_load_transfer(
        self, from_feeder: str, to_feeder: str, section_id: str
    ) -> Optional[SwitchingSequence]:
        """
        Plan a load transfer from one feeder to another.

        Parameters:
        from_feeder: Source feeder ID.
        to_feeder: Target feeder ID.
        section_id: Section to transfer.

        Returns:
        SwitchingSequence or None if not possible.
        """
        from_root = self.feeder_roots.get(from_feeder)
        to_root = self.feeder_roots.get(to_feeder)
        if not from_root or not to_root:
            return None

        # Find path from target feeder to section
        path = self.topology.find_path(
            to_root,
            list(self.topology.section_buses.get(section_id, set()))[0]
            if section_id in self.topology.section_buses
            else to_root,
        )
        if not path:
            return None

        actions = [
            (sid, SwitchingActionType.CLOSE, "Load transfer: close tie switch")
            for sid in self.topology.get_switches_on_path(path)
        ]

        return self.create_switching_sequence(
            actions,
            description=f"Load transfer: section {section_id} from {from_feeder} to {to_feeder}",
        )

    # --- FLISR ---

    def detect_fault_section(self, tripped_switch_ids: List[str]) -> Optional[str]:
        """
        Identify the faulted section based on tripped switches.

        Uses topology to find the section between tripped protection devices.
        """
        if not tripped_switch_ids:
            return None

        # Get buses on either side of each tripped switch
        fault_buses = set()
        for sid in tripped_switch_ids:
            if sid in self.topology.switches:
                bus1, bus2 = self.topology.switches[sid]
                fault_buses.add(bus1)
                fault_buses.add(bus2)

        # The fault section is the one containing these buses
        self.topology.identify_sections()
        for section_id, buses in self.topology.section_buses.items():
            if fault_buses & buses:
                return section_id
        return None

    def isolate_fault(self, fault_section: str) -> Optional[SwitchingSequence]:
        """
        Create switching sequence to isolate the faulted section.

        Opens all switches connecting the faulted section to healthy sections.
        """
        actions = []
        fault_buses = self.topology.section_buses.get(fault_section, set())

        for switch_id, (bus1, bus2) in self.topology.switches.items():
            if (bus1 in fault_buses and bus2 not in fault_buses) or (
                bus2 in fault_buses and bus1 not in fault_buses
            ):
                actions.append(
                    (
                        switch_id,
                        SwitchingActionType.OPEN,
                        f"Fault isolation: open boundary switch for section {fault_section}",
                    )
                )

        if not actions:
            return None

        return self.create_switching_sequence(
            actions, description=f"Fault isolation for section {fault_section}"
        )

    def plan_restoration(
        self, fault_section: str, de_energized_sections: List[str] = None
    ) -> Optional[SwitchingSequence]:
        """
        Plan service restoration for de-energized sections after fault isolation.

        Attempts to find alternative feed paths via normally-open tie switches.
        """
        sections_to_restore = de_energized_sections or []
        if not sections_to_restore:
            return None

        actions = []
        restored = []

        for section_id in sections_to_restore:
            if section_id == fault_section:
                continue

            section_buses = self.topology.section_buses.get(section_id, set())
            if not section_buses:
                continue

            # Find tie switches connecting to energized sections
            for switch_id, (bus1, bus2) in self.topology.switches.items():
                if bus1 in section_buses and bus2 not in section_buses:
                    # Check if bus2's section is energized (connected to source)
                    bus2_section = self.topology.bus_section.get(bus2)
                    if bus2_section and bus2_section != fault_section:
                        bus2_buses = self.topology.section_buses.get(bus2_section, set())
                        if bus2_buses & self.source_buses or any(
                            self.topology.find_path(bus, src)
                            for bus in bus2_buses
                            for src in self.source_buses
                        ):
                            actions.append(
                                (
                                    switch_id,
                                    SwitchingActionType.CLOSE,
                                    f"Restoration: close tie switch for section {section_id}",
                                )
                            )
                            restored.append(section_id)
                            break

        if not actions:
            return None

        return self.create_switching_sequence(
            actions, description=f"Service restoration for sections: {restored}"
        )

    def execute_flisr(self, tripped_switch_ids: List[str], scada_db=None) -> FLISRResult:
        """
        Execute full FLISR sequence:
        1. Detect fault section
        2. Isolate fault
        3. Restore service to healthy sections

        Parameters:
        tripped_switch_ids: IDs of switches that tripped due to fault.
        scada_db: Optional SCADA database.

        Returns:
        FLISRResult
        """
        start_time = time.time()
        result = FLISRResult()

        # Stage 1: Fault Detection
        result.stage = FLISRStage.FAULT_DETECTION
        fault_section = self.detect_fault_section(tripped_switch_ids)
        if not fault_section:
            result.stage = FLISRStage.FAILED
            return result
        result.fault_section = fault_section

        # Stage 2: Fault Isolation
        result.stage = FLISRStage.FAULT_ISOLATION
        isolation_seq = self.isolate_fault(fault_section)
        if isolation_seq:
            success = self.execute_switching_sequence(isolation_seq, scada_db)
            if not success:
                result.stage = FLISRStage.FAILED
                return result
            result.isolated_sections.append(fault_section)

        # Update topology after isolation
        self.topology.identify_sections()

        # Find de-energized sections (not connected to any source)
        de_energized = []
        for section_id, buses in self.topology.section_buses.items():
            if section_id == fault_section:
                continue
            is_energized = any(
                self.topology.find_path(bus, src) for bus in buses for src in self.source_buses
            )
            if not is_energized:
                de_energized.append(section_id)

        # Stage 3: Service Restoration
        result.stage = FLISRStage.SERVICE_RESTORATION
        if de_energized:
            restoration_seq = self.plan_restoration(fault_section, de_energized)
            if restoration_seq:
                success = self.execute_switching_sequence(restoration_seq, scada_db)
                if success:
                    result.restored_sections = de_energized
                    for sec in de_energized:
                        result.customers_restored += self.section_customers.get(sec, 0)
                else:
                    result.unrestored_sections = de_energized
            else:
                result.unrestored_sections = de_energized

        for sec in result.unrestored_sections:
            result.customers_affected += self.section_customers.get(sec, 0)
        result.customers_affected += self.section_customers.get(fault_section, 0)

        result.restoration_time_s = time.time() - start_time
        result.stage = FLISRStage.COMPLETED
        self.active_flisr = result
        return result

    # --- Topology Analysis ---

    def get_energized_sections(self) -> List[str]:
        """Get list of currently energized sections."""
        self.topology.identify_sections()
        energized = []
        for section_id, buses in self.topology.section_buses.items():
            if any(self.topology.find_path(bus, src) for bus in buses for src in self.source_buses):
                energized.append(section_id)
        return energized

    def get_de_energized_sections(self) -> List[str]:
        """Get list of currently de-energized sections."""
        all_sections = set(self.topology.section_buses.keys())
        return list(all_sections - set(self.get_energized_sections()))

    def get_feeder_loading(self) -> Dict[str, float]:
        """Get total loading per feeder in MW."""
        loading = {}
        for feeder_id, root_bus in self.feeder_roots.items():
            total_load = 0.0
            for section_id, buses in self.topology.section_buses.items():
                if any(self.topology.find_path(bus, root_bus) for bus in buses):
                    total_load += self.section_loads.get(section_id, 0.0)
            loading[feeder_id] = total_load
        return loading

    def get_statistics(self) -> dict:
        """Get ADMS control engine statistics."""
        return {
            "total_switching_sequences": len(self.switching_history),
            "source_buses": len(self.source_buses),
            "registered_feeders": len(self.feeder_roots),
            "energized_sections": len(self.get_energized_sections()),
            "de_energized_sections": len(self.get_de_energized_sections()),
            "active_flisr": self.active_flisr.to_dict() if self.active_flisr else None,
        }
