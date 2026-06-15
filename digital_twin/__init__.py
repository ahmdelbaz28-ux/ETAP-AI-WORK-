
"""
Digital Twin Package - ADMS + ETAP GIS + Power System Engineering
=================================================================
Unified synchronization layer for the 4-layer utility platform.

Layers:
  1. GIS Spatial Layer (Spatial Truth)
  2. Electrical Network Model Layer (Mathematical Truth)
  3. Real-time ADMS Control Layer (Operational Truth)
  4. Engineering Simulation Layer

Hard Constraints:
  - GIS layer is the spatial truth
  - Electrical model is the mathematical truth
  - ADMS is the operational truth
  - All three must remain synchronized
  - Any inconsistency triggers validation errors
"""

from .digital_twin_core import (
    ChangePropagationEngine,
    DigitalTwinState,
    EventProcessor,
    LivePowerSystemEngine,
    SynchronizationEngine,
    TimeSteppedSimulator,
)
from .event_bus import (
    BatteryDispatch,
    DigitalTwinStateUpdated,
    DomainEvent,
    EventBus,
    EventType,
    FaultAnalysisCompleted,
    FaultDetected,
    LoadChanged,
    LoadFlowCompleted,
    PVChanged,
    SCADAUpdateReceived,
    StateEstimationCompleted,
    SwitchClosed,
    SwitchOpened,
    TopologyChanged,
    ValidationErrorEvent,
    YbusRebuilt,
)
from .state_store import StateSnapshot, StateStore
from .validation_gateway import (
    DigitalTwinValidationError,
    ValidationGateway,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)

__all__ = [
    "EventBus", "EventType", "DomainEvent",
    "SwitchOpened", "SwitchClosed", "FaultDetected",
    "LoadChanged", "PVChanged", "BatteryDispatch", "SCADAUpdateReceived",
    "TopologyChanged", "YbusRebuilt", "LoadFlowCompleted",
    "StateEstimationCompleted", "FaultAnalysisCompleted",
    "DigitalTwinStateUpdated", "ValidationErrorEvent",
    "StateStore", "StateSnapshot",
    "ValidationGateway", "ValidationRule", "ValidationResult",
    "ValidationSeverity", "DigitalTwinValidationError",
    "DigitalTwinState", "SynchronizationEngine",
    "ChangePropagationEngine", "EventProcessor",
    "TimeSteppedSimulator", "LivePowerSystemEngine",
]
