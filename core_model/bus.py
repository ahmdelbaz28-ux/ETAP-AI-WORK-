import numpy as np


class Bus:
    __slots__ = (
        "bus_id",
        "voltage_magnitude",
        "voltage_angle",
        "load_power",
        "generation_power",
        "base_kv",
        "bus_type",
        "q_min",
        "q_max",
        "voltage_magnitude_scheduled",
        "zip_model",
    )

    def __init__(
        self,
        bus_id,
        voltage_magnitude=1.0,
        voltage_angle=0.0,
        load_power=0 + 0j,
        generation_power=0 + 0j,
        base_kv=None,
        bus_type="pq",
        q_min=-999.0,
        q_max=999.0,
    ):
        """
        Initialize a Bus object.

        Parameters:
        bus_id (int): Unique identifier for the bus.
        voltage_magnitude (float): Voltage magnitude in per-unit (default 1.0).
        voltage_angle (float): Voltage angle in radians (default 0.0).
        load_power (complex): Load power in per-unit (default 0+0j).
        generation_power (complex): Generation power in per-unit (default 0+0j).
        base_kv (float): Base voltage in kV for this bus (optional).
        bus_type (str): Type of bus: 'slack', 'pv', or 'pq' (default 'pq').
        """
        self.bus_id = bus_id
        self.voltage_magnitude = voltage_magnitude
        self.voltage_angle = voltage_angle
        self.load_power = load_power
        self.generation_power = generation_power
        self.base_kv = base_kv
        self.bus_type = bus_type  # 'slack', 'pv', 'pq'
        # Reactive power limits for PV buses
        self.q_min = q_min
        self.q_max = q_max
        # Scheduled voltage magnitude for PV buses (used for PQ->PV restoration)
        self.voltage_magnitude_scheduled = voltage_magnitude if bus_type == "pv" else None
        # ZIP load model (optional)
        self.zip_model = None

    @property
    def voltage(self):
        """Complex voltage in per-unit."""
        return self.voltage_magnitude * np.exp(1j * self.voltage_angle)

    @voltage.setter
    def voltage(self, value):
        """Set voltage from complex value."""
        self.voltage_magnitude = np.abs(value)
        self.voltage_angle = np.angle(value)

    def __repr__(self):
        return f"Bus({self.bus_id}): V={self.voltage_magnitude:.3f}∠{np.degrees(self.voltage_angle):.1f}°, type={self.bus_type}"
