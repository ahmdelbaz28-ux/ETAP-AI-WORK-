
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

from .event_bus import (
    EventBus, EventType, DomainEvent,
    SwitchOpened, SwitchClosed, FaultDetected,
    LoadChanged, PVChanged, BatteryDispatch, SCADAUpdateReceived,
    TopologyChanged, YbusRebuilt, LoadFlowCompleted,
    StateEstimationCompleted, FaultAnalysisCompleted,
    DigitalTwinStateUpdated, ValidationErrorEvent
)
from .state_store import StateStore, StateSnapshot
from .validation_gateway import (
    ValidationGateway, ValidationRule, ValidationResult,
    ValidationSeverity, DigitalTwinValidationError
)
from .digital_twin_core import (
    DigitalTwinState, SynchronizationEngine,
    ChangePropagationEngine, EventProcessor,
    TimeSteppedSimulator, LivePowerSystemEngine
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
