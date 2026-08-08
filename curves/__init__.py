"""Curves - IEC 60255 and IEEE C37.112 time-current characteristic curves.

Provides the safe entry point ``calculate_iec_operating_time`` for all TCC
calculations, along with the backward-compatible ``IEC60255Curves`` class
and safety-guard constants.
"""

from curves.curves import (
    IEC60255Curves,
    calculate_iec_operating_time,
    MAX_MULTIPLIER_OF_PICKUP,
    MIN_OPERATING_TIME_S,
)

__all__ = [
    "IEC60255Curves",
    "calculate_iec_operating_time",
    "MAX_MULTIPLIER_OF_PICKUP",
    "MIN_OPERATING_TIME_S",
]

"""Curves - IEC 60255 protection relay curve implementations.

Provides standard time-current characteristic curves used in
protection relay coordination studies per IEC 60255.
"""

from curves.curves import IEC60255Curves

__all__ = ["IEC60255Curves"]
