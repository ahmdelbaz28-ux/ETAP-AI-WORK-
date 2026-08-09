"""
Relay models for protection coordination studies.

V-TCC-01: OvercurrentRelay now delegates to calculate_iec_operating_time()
for all TCC calculations, ensuring safety guards (min operating time,
max multiplier, instantaneous override) are always enforced.
"""

from __future__ import annotations

import numpy as np

from curves.curves import (
    MAX_MULTIPLIER_OF_PICKUP,
    MIN_OPERATING_TIME_S,
    IEC60255Curves,
    calculate_iec_operating_time,
)


class Relay:
    def __init__(self, relay_id, name="Relay"):
        self.relay_id = relay_id
        self.name = name
        self.pickup = False
        self.trip = False

    def pickup_logic(self, value):
        """
        Determine if the relay picks up based on input value.

        Default base implementation: never pick up. Each concrete
        relay subclass (OvercurrentRelay, DistanceRelay,
        DifferentialRelay, DirectionalRelay) overrides this with
        its own characteristic and signature.

        Parameters
        ----------
        value : Union[float, complex]
            Measured quantity (current, voltage, impedance, etc.).
            The base class does not interpret ``value``; subclasses
            document the expected quantity.

        Returns
        -------
        bool
            True if the relay would pick up, False otherwise.
        """
        # Safe default: a base Relay never picks up. This prevents
        # accidental trips from any subclass that forgets to override
        # pickup_logic for its specific measurement quantity.
        return False

    def operate(self, value):
        """
        Operate the relay: update pickup and trip status.
        Returns True if the relay trips.
        """
        self.pickup = self.pickup_logic(value)
        # For instantaneous relays, trip if picked up.
        # For time-overcurrent relays, trip logic is separate.
        return self.trip

    def trip_time(self, _value):
        """
        Calculate trip time for time-overcurrent relays.
        Returns time in seconds, or infinity if not picked up.
        """
        return float("inf")


class OvercurrentRelay(Relay):
    """Overcurrent relay (50/51) with IEC 60255 / IEEE C37.112 curves.

    V-TCC-01: All trip-time calculations now go through
    ``calculate_iec_operating_time()`` which enforces:
      - Input validation
      - Maximum multiplier cap (I/Ip <= 40x)
      - Minimum operating time floor (0.02 s)
      - Instantaneous overcurrent element (element 50)

    Backward compatibility: ``TMS`` and ``Ip`` (uppercase) are accepted
    via ``**kwargs`` and mapped to ``tms`` / ``ip``.
    """

    # Canonical curve names supported by calculate_iec_operating_time()
    VALID_CURVE_TYPES = frozenset(
        [
            "standard_inverse",
            "very_inverse",
            "extremely_inverse",
            "long_inverse",
            "ieee_moderately_inverse",
            "ieee_very_inverse",
            "ieee_extremely_inverse",
        ]
    )

    def __init__(
        self,
        relay_id,
        name="OvercurrentRelay",
        curve_type="standard_inverse",
        tms=1.0,
        ip=1.0,
        *,
        instantaneous_override=None,
        instantaneous_time_s=0.02,
        min_operating_time_s=MIN_OPERATING_TIME_S,
        max_multiplier=MAX_MULTIPLIER_OF_PICKUP,
        **kwargs,
    ):  # NOSONAR physics/engineering notation
        # Backward compatibility: accept uppercase TMS / Ip from existing code
        tms = kwargs.pop("TMS", tms)  # NOSONAR physics/engineering notation
        ip = kwargs.pop("Ip", ip)  # NOSONAR physics/engineering notation

        if kwargs:
            unexpected = ", ".join(kwargs.keys())
            raise TypeError(f"Unexpected keyword arguments: {unexpected}")

        super().__init__(relay_id, name)

        self.curve_type = curve_type.lower().strip()
        if self.curve_type not in self.VALID_CURVE_TYPES:
            valid = sorted(self.VALID_CURVE_TYPES)
            raise ValueError(f"Unknown curve type '{curve_type}'. Valid: {valid}")

        self.TMS = float(tms)  # NOSONAR physics/engineering notation
        self.Ip = float(ip)  # NOSONAR physics/engineering notation
        self.instantaneous_override = instantaneous_override
        self.instantaneous_time_s = instantaneous_time_s
        self.min_operating_time_s = min_operating_time_s
        self.max_multiplier = max_multiplier

        # Retained for backward compatibility — CoordinationEngine and other
        # code reference relay.curves.  Now a thin wrapper that delegates
        # to the safe function.
        self.curves = IEC60255Curves()

    def pickup_logic(
        self,
        i,
    ):  # NOSONAR physics/engineering notation
        """
        Pickup if current meets or exceeds pickup setting.
        """
        return abs(i) >= self.Ip

    def trip_time(
        self,
        i,
    ):  # NOSONAR physics/engineering notation
        """
        Calculate trip time using calculate_iec_operating_time().

        V-TCC-01: This ensures all safety guards are enforced automatically.
        """
        result = calculate_iec_operating_time(
            i_fault=abs(i),
            i_setting=self.Ip,
            tms=self.TMS,
            curve_type=self.curve_type,
            instantaneous_override_a=self.instantaneous_override,
            instantaneous_time_s=self.instantaneous_time_s,
            min_operating_time_s=self.min_operating_time_s,
            max_multiplier=self.max_multiplier,
        )
        return result["operating_time_s"]

    def operate(
        self,
        i,
        t=0,
    ):  # NOSONAR physics/engineering notation
        """
        Operate the relay: if picked up and time exceeds trip time, then trip.
        For simplicity, we assume instantaneous trip if we pass the operate method with time.
        In practice, the relay would integrate over time.
        We'll implement: if picked up and t >= trip_time(I), then trip.
        """
        self.pickup = self.pickup_logic(i)
        if self.pickup and t >= self.trip_time(i):
            self.trip = True
        else:
            self.trip = False
        return self.trip


