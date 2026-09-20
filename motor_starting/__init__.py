"""
motor_starting — Dynamic Time-Domain Motor Starting Simulation (IEEE 399).
"""

from motor_starting.engine import (
    MotorStartingEngine,
    MotorStartingResult,
    MotorStartingTrajectory,
)
from motor_starting.motor_models import (
    DynamicMotorParams,
    InductionMotorDynamics,
    LoadProfile,
    MechanicalLoadModel,
    StartingMethod,
)

__all__ = [
    "DynamicMotorParams",
    "InductionMotorDynamics",
    "LoadProfile",
    "MechanicalLoadModel",
    "StartingMethod",
    "MotorStartingEngine",
    "MotorStartingResult",
    "MotorStartingTrajectory",
]
