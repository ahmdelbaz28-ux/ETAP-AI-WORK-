import numpy as np


class FaultAnalyzer:
    def __init__(self, ybus_pos, ybus_neg=None, ybus_zero=None, base_mva=100.0, base_kv=115.0):
        """
        Initialize the FaultAnalyzer with sequence admittance matrices.

        Parameters:
        ybus_pos (numpy.ndarray): Positive sequence Ybus matrix.
        ybus_neg (numpy.ndarray): Negative sequence Ybus matrix (optional, defaults to ybus_pos).
        ybus_zero (numpy.ndarray): Zero sequence Ybus matrix (optional, defaults to ybus_pos).
        base_mva (float): Base MVA for per-unit conversion. Default 100.0.
        base_kv (float): Base kV for current conversion. Default 115.0.
        """
        self.Ybus_pos = ybus_pos
        self.Ybus_neg = ybus_neg if ybus_neg is not None else ybus_pos
        self.Ybus_zero = ybus_zero if ybus_zero is not None else ybus_pos
        self.base_mva = base_mva
        self.base_kv = base_kv

        self.Zbus_pos = self._invert_ybus(self.Ybus_pos)
        self.Zbus_neg = self._invert_ybus(self.Ybus_neg)
        self.Zbus_zero = self._invert_ybus(self.Ybus_zero)

    def _invert_ybus(self, Ybus):
        """
        Invert Ybus to get Zbus, handling singularity by using pseudo-inverse.
        Assumes that the Ybus is for a grounded system (so invertible) or we use pseudo-inverse.
        """
        try:
            return np.linalg.inv(Ybus)
        except np.linalg.LinAlgError:
            return np.linalg.pinv(Ybus)

    def _pu_to_ka(self, current_pu):
        """Convert per-unit current to kA."""
        base_ka = self.base_mva / (np.sqrt(3) * self.base_kv)
        return abs(current_pu) * base_ka

    def three_phase_fault(self, bus_index):
        """
        Calculate three-phase fault current at a given bus using Thevenin method.

        The fault current is If = Vpre / Zth where Zth = Zbus[k,k] is the
        Thevenin impedance at the faulted bus.

        Parameters:
        bus_index (int): Index of the bus where fault occurs (0-based index in Ybus matrix).

        Returns:
        dict: Contains fault current (complex) in per-unit, and optionally voltage.
        """
        Vpre = complex(1.0, 0.0)
        Zth = self.Zbus_pos[bus_index, bus_index]
        if Zth == 0:
            If = complex('inf')
        else:
            If = Vpre / Zth
        return {
            'fault_current': If,
            'fault_current_magnitude': np.abs(If),
            'fault_current_ka': self._pu_to_ka(If),
            'fault_current_angle': np.angle(If, deg=True),
            'affected_bus_index': bus_index,
            'fault_type': 'three_phase'
        }

    def line_to_ground_fault(self, bus_index):
        """
        Calculate line-to-ground fault current at a given bus.

        Parameters:
        bus_index (int): Index of the bus where fault occurs.

        Returns:
        dict: Contains fault current (complex) in per-unit for the faulted phase.
        """
        Vpre = complex(1.0, 0.0)
        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        Z0 = self.Zbus_zero[bus_index, bus_index]
        denominator = Z1 + Z2 + Z0
        if denominator == 0:
            If = complex('inf')
        else:
            If = 3 * Vpre / denominator
        return {
            'fault_current': If,
            'fault_current_magnitude': np.abs(If),
            'fault_current_ka': self._pu_to_ka(If),
            'fault_current_angle': np.angle(If, deg=True),
            'affected_bus_index': bus_index,
            'fault_type': 'line_to_ground'
        }

    def line_to_line_fault(self, bus_index):
        """
        Calculate line-to-line fault current at a given bus.

        Parameters:
        bus_index (int): Index of the bus where fault occurs.

        Returns:
        dict: Contains fault current (complex) in per-unit for the faulted phases.
        """
        Vpre = complex(1.0, 0.0)
        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        denominator = Z1 + Z2
        if denominator == 0:
            If = complex('inf')
        else:
            If = Vpre * np.sqrt(3) / denominator
        return {
            'fault_current': If,
            'fault_current_magnitude': np.abs(If),
            'fault_current_ka': self._pu_to_ka(If),
            'fault_current_angle': np.angle(If, deg=True),
            'affected_bus_index': bus_index,
            'fault_type': 'line_to_line'
        }

    def double_line_to_ground_fault(self, bus_index):
        """
        Calculate double line-to-ground fault current at a given bus.

        Parameters:
        bus_index (int): Index of the bus where fault occurs.

        Returns:
        dict: Contains fault currents (complex) in per-unit.
        """
        Vpre = complex(1.0, 0.0)
        Z1 = self.Zbus_pos[bus_index, bus_index]
        Z2 = self.Zbus_neg[bus_index, bus_index]
        Z0 = self.Zbus_zero[bus_index, bus_index]
        Z20 = (Z2 * Z0) / (Z2 + Z0) if (Z2 + Z0) != 0 else 0
        If1 = Vpre / (Z1 + Z20)
        If0 = -If1 * (Z2 / (Z2 + Z0)) if (Z2 + Z0) != 0 else 0
        If2 = -If1 - If0
        a = complex(-0.5, np.sqrt(3)/2)
        a2 = complex(-0.5, -np.sqrt(3)/2)
        If1 + If2 + If0
        Ib = a2*If1 + a*If2 + If0
        Ic = a*If1 + a2*If2 + If0
        return {
            'fault_current_b': Ib,
            'fault_current_c': Ic,
            'fault_current_b_magnitude': np.abs(Ib),
            'fault_current_b_angle': np.angle(Ib, deg=True),
            'fault_current_b_ka': self._pu_to_ka(Ib),
            'fault_current_c_magnitude': np.abs(Ic),
            'fault_current_c_angle': np.angle(Ic, deg=True),
            'fault_current_c_ka': self._pu_to_ka(Ic),
            'affected_bus_index': bus_index,
            'fault_type': 'double_line_to_ground'
        }