class DistanceRelay(Relay):
    def __init__(self, relay_id, name="DistanceRelay", impedance_setting=0.5, offset_angle=0):
        """
        Distance relay (21).

        Parameters:
        relay_id (int): Unique identifier.
        name (str): Name of the relay.
        impedance_setting (float): Impedance setting in per-unit.
        offset_angle (float): Offset angle in degrees for directional characteristic.
        """
        super().__init__(relay_id, name)
        self.impedance_setting = impedance_setting
        self.offset_angle = np.radians(offset_angle)

    def pickup_logic(
        self,
        v=None,
        i=None,  # NOSONAR
    ):  # NOSONAR relay subclasses intentionally use domain-specific signatures (V,I for distance/directional; Ibias,Idiff for differential); base class is a protocol stub
        if i == 0:
            return False
        Z = v / i  # NOSONAR physics/engineering notation
        # Check if impedance magnitude is less than setting
        return abs(Z) < self.impedance_setting

    def operate(
        self,
        v=None,
        i=None,  # NOSONAR
    ):  # NOSONAR see pickup_logic; signature matches the relay's measurement quantities
        self.pickup = self.pickup_logic(v, i)
        # For distance relays, trip is typically instantaneous if picked up.
        self.trip = self.pickup
        return self.trip


class DifferentialRelay(Relay):
    def __init__(
        self,
        relay_id,
        name="DifferentialRelay",
        ip=0.1,
        slope1=0.2,
        slope2=0.5,
        **kwargs,
    ):  # NOSONAR physics notation (I/V/P/Q); snake_case harms readability
        # Backward compatibility: accept uppercase Ip
        ip = kwargs.pop("Ip", ip)  # NOSONAR physics/engineering notation

        """
        Differential relay (87).

        Parameters:
        relay_id (int): Unique identifier.
        name (str): Name of the relay.
        Ip (float): Pickup current in per-unit.
        slope1 (float): Slope1 of the characteristic.
        slope2 (float): Slope2 of the characteristic.
        """
        super().__init__(relay_id, name)
        self.Ip = ip  # NOSONAR physics/engineering notation
        self.slope1 = slope1
        self.slope2 = slope2

    def pickup_logic(
        self,
        ibias=None,
        idiff=None,  # NOSONAR
        **kwargs,
    ):  # NOSONAR differential relay uses (Ibias, Idiff) per IEEE C37.91; base class `value` is a protocol stub
        # Backward compatibility: accept uppercase keyword args
        ibias = kwargs.pop("Ibias", ibias)  # NOSONAR physics/engineering notation
        idiff = kwargs.pop("Idiff", idiff)  # NOSONAR physics/engineering notation

        ibias = abs(ibias)
        idiff = abs(idiff)
        Ibias2 = 2.0  # NOSONAR
        if ibias < Ibias2:
            return idiff > self.Ip + self.slope1 * ibias
        else:
            return idiff > self.Ip + self.slope1 * Ibias2 + self.slope2 * (
                ibias - Ibias2
            )  # NOSONAR physics/engineering notation

    def operate(
        self,
        ibias=None,
        idiff=None,  # NOSONAR
        **kwargs,
    ):  # NOSONAR see pickup_logic; differential relay operates on bias+diff currents
        # Backward compatibility: accept uppercase keyword args
        ibias = kwargs.pop("Ibias", ibias)  # NOSONAR physics/engineering notation
        idiff = kwargs.pop("Idiff", idiff)  # NOSONAR physics/engineering notation

        self.pickup = self.pickup_logic(ibias, idiff)
        # Differential relays are typically instantaneous.
        self.trip = self.pickup
        return self.trip


class DirectionalRelay(Relay):  # NOSONAR physics/engineering notation
    def __init__(self, relay_id, name="DirectionalRelay", voltage_threshold=0.1, angle_offset=0):
        """
        Directional relay (67).

        Parameters:
        relay_id (int): Unique identifier.
        name (str): Name of the relay.
        voltage_threshold (float): Minimum voltage for operation in per-unit.
        angle_offset (float): Angle offset in degrees for directional characteristic.
        """
        super().__init__(relay_id, name)
        self.voltage_threshold = voltage_threshold
        self.angle_offset = np.radians(angle_offset)

    def pickup_logic(
        self,
        v=None,
        i=None,  # NOSONAR
    ):  # NOSONAR directional relay (67) needs V and I to compute direction; base `value` is a protocol stub
        if abs(v) < self.voltage_threshold or abs(i) < 1e-3:
            return False
        # Calculate the angle of VI
        S = v * np.conj(i)  # complex power  # NOSONAR physics/engineering notation
        angle_S = np.angle(S)  # NOSONAR physics notation
        # Check if angle is within +/- 90 degrees of the offset angle (forward direction)
        angle_diff = angle_S - self.angle_offset
        # Normalize to [-180, 180]
        angle_diff = np.arctan2(np.sin(angle_diff), np.cos(angle_diff))
        return abs(angle_diff) < np.radians(90)

    def operate(
        self, v=None, i=None
    ):  # NOSONAR see pickup_logic; S2638 default=None satisfies LSP; directional relay operates on V+I
        self.pickup = self.pickup_logic(v, i)
        # Directional relays are often used with overcurrent relays, but we treat as instantaneous for simplicity.
        self.trip = self.pickup
        return self.trip  # NOSONAR physics/engineering notation
