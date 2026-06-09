import numpy as np

class Load:
    def __init__(self, load_id, bus, 
                 load_power=None,
                 impedance=None,
                 power_factor=None, constant_impedance=False):
        """
        Initialize a Load object.

        Parameters:
        load_id (int): Unique identifier for the load.
        bus (Bus): The bus to which the load is connected.
        load_power (complex): Load power in per-unit (default 0+0j).
        impedance (dict): Dictionary of impedances per unit for each sequence.
                          Format: {'1': Z1, '2': Z2, '0': Z0} where each is a complex number.
                          Default: open circuit (infinite impedance) for all sequences.
        power_factor (float): Power factor (optional, if provided, adjusts reactive power).
        constant_impedance (bool): If True, load is modeled as constant impedance (default False, constant power).
        """
        self.load_id = load_id
        self.bus = bus
        if load_power is None:
            self.load_power = complex(0.0, 0.0)
        else:
            self.load_power = load_power
        # Default impedance: open circuit
        if impedance is None:
            self.impedance = {
                '1': complex(1e9, 0.0),  # approximates open circuit
                '2': complex(1e9, 0.0),
                '0': complex(1e9, 0.0)
            }
        else:
            self.impedance = impedance
        self.power_factor = power_factor
        self.constant_impedance = constant_impedance

        # Automatically update the bus load_power when a load is connected
        self.bus.load_power += self.load_power

    def get_impedance(self, seq='1'):
        """Get impedance for a given sequence."""
        return self.impedance.get(seq, complex(1e9,0))

    def __repr__(self):
        return f"Load({self.load_id}) at Bus {self.bus.bus_id}: P={self.load_power.real:.3f}, Q={self.load_power.imag:.3f} pu"