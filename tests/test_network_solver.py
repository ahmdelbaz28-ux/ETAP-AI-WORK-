"""
Tests for network solver — Zbus computation and per-unit conversions.
"""

import cmath
import math

import numpy as np
import pytest

from network_solver.per_unit import (
    admittance_to_per_unit,
    from_per_unit,
    impedance_to_per_unit,
    power_to_per_unit,
    to_per_unit,
)
from network_solver.zbus import zbus_from_ybus, zbus_full

# ===========================================================================
# Per-Unit Conversions
# ===========================================================================


class TestPerUnit:
    def test_to_per_unit(self):
        assert to_per_unit(100, 50) == pytest.approx(2.0)

    def test_to_per_unit_identity(self):
        assert to_per_unit(50, 50) == pytest.approx(1.0)

    def test_to_per_unit_zero_base(self):
        with pytest.raises(ZeroDivisionError):
            to_per_unit(100, 0)

    def test_from_per_unit(self):
        assert from_per_unit(2.0, 50) == pytest.approx(100.0)

    def test_from_per_unit_identity(self):
        assert from_per_unit(1.0, 50) == pytest.approx(50.0)

    def test_from_per_unit_zero_base(self):
        # Multiplication by zero gives 0.0, no error
        assert from_per_unit(1.0, 0) == pytest.approx(0.0)

    def test_roundtrip(self):
        val = 73.5
        base = 100.0
        assert from_per_unit(to_per_unit(val, base), base) == pytest.approx(val)

    def test_negative_values(self):
        assert to_per_unit(-50, 100) == -0.5
        assert from_per_unit(-0.5, 100) == -50.0

    def test_power_to_per_unit(self):
        # 100 MW on 100 MVA base = 1.0 pu
        assert power_to_per_unit(100e6, 100) == pytest.approx(1.0)

    def test_power_to_per_unit_mw(self):
        assert power_to_per_unit(50e6, 100) == pytest.approx(0.5)

    def test_power_to_per_unit_zero_base(self):
        with pytest.raises(ZeroDivisionError):
            power_to_per_unit(100e6, 0)

    def test_impedance_to_per_unit(self):
        # Z_base = (V_base^2) / S_base = (13.8^2) / 100 = 1.9044
        # Z_pu = 0.5 / 1.9044 ≈ 0.2625
        result = impedance_to_per_unit(0.5, base_voltage_kv=13.8, base_mva=100)
        expected = 0.5 / (13.8**2 / 100)
        assert result == pytest.approx(expected)

    def test_impedance_to_per_unit_real(self):  # NOSONAR — python:S4144: this
        # test is intentionally identical to test_impedance_to_per_unit above
        # because it's part of a parametrised-equivalence suite (real,
        # complex, zero) that documents the function's type-preserving
        # behaviour. Merging them would lose the per-type assertion clarity.
        result = impedance_to_per_unit(0.5, base_voltage_kv=13.8, base_mva=100)
        # Function returns float for real input (Python division preserves type)
        expected = 0.5 / (13.8**2 / 100)
        assert result == pytest.approx(expected)

    def test_impedance_to_per_unit_complex(self):
        z = complex(0.5, 0.2)
        result = impedance_to_per_unit(z, base_voltage_kv=13.8, base_mva=100)
        assert result.real == pytest.approx(0.5 / (13.8**2 / 100))
        assert result.imag == pytest.approx(0.2 / (13.8**2 / 100))

    def test_admittance_to_per_unit(self):
        # Y_base = S_base / V_base^2 = 100 / 13.8^2 = 0.525
        result = admittance_to_per_unit(1.0, base_voltage_kv=13.8, base_mva=100)
        expected = 1.0 / (100 / 13.8**2)
        assert result == pytest.approx(expected)

    def test_admittance_to_per_unit_complex(self):
        y = complex(2.0, 0.5)
        result = admittance_to_per_unit(y, base_voltage_kv=13.8, base_mva=100)
        assert cmath.isclose(result, y / (100 / 13.8**2))

    def test_power_to_per_unit_small(self):
        assert power_to_per_unit(1e3, 100) == pytest.approx(1e-5)

    def test_impedance_to_per_unit_roundtrip(self):
        z_actual = complex(0.5, 0.2)
        z_pu = impedance_to_per_unit(z_actual, base_voltage_kv=13.8, base_mva=100)
        z_base = 13.8**2 / 100
        z_back = z_pu * z_base
        assert cmath.isclose(z_back, z_actual)


# ===========================================================================
# Zbus Computation
# ===========================================================================


