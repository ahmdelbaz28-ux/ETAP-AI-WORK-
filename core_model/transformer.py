import numpy as np

class Transformer:
    def __init__(self, transformer_id, from_bus, to_bus,
                 z1=complex(0,0), z2=None, z0=None,
                 yshunt1=complex(0,0), yshunt2=None, yshunt0=None,
                 rating=None, tap_ratio=1.0, phase_shift=0.0):
        """
        Initialize a Transformer object with sequence impedances.

        Parameters:
        transformer_id (int): Unique identifier for the transformer.
        from_bus (Bus): The bus at the primary side.
        to_bus (Bus): The bus at the secondary side.
        z1 (complex): Positive sequence impedance in per-unit.
        z2 (complex): Negative sequence impedance in per-unit (default: same as z1).
        z0 (complex): Zero sequence impedance in per-unit (default: same as z1).
        yshunt1 (complex): Positive sequence shunt admittance in per-unit.
        yshunt2 (complex): Negative sequence shunt admittance (default: same as yshunt1).
        yshunt0 (complex): Zero sequence shunt admittance (default: same as yshunt1).
        rating (float): Power rating in per-unit (optional).
        tap_ratio (float): Tap ratio (secondary/primary) (default 1.0).
        phase_shift (float): Phase shift in radians (default 0.0).
        """
        self.transformer_id = transformer_id
        self.from_bus = from_bus
        self.to_bus = to_bus
        self.z1 = z1
        self.z2 = z2 if z2 is not None else z1
        self.z0 = z0 if z0 is not None else z1
        self.yshunt1 = yshunt1
        self.yshunt2 = yshunt2 if yshunt2 is not None else yshunt1
        self.yshunt0 = yshunt0 if yshunt0 is not None else yshunt1
        self.rating = rating
        self.tap_ratio = tap_ratio
        self.phase_shift = phase_shift

    def get_impedance(self, seq='1'):
        """
        Get impedance for a given sequence.
        Parameters:
        seq (str): '1', '2', or '0' for positive, negative, zero sequence.
        Returns:
        complex: Impedance in per-unit.
        """
        if seq == '1':
            return self.z1
        elif seq == '2':
            return self.z2
        elif seq == '0':
            return self.z0
        else:
            raise ValueError("Sequence must be '1', '2', or '0'")

    def get_shunt_admittance(self, seq='1'):
        """
        Get shunt admittance for a given sequence.
        Parameters:
        seq (str): '1', '2', or '0' for positive, negative, zero sequence.
        Returns:
        complex: Shunt admittance in per-unit.
        """
        if seq == '1':
            return self.yshunt1
        elif seq == '2':
            return self.yshunt2
        elif seq == '0':
            return self.yshunt0
        else:
            raise ValueError("Sequence must be '1', '2', or '0'")

    def __repr__(self):
        return f"Transformer({self.transformer_id}): {self.from_bus.bus_id} -> {self.to_bus.bus_id}, Z1={self.z1:.3f} pu, tap={self.tap_ratio:.3f}"
