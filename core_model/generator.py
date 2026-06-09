import numpy as np

class Generator:
    def __init__(self, generator_id, bus, 
                 internal_voltage=None, 
                 impedance=None,
                 max_power=None, min_power=None):
        """
        Initialize a Generator object.

        Parameters:
        generator_id (int): Unique identifier for the generator.
        bus (Bus): The bus to which the generator is connected.
        internal_voltage (dict): Dictionary of internal voltages per unit for each sequence.
                                 Format: {'1': V1, '2': V2, '0': V0} where each is a complex number.
                                 Default: positive sequence = 1.0∠0, negative and zero = 0.
        impedance (dict): Dictionary of impedances per unit for each sequence.
                          Format: {'1': Z1, '2': Z2, '0': Z0} where each is a complex number.
                          Default: all zero (ideal voltage source).
        max_power (complex): Maximum generation capability (optional).
        min_power (complex): Minimum generation capability (optional).
        """
        self.generator_id = generator_id
        self.bus = bus
        # Set default internal voltage: positive sequence = 1.0∠0, others zero
        if internal_voltage is None:
            self.internal_voltage = {
                '1': complex(1.0, 0.0),
                '2': complex(0.0, 0.0),
                '0': complex(0.0, 0.0)
            }
        else:
            self.internal_voltage = internal_voltage
        # Set default impedance: zero for all sequences
        if impedance is None:
            self.impedance = {
                '1': complex(0.0, 0.0),
                '2': complex(0.0, 0.0),
                '0': complex(0.0, 0.0)
            }
        else:
            self.impedance = impedance
        self.max_power = max_power
        self.min_power = min_power

        # Automatically update the bus generation_power when a generator is connected
        # Positive sequence internal voltage represents the scheduled voltage
        # For PV buses, the generation power is set from the scheduled P and V
        if self.internal_voltage.get('1', complex(0, 0)) != complex(0, 0):
            # Generator is active - update bus generation power if not already set
            pass  # Generation power is set explicitly in the system model

    def get_internal_voltage(self, seq='1'):
        """Get internal voltage for a given sequence."""
        return self.internal_voltage.get(seq, complex(0,0))

    def get_impedance(self, seq='1'):
        """Get impedance for a given sequence."""
        return self.impedance.get(seq, complex(0,0))

    def __repr__(self):
        return f"Generator({self.generator_id}) at Bus {self.bus.bus_id}: Vint={self.internal_voltage['1']:.3f} pu"