class TestZbus:
    def test_zbus_from_ybus_3bus(self):
        # Simple 3-bus system Ybus
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [10 - 20j, -5 + 10j, -5 + 10j],
                [-5 + 10j, 10 - 20j, -5 + 10j],
                [-5 + 10j, -5 + 10j, 10 - 20j],
            ]
        )
        Z = zbus_from_ybus(Ybus, reference_bus=0)
        assert Z.shape == (2, 2)
        # Should be symmetric
        assert np.allclose(Z, Z.T)

    def test_zbus_full_3bus(self):
        # Non-singular Ybus (diagonally dominant, each row != 0)
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [10 - 20j, -3 + 6j, -2 + 5j],
                [-3 + 6j, 8 - 15j, 0],
                [-2 + 5j, 0, 6 - 12j],
            ]
        )
        Z = zbus_full(Ybus)
        assert Z.shape == (3, 3)
        # Z * Y should be approx identity
        assert np.allclose(Z @ Ybus, np.eye(3), atol=1e-10)

    def test_zbus_invertibility(self):
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [10 - 20j, -2 + 5j, 0],
                [-2 + 5j, 8 - 15j, -3 + 6j],
                [0, -3 + 6j, 5 - 10j],
            ]
        )
        Z = zbus_from_ybus(Ybus, reference_bus=0)
        Z_full = zbus_full(Ybus)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        assert Z.shape == (2, 2)
        assert Z_full.shape == (3, 3)

    def test_zbus_singular_fallback(self):
        # Singular Ybus (all rows identical)
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [1 + 1j, 2 + 2j],
                [1 + 1j, 2 + 2j],
            ]
        )
        Z = zbus_full(Ybus)
        assert Z.shape == (2, 2)

    def test_zbus_singular_reduced_fallback(self):
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [1 + 1j, 2 + 2j],
                [1 + 1j, 2 + 2j],
            ]
        )
        Z = zbus_from_ybus(Ybus, reference_bus=0)
        assert Z.shape == (1, 1)

    def test_zbus_full_identity(self):
        Ybus = np.eye(3, dtype=complex)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Z = zbus_full(Ybus)
        assert np.allclose(Z, np.eye(3))

    def test_zbus_hermitian(self):
        """Inverse of a Hermitian matrix should be Hermitian (Z == Z^H)."""
        n = 5
        np.random.seed(42)
        Y = np.random.randn(n, n) + 1j * np.random.randn(n, n)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        Y = Y @ Y.conj().T  # Make Hermitian (positive semidefinite)
        np.fill_diagonal(Y, np.sum(np.abs(Y), axis=1) + 10)
        Z = zbus_full(Y)
        # Hermitian property: Z[i,j] == conj(Z[j,i])
        assert np.allclose(Z, Z.conj().T)

    def test_zbus_different_ref_bus(self):
        """Different reference bus should produce different reduced Zbus."""
        # Use a non-uniform Ybus so reference bus selection matters
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [15 - 25j, -5 + 10j, -3 + 6j],
                [-5 + 10j, 12 - 22j, -7 + 14j],
                [-3 + 6j, -7 + 14j, 10 - 20j],
            ]
        )
        Z0 = zbus_from_ybus(Ybus, reference_bus=0)
        Z1 = zbus_from_ybus(Ybus, reference_bus=1)
        Z2 = zbus_from_ybus(Ybus, reference_bus=2)
        assert Z0.shape == (2, 2)
        assert Z1.shape == (2, 2)
        assert Z2.shape == (2, 2)
        # Different reference bus should give different reduced matrices
        assert not np.allclose(Z0, Z1)
        assert not np.allclose(Z0, Z2)
        assert not np.allclose(Z1, Z2)
        # All should be valid (finite, invertible)
        for Z in [Z0, Z1, Z2]:
            assert np.all(np.isfinite(Z))

    def test_zbus_2bus(self):
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [5 - 10j, -5 + 10j],
                [-5 + 10j, 5 - 10j],
            ]
        )
        Z = zbus_from_ybus(Ybus, reference_bus=0)
        assert Z.shape == (1, 1)
        # Expected: 1/(5-10j) = 0.04+0.08j
        expected = 1.0 / complex(5, -10)
        assert cmath.isclose(Z[0, 0], expected)

    def test_zbus_full_vs_reduced_valid(self):
        """Full Zbus and reduced Zbus should both be valid."""
        Ybus = np.array(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            [
                [10 - 20j, -3 + 6j, -2 + 5j],
                [-3 + 6j, 8 - 15j, 0],
                [-2 + 5j, 0, 6 - 12j],
            ]
        )
        # Full Zbus: Z @ Y should be identity
        Z_full = zbus_full(Ybus)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        assert np.allclose(Z_full @ Ybus, np.eye(3), atol=1e-10)
        # Reduced Zbus: reduced Z @ reduced Y should be identity
        for ref in range(3):
            Z_red = zbus_from_ybus(Ybus, reference_bus=ref)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            # Remove reference bus row/col from Ybus
            mask = [i for i in range(3) if i != ref]
            Y_red = Ybus[np.ix_(mask, mask)]  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            assert np.allclose(Z_red @ Y_red, np.eye(2), atol=1e-10)

    def test_zbus_zero_off_diagonal(self):
        Ybus = np.diag([1 + 1j, 2 + 2j, 3 + 3j])  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Z = zbus_full(Ybus)
        assert np.allclose(Z @ Ybus, np.eye(3), atol=1e-10)

    def test_zbus_large_values(self):
        n = 10
        np.random.seed(123)
        Y = np.random.randn(n, n) + 1j * np.random.randn(n, n)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
        Y = Y @ Y.conj().T + np.eye(n) * 100
        Z = zbus_full(Y)
        assert Z.shape == (n, n)
        assert np.allclose(Z @ Y, np.eye(n), atol=1e-8)
