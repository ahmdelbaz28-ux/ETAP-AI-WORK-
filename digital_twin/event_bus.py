
"""
Event Bus - Event-Driven Architecture for Digital Twin
======================================================
Implements publish/subscribe event system for cross-layer communication.

Events follow the automatic workflow:
  SCADA Update -> Topology Update -> Ybus Rebuild -> Load Flow ->
  State Estimation Validation -> Short Circuit Refresh ->
  Arc Flash Refresh -> Protection Refresh -> Digital Twin State Update

Reference: IEC 61970 CIM Event Model, EPRI ADMS Architecture Guide
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
from collections import defaultdict


# ============================================================
# EVENT TYPES
# ============================================================

class EventType(Enum):
    """All event types in the digital twin event system."""
    # --- Input Events (from external systems) ---
    SWITCH_OPENED = "switch_opened"
    SWITCH_CLOSED = "switch_closed"
    FAULT_DETECTED = "fault_detected"
    LOAD_CHANGED = "load_changed"
    PV_CHANGED = "pv_changed"
    BATTERY_DISPATCH = "battery_dispatch"
    SCADA_UPDATE_RECEIVED = "scada_update_received"

    # --- Internal Propagation Events ---
    TOPOLOGY_CHANGED = "topology_changed"
    YBUS_REBUILT = "ybus_rebuilt"
    LOAD_FLOW_COMPLETED = "load_flow_completed"
    STATE_ESTIMATION_COMPLETED = "state_estimation_completed"
    FAULT_ANALYSIS_COMPLETED = "fault_analysis_completed"
    ARC_FLASH_REFRESHED = "arc_flash_refreshed"
    PROTECTION_REFRESHED = "protection_refreshed"

    # --- Output Events ---
    DIGITAL_TWIN_STATE_UPDATED = "digital_twin_state_updated"
    VALIDATION_ERROR = "validation_error"

    # --- Lifecycle Events ---
    SIMULATION_STARTED = "simulation_started"
    SIMULATION_STEP_COMPLETED = "simulation_step_completed"
    SIMULATION_STOPPED = "simulation_stopped"


# ============================================================
# DOMAIN EVENTS
# ============================================================

@dataclass
class DomainEvent:
    """Base domain event for the digital twin system."""
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "unknown"
    correlation_id: Optional[str] = None  # Links related events
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata
        }


@dataclass
class SwitchOpened(DomainEvent):
    """Event: A switch has been opened."""
    event_type: EventType = field(default=EventType.SWITCH_OPENED, init=False)
    switch_id: str = ""
    bus1: str = ""
    bus2: str = ""
    reason: str = ""

    def __post_init__(self):
        if self.event_type != EventType.SWITCH_OPENED:
            self.event_type = EventType.SWITCH_OPENED


@dataclass
class SwitchClosed(DomainEvent):
    """Event: A switch has been closed."""
    event_type: EventType = field(default=EventType.SWITCH_CLOSED, init=False)
    switch_id: str = ""
    bus1: str = ""
    bus2: str = ""
    reason: str = ""

    def __post_init__(self):
        if self.event_type != EventType.SWITCH_CLOSED:
            self.event_type = EventType.SWITCH_CLOSED


@dataclass
class FaultDetected(DomainEvent):
    """Event: A fault has been detected on the network."""
    event_type: EventType = field(default=EventType.FAULT_DETECTED, init=False)
    fault_type: str = ""  # three_phase, line_to_ground, etc.
    bus_id: str = ""
    fault_current_pu: float = 0.0
    tripped_switches: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.event_type != EventType.FAULT_DETECTED:
            self.event_type = EventType.FAULT_DETECTED


@dataclass
class LoadChanged(DomainEvent):
    """Event: A load has changed at a bus."""
    event_type: EventType = field(default=EventType.LOAD_CHANGED, init=False)
    bus_id: str = ""
    old_power: complex = complex(0, 0)
    new_power: complex = complex(0, 0)

    def __post_init__(self):
        if self.event_type != EventType.LOAD_CHANGED:
            self.event_type = EventType.LOAD_CHANGED


@dataclass
class PVChanged(DomainEvent):
    """Event: PV generation output has changed."""
    event_type: EventType = field(default=EventType.PV_CHANGED, init=False)
    bus_id: str = ""
    old_power: complex = complex(0, 0)
    new_power: complex = complex(0, 0)
    irradiance: float = 0.0

    def __post_init__(self):
        if self.event_type != EventType.PV_CHANGED:
            self.event_type = EventType.PV_CHANGED


@dataclass
class BatteryDispatch(DomainEvent):
    """Event: Battery storage dispatch command."""
    event_type: EventType = field(default=EventType.BATTERY_DISPATCH, init=False)
    bus_id: str = ""
    power_command: complex = complex(0, 0)
    soc_before: float = 0.0
    soc_after: float = 0.0

    def __post_init__(self):
        if self.event_type != EventType.BATTERY_DISPATCH:
            self.event_type = EventType.BATTERY_DISPATCH


@dataclass
class SCADAUpdateReceived(DomainEvent):
    """Event: SCADA measurement update received."""
    event_type: EventType = field(default=EventType.SCADA_UPDATE_RECEIVED, init=False)
    measurements: List[Dict[str, Any]] = field(default_factory=list)
    switch_statuses: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.event_type != EventType.SCADA_UPDATE_RECEIVED:
            self.event_type = EventType.SCADA_UPDATE_RECEIVED


@dataclass
class TopologyChanged(DomainEvent):
    """Event: Network topology has changed (internal propagation)."""
    event_type: EventType = field(default=EventType.TOPOLOGY_CHANGED, init=False)
    change_description: str = ""
    affected_buses: List[str] = field(default_factory=list)
    affected_switches: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.event_type != EventType.TOPOLOGY_CHANGED:
            self.event_type = EventType.TOPOLOGY_CHANGED


@dataclass
class YbusRebuilt(DomainEvent):
    """Event: Ybus matrix has been rebuilt (internal propagation)."""
    event_type: EventType = field(default=EventType.YBUS_REBUILT, init=False)
    matrix_size: int = 0
    sequences_rebuilt: List[str] = field(default_factory=lambda: ['1'])

    def __post_init__(self):
        if self.event_type != EventType.YBUS_REBUILT:
            self.event_type = EventType.YBUS_REBUILT


@dataclass
class LoadFlowCompleted(DomainEvent):
    """Event: Load flow analysis completed (internal propagation)."""
    event_type: EventType = field(default=EventType.LOAD_FLOW_COMPLETED, init=False)
    converged: bool = False
    iterations: int = 0
    bus_voltages: Dict[str, complex] = field(default_factory=dict)

    def __post_init__(self):
        if self.event_type != EventType.LOAD_FLOW_COMPLETED:
            self.event_type = EventType.LOAD_FLOW_COMPLETED


@dataclass
class StateEstimationCompleted(DomainEvent):
    """Event: State estimation completed (internal propagation)."""
    event_type: EventType = field(default=EventType.STATE_ESTIMATION_COMPLETED, init=False)
    converged: bool = False
    bad_data_count: int = 0
    max_residual: float = 0.0

    def __post_init__(self):
        if self.event_type != EventType.STATE_ESTIMATION_COMPLETED:
            self.event_type = EventType.STATE_ESTIMATION_COMPLETED


@dataclass
class FaultAnalysisCompleted(DomainEvent):
    """Event: Fault analysis completed (internal propagation)."""
    event_type: EventType = field(default=EventType.FAULT_ANALYSIS_COMPLETED, init=False)
    fault_type: str = ""
    fault_bus: str = ""
    fault_current_pu: float = 0.0

    def __post_init__(self):
        if self.event_type != EventType.FAULT_ANALYSIS_COMPLETED:
            self.event_type = EventType.FAULT_ANALYSIS_COMPLETED


@dataclass
class ArcFlashRefreshed(DomainEvent):
    """Event: Arc flash analysis refreshed (internal propagation)."""
    event_type: EventType = field(default=EventType.ARC_FLASH_REFRESHED, init=False)
    bus_count: int = 0
    max_incident_energy: float = 0.0

    def __post_init__(self):
        if self.event_type != EventType.ARC_FLASH_REFRESHED:
            self.event_type = EventType.ARC_FLASH_REFRESHED


@dataclass
class ProtectionRefreshed(DomainEvent):
    """Event: Protection coordination refreshed (internal propagation)."""
    event_type: EventType = field(default=EventType.PROTECTION_REFRESHED, init=False)
    relay_count: int = 0
    coordination_issues: int = 0

    def __post_init__(self):
        if self.event_type != EventType.PROTECTION_REFRESHED:
            self.event_type = EventType.PROTECTION_REFRESHED


@dataclass
class DigitalTwinStateUpdated(DomainEvent):
    """Event: Digital twin state has been fully updated (output event)."""
    event_type: EventType = field(default=EventType.DIGITAL_TWIN_STATE_UPDATED, init=False)
    state_version: int = 0
    layers_synchronized: bool = False
    validation_passed: bool = False

    def __post_init__(self):
        if self.event_type != EventType.DIGITAL_TWIN_STATE_UPDATED:
            self.event_type = EventType.DIGITAL_TWIN_STATE_UPDATED


@dataclass
class ValidationErrorEvent(DomainEvent):
    """Event: Validation error detected in the digital twin."""
    event_type: EventType = field(default=EventType.VALIDATION_ERROR, init=False)
    errors: List[str] = field(default_factory=list)
    layer: str = ""  # gis, electrical, adms

    def __post_init__(self):
        if self.event_type != EventType.VALIDATION_ERROR:
            self.event_type = EventType.VALIDATION_ERROR


# ============================================================
# EVENT BUS
# ============================================================

class EventBus:
    """
    Publish/Subscribe event bus for digital twin communication.

    Supports:
    - Event publishing with synchronous handler dispatch
    - Topic-based subscriptions (by EventType)
    - Wildcard subscriptions (all events)
    - Event history and replay
    - Handler priority ordering
    - Error isolation (one handler failure does not block others)
    """

    def __init__(self, max_history: int = 10000):
        self._subscribers: Dict[EventType, List[tuple]] = defaultdict(list)
        self._wildcard_subscribers: List[tuple] = []
        self._history: List[DomainEvent] = []
        self._max_history = max_history
        self._handler_errors: List[Dict[str, Any]] = []
        self._publishing = False
        self._event_queue: List[DomainEvent] = []

    def subscribe(self, event_type: EventType,
                  handler: Callable[[DomainEvent], None],
                  priority: int = 0) -> str:
        """
        Subscribe a handler to an event type.

        Parameters:
        event_type: The event type to subscribe to.
        handler: Callback function that receives the event.
        priority: Handler priority (higher = called first). Default 0.

        Returns:
        str: Subscription ID for unsubscription.
        """
        sub_id = str(uuid.uuid4())
        entry = (priority, sub_id, handler)
        self._subscribers[event_type].append(entry)
        self._subscribers[event_type].sort(key=lambda x: -x[0])
        return sub_id

    def subscribe_all(self, handler: Callable[[DomainEvent], None],
                      priority: int = 0) -> str:
        """Subscribe to all events (wildcard)."""
        sub_id = str(uuid.uuid4())
        entry = (priority, sub_id, handler)
        self._wildcard_subscribers.append(entry)
        self._wildcard_subscribers.sort(key=lambda x: -x[0])
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove a subscription by ID."""
        for event_type, entries in self._subscribers.items():
            for i, (_, sid, _) in enumerate(entries):
                if sid == sub_id:
                    entries.pop(i)
                    return True
        for i, (_, sid, _) in enumerate(self._wildcard_subscribers):
            if sid == sub_id:
                self._wildcard_subscribers.pop(i)
                return True
        return False

    def publish(self, event: DomainEvent) -> List[Exception]:
        """
        Publish an event to all subscribers.

        Handlers are called synchronously in priority order.
        Errors in one handler do not block other handlers.

        Returns:
        List of exceptions raised by handlers.
        """
        self._add_to_history(event)
        errors = []

        # Call wildcard subscribers first
        for _, _, handler in self._wildcard_subscribers:
            try:
                handler(event)
            except Exception as e:
                errors.append(e)
                self._handler_errors.append({
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "handler": str(handler),
                    "error": str(e),
                    "timestamp": time.time()
                })

        # Call type-specific subscribers
        for _, _, handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                errors.append(e)
                self._handler_errors.append({
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "handler": str(handler),
                    "error": str(e),
                    "timestamp": time.time()
                })

        return errors

    def _add_to_history(self, event: DomainEvent) -> None:
        """Add event to history with size limit."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(self, event_type: EventType = None,
                    limit: int = 100) -> List[DomainEvent]:
        """Get event history, optionally filtered by type."""
        if event_type:
            filtered = [e for e in self._history if e.event_type == event_type]
        else:
            filtered = list(self._history)
        return filtered[-limit:]

    def get_handler_errors(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get handler error history."""
        return self._handler_errors[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()
        self._handler_errors.clear()

    def get_statistics(self) -> dict:
        """Get event bus statistics."""
        type_counts = defaultdict(int)
        for event in self._history:
            type_counts[event.event_type.value] += 1
        return {
            "total_events_published": len(self._history),
            "subscriber_count": sum(len(v) for v in self._subscribers.values()) + len(self._wildcard_subscribers),
            "event_type_counts": dict(type_counts),
            "handler_error_count": len(self._handler_errors),
            "event_types_with_subscribers": list(self._subscribers.keys())
        }

    def reset(self) -> None:
        """Reset the event bus."""
        self._subscribers.clear()
        self._wildcard_subscribers.clear()
        self._history.clear()
        self._handler_errors.clear()
