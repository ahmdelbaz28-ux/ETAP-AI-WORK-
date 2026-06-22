import numpy as np

from curves.curves import IEC60255Curves


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
        value : float | complex
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

    def trip_time(self, value):
        """
        Calculate trip time for time-overcurrent relays.
        Returns time in seconds, or infinity if not picked up.
        """
        return float("inf")


class OvercurrentRelay(Relay):
    def __init__(
        self, relay_id, name="OvercurrentRelay", curve_type="standard_inverse", TMS=1.0, Ip=1.0
    ):
        """
        Overcurrent relay (50/51).

        Parameters:
        relay_id (int): Unique identifier.
        name (str): Name of the relay.
        curve_type (str): IEC curve type: 'standard_inverse', 'very_inverse', 'extremely_inverse', 'long_inverse'.
        TMS (float): Time multiplier setting.
        Ip (float): Pickup current in per-unit.
        """
        super().__init__(relay_id, name)
        self.curve_type = curve_type
        self.TMS = TMS
        self.Ip = Ip
        self.curves = IEC60255Curves()

    def pickup_logic(self, I):
        """
        Pickup if current meets or exceeds pickup setting.
        """
        return abs(I) >= self.Ip

    def trip_time(self, I):
        """
        Calculate trip time based on IEC curve.
        """
        if not self.pickup_logic(I):
            return float("inf")
        I_mag = abs(I)
        if self.curve_type == "standard_inverse":
            return self.curves.standard_inverse(self.TMS, I_mag, self.Ip)
        elif self.curve_type == "very_inverse":
            return self.curves.very_inverse(self.TMS, I_mag, self.Ip)
        elif self.curve_type == "extremely_inverse":
            return self.curves.extremely_inverse(self.TMS, I_mag, self.Ip)
        elif self.curve_type == "long_inverse":
            return self.curves.long_inverse(self.TMS, I_mag, self.Ip)
        else:
            raise ValueError(f"Unknown curve type: {self.curve_type}")

    def operate(self, I, t=0):
        """
        Operate the relay: if picked up and time exceeds trip time, then trip.
        For simplicity, we assume instantaneous trip if we pass the operate method with time.
        In practice, the relay would integrate over time.
        We'll implement: if picked up and t >= trip_time(I), then trip.
        """
        self.pickup = self.pickup_logic(I)
        if self.pickup and t >= self.trip_time(I):
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

    def pickup_logic(self, V, I):
        """
        Pickup if measured impedance is within the characteristic.
        Simplified: we assume a circular characteristic.
        """
        if I == 0:
            return False
        Z = V / I
        # Check if impedance magnitude is less than setting
        return abs(Z) < self.impedance_setting

    def operate(self, V, I):
        """
        Operate the distance relay.
        """
        self.pickup = self.pickup_logic(V, I)
        # For distance relays, trip is typically instantaneous if picked up.
        self.trip = self.pickup
        return self.trip


class DifferentialRelay(Relay):
    def __init__(self, relay_id, name="DifferentialRelay", Ip=0.1, slope1=0.2, slope2=0.5):
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
        self.Ip = Ip
        self.slope1 = slope1
        self.slope2 = slope2

    def pickup_logic(self, Ibias, Idiff):
        """
        Pickup based on differential current and bias current.
        Simplified characteristic: |Idiff| > Ip + slope1 * Ibias for Ibias < Ibias2, etc.
        We'll implement a simple two-slope characteristic.
        Assume Ibias2 = 2.0 for simplicity.
        """
        Ibias = abs(Ibias)
        Idiff = abs(Idiff)
        Ibias2 = 2.0  # breakpoint for slope2
        if Ibias < Ibias2:
            return Idiff > self.Ip + self.slope1 * Ibias
        else:
            return Idiff > self.Ip + self.slope1 * Ibias2 + self.slope2 * (Ibias - Ibias2)

    def operate(self, Ibias, Idiff):
        """
        Operate the differential relay.
        """
        self.pickup = self.pickup_logic(Ibias, Idiff)
        # Differential relays are typically instantaneous.
        self.trip = self.pickup
        return self.trip


class DirectionalRelay(Relay):
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

    def pickup_logic(self, V, I):
        """
        Pickup if voltage is above threshold and the phase angle of VI is within the forward direction.
        """
        if abs(V) < self.voltage_threshold or abs(I) < 1e-3:
            return False
        # Calculate the angle of VI
        S = V * np.conj(I)  # complex power
        angle_S = np.angle(S)
        # Check if angle is within +/- 90 degrees of the offset angle (forward direction)
        angle_diff = angle_S - self.angle_offset
        # Normalize to [-180, 180]
        angle_diff = np.arctan2(np.sin(angle_diff), np.cos(angle_diff))
        return abs(angle_diff) < np.radians(90)

    def operate(self, V, I):
        """
        Operate the directional relay.
        """
        self.pickup = self.pickup_logic(V, I)
        # Directional relays are often used with overcurrent relays, but we treat as instantaneous for simplicity.
        self.trip = self.pickup
        return self.trip
