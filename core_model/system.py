import math

import numpy as np


class System:
    __slots__ = (
        "base_mva",
        "buses",
        "lines",
        "transformers",
        "generators",
        "loads",
        "Ybus_seq",
        "_include_gen_impedance_pos",
    )

    def __init__(self, base_mva=100.0):
        """
        Initialize a Power System object.

        Parameters:
        base_mva (float): Base MVA for per-unit system (default 100.0).
        """
        self.base_mva = base_mva
        self.buses = {}  # bus_id -> Bus
        self.lines = []  # list of Line
        self.transformers = []  # list of Transformer
        self.generators = []  # list of Generator  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.loads = []  # list of Load
        self.Ybus_seq = {}  # sequence -> Ybus matrix
        self._include_gen_impedance_pos = False  # True for fault analysis, False for load flow

    def add_bus(self, bus):
        """Add a bus to the system."""
        self.buses[bus.bus_id] = bus

    def add_line(self, line):
        """Add a line to the system."""
        self.lines.append(line)

    def add_transformer(self, transformer):
        """Add a transformer to the system."""
        self.transformers.append(transformer)

    def add_generator(self, generator):
        """Add a generator to the system."""
        self.generators.append(generator)

    def add_load(self, load):
        """Add a load to the system and accumulate its power at the connected bus."""
        self.loads.append(load)
        # Accumulate load power at the connected bus (was previously in Load.__init__)
        load.bus.load_power += load.load_power  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)

    def build_ybus(self, seq="1"):  # NOSONAR — S3776: cognitive complexity; refactoring sprint
        """
        Build the Ybus admittance matrix for the system for a given sequence.

        Parameters:
        seq (str): '1', '2', or '0' for positive, negative, zero sequence.

        Returns:
        numpy.ndarray: Complex admittance matrix (Ybus) of size (n x n).
        """
        # Create a mapping from bus_id to index
        bus_ids = sorted(self.buses.keys())
        n = len(bus_ids)
        bus_index = {bus_id: i for i, bus_id in enumerate(bus_ids)}
  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        # Initialize Ybus as zero matrix
        Ybus = np.zeros((n, n), dtype=complex)  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability

        # Add contributions from lines
        for line in self.lines:
            i = bus_index[line.from_bus.bus_id]
            j = bus_index[line.to_bus.bus_id]
            z = line.get_impedance(seq)
            y = 1.0 / z if abs(z) > 1e-12 else 0
            # Shunt susceptance/2 at each end
            y_shunt = line.get_shunt_admittance(seq) / 2.0

            Ybus[i, i] += y + y_shunt
            Ybus[j, j] += y + y_shunt
            # Off-diagonal elements: Ybus[i,j] = Ybus[j,i] = -y (symmetric for real y)
            # For complex y (e.g., from complex impedance), both off-diagonals are -y
            Ybus[i, j] -= y
            Ybus[j, i] -= y

        # Add contributions from transformers
        for xf in self.transformers:
            i = bus_index[xf.from_bus.bus_id]
            j = bus_index[xf.to_bus.bus_id]
            z = xf.get_impedance(seq)
            y = 1.0 / z if abs(z) > 1e-12 else 0
            # Transformer shunt admittance is split equally between the two
            # buses, consistent with the π-model (half on each side).
            y_shunt_half = xf.get_shunt_admittance(seq) / 2.0

            # Handle tap ratio and phase shift for transformers
            tap = xf.tap_ratio
            phase_shift = xf.phase_shift

            if not math.isclose(tap, 1.0) or not math.isclose(phase_shift, 0.0):
                # Off-nominal tap ratio transformer model
                # Complex tap ratio: a = tap * exp(j * phase_shift)
                a = tap * np.exp(1j * phase_shift)

                # Ybus entries for tap-changing transformer (standard formulation)
                # Shunt on tapped side (bus i) must be referred through |a|²
                Ybus[i, i] += (y / (abs(a) ** 2)) + y_shunt_half / (abs(a) ** 2)
                Ybus[j, j] += y + y_shunt_half
                Ybus[i, j] -= y / np.conj(a)
                Ybus[j, i] -= y / a
            else:
                # Standard transformer (tap = 1.0, no phase shift)
                Ybus[i, i] += y + y_shunt_half
                Ybus[j, j] += y + y_shunt_half
                Ybus[i, j] -= y
                Ybus[j, i] -= y

        # Add generator impedance contributions to Ybus diagonal
        # For positive sequence with include_gen_impedance=True (fault analysis),
        # generator impedance IS included.
        # For positive sequence with include_gen_impedance=False (load flow),
        # the generator is modeled as a voltage source, so impedance is NOT added.
        if seq != "1" or self._include_gen_impedance_pos:
            for gen in self.generators:
                i = bus_index[gen.bus.bus_id]
                zg = gen.get_impedance(seq)
                if abs(zg) > 1e-12:
                    yg = 1.0 / zg
                    Ybus[i, i] += yg

        # Add load contributions to Ybus for constant-impedance loads
        # For constant power loads (default), no Ybus modification is needed
        # as they are handled via power mismatch in the load flow solver.
        # For constant-impedance loads, add their admittance to Ybus diagonal.
        for load in self.loads:
            i = bus_index[load.bus.bus_id]
            if load.constant_impedance:
                z_load = load.get_impedance(seq)
                if abs(z_load) > 1e-12 and abs(z_load) < 1e8:
                    y_load = 1.0 / z_load
                    Ybus[i, i] += y_load

        self.Ybus_seq[seq] = Ybus
        return Ybus

    def get_ybus(self, seq="1"):
        """
        Get the Ybus matrix for a given sequence, building it if necessary.

        Parameters:
        seq (str): '1', '2', or '0' for positive, negative, zero sequence.

        Returns:
        numpy.ndarray: Complex admittance matrix (Ybus).
        """
        if seq not in self.Ybus_seq:
            return self.build_ybus(seq)
        return self.Ybus_seq[seq]

    def build_sequence_networks(self, for_fault=False):
        """
        Build Ybus for all three sequences (positive, negative, zero).

        Parameters:
        for_fault (bool): If True, include generator impedances in positive sequence
                         (needed for fault analysis). If False, exclude them
                         (needed for load flow).
        """
        self._include_gen_impedance_pos = for_fault
        # Clear cached Ybus to force rebuild with new settings
        self.Ybus_seq.clear()
        for seq in ["1", "2", "0"]:
            self.build_ybus(seq)

    def get_bus_voltages(self):
        """Return a list of complex voltages for each bus in order of bus_id."""
        bus_ids = sorted(self.buses.keys())
        return [self.buses[bid].voltage for bid in bus_ids]

    def set_bus_voltages(self, voltages):
        """Set bus voltages from a list of complex values in order of bus_id."""
        bus_ids = sorted(self.buses.keys())
        for bid, v in zip(bus_ids, voltages):
            self.buses[bid].voltage = v

    def __repr__(self):
        return f"System({len(self.buses)} buses, {len(self.lines)} lines, {len(self.transformers)} transformers)"
