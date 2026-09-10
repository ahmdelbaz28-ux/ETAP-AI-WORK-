"""
Deep Arc Flash Analysis Tests - IEEE 1584-2018 & Ralph Lee

Covers:
- Input validation (voltage, current, duration, distance ranges)
- All electrode configurations (VCB, VCBB, HCB, VOA, HOA)
- Low-voltage (<1 kV) and medium-voltage (>=1 kV) ranges
- Box vs Open enclosures
- Incident energy and arc flash boundary calculations
- NFPA 70E PPE category determination
- Ralph Lee method for out-of-range voltages (>15 kV)
"""

from __future__ import annotations

import math

import pytest

from fault_analysis.arc_flash_engine import (
    ArcFlashEngine,
    ArcFlashResult,
    ElectrodeConfig,
    EnclosureType,
)


@pytest.fixture(name="engine")
def fixture_engine():
    return ArcFlashEngine()


class TestInputValidation:
    """Validate boundary checks per IEEE 1584-2018."""

    def test_voltage_too_low(self, engine):
        with pytest.raises(ValueError, match="below the IEEE 1584-2018 minimum"):
            engine.calculate(0.120, 20.0, 0.1, 457.0)

    def test_voltage_too_high(self, engine):
        with pytest.raises(ValueError, match="above the IEEE 1584-2018 maximum"):
            engine.calculate(34.5, 20.0, 0.1, 914.0)

    def test_current_too_low(self, engine):
        with pytest.raises(ValueError, match="below the IEEE 1584-2018 minimum"):
            engine.calculate(0.48, 0.5, 0.1, 457.0)

    def test_current_too_high(self, engine):
        with pytest.raises(ValueError, match="above the IEEE 1584-2018 maximum"):
            engine.calculate(0.48, 120.0, 0.1, 457.0)

    def test_duration_non_positive(self, engine):
        with pytest.raises(ValueError, match="Arc duration must be positive"):
            engine.calculate(0.48, 20.0, 0.0, 457.0)

    def test_working_distance_non_positive(self, engine):
        with pytest.raises(ValueError, match="Working distance must be positive"):
            engine.calculate(0.48, 20.0, 0.1, 0.0)

    def test_nan_voltage_raises(self, engine):
        with pytest.raises(ValueError, match="must be a finite number"):
            engine.calculate(float("nan"), 20.0, 0.1, 457.0)

    def test_inf_current_raises(self, engine):
        with pytest.raises(ValueError, match="must be a finite number"):
            engine.calculate(0.48, float("inf"), 0.1, 457.0)


class TestArcCurrentCalculations:
    """Test arc current equation across configurations and voltage tiers."""

    @pytest.mark.parametrize(
        "config",
        [
            ElectrodeConfig.VCB,
            ElectrodeConfig.VCBB,
            ElectrodeConfig.HCB,
            ElectrodeConfig.VOA,
            ElectrodeConfig.HOA,
        ],
    )
    def test_low_voltage_arc_current(self, config):
        iarc, iarc_red = ArcFlashEngine.calculate_arc_current(
            voltage_kv=0.48,
            bolted_fault_current_ka=25.0,
            electrode_config=config,
        )
        assert iarc > 0
        assert iarc_red > 0
        assert math.isclose(iarc_red, 0.85 * iarc, rel_tol=1e-4)

    @pytest.mark.parametrize(
        "config",
        [
            ElectrodeConfig.VCB,
            ElectrodeConfig.VCBB,
            ElectrodeConfig.HCB,
            ElectrodeConfig.VOA,
            ElectrodeConfig.HOA,
        ],
    )
    def test_medium_voltage_arc_current(self, config):
        iarc, iarc_red = ArcFlashEngine.calculate_arc_current(
            voltage_kv=13.8,
            bolted_fault_current_ka=15.0,
            electrode_config=config,
        )
        assert iarc > 0
        assert iarc_red > 0
        assert math.isclose(iarc_red, 0.85 * iarc, rel_tol=1e-4)

    def test_arc_current_finite_and_positive(self):
        iarc, iarc_red = ArcFlashEngine.calculate_arc_current(0.48, 10.0, ElectrodeConfig.VCB)
        assert iarc > 0 and math.isfinite(iarc)
        assert iarc_red > 0 and math.isfinite(iarc_red)


class TestIncidentEnergy:
    """Verify incident energy characteristics and trends."""

    def test_working_distance_reduces_incident_energy(self):
        e_close, _, _ = ArcFlashEngine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.1,
            working_distance_mm=305.0,
        )
        e_far, _, _ = ArcFlashEngine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.1,
            working_distance_mm=610.0,
        )
        assert e_close > e_far

    def test_duration_increases_incident_energy(self):
        e_short, _, _ = ArcFlashEngine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.05,
            working_distance_mm=457.0,
        )
        e_long, _, _ = ArcFlashEngine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.2,
            working_distance_mm=457.0,
        )
        assert e_long > e_short

    def test_box_vs_open_enclosure(self):
        e_box, _, _ = ArcFlashEngine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
            electrode_config=ElectrodeConfig.VCB,
            enclosure_type=EnclosureType.BOX,
        )
        e_open, _, _ = ArcFlashEngine.calculate_incident_energy(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
            electrode_config=ElectrodeConfig.VOA,
            enclosure_type=EnclosureType.OPEN,
        )
        assert e_box > 0
        assert e_open > 0


class TestArcFlashBoundary:
    """Verify arc flash boundary (distance to 1.2 cal/cm2)."""

    def test_boundary_positive(self):
        boundary = ArcFlashEngine.calculate_arc_flash_boundary(
            voltage_kv=0.48,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
        )
        assert boundary > 0

    def test_higher_energy_gives_larger_boundary(self):
        b_low = ArcFlashEngine.calculate_arc_flash_boundary(
            voltage_kv=0.48,
            bolted_fault_current_ka=10.0,
            arc_duration_sec=0.05,
            working_distance_mm=457.0,
        )
        b_high = ArcFlashEngine.calculate_arc_flash_boundary(
            voltage_kv=0.48,
            bolted_fault_current_ka=40.0,
            arc_duration_sec=0.2,
            working_distance_mm=457.0,
        )
        assert b_high > b_low


class TestPPEDetermination:
    """Check NFPA 70E category mapping."""

    @pytest.mark.parametrize(
        "energy,expected_level",
        [
            (0.5, "0"),
            (1.2, "0"),
            (2.5, "1"),
            (4.0, "1"),
            (6.0, "2"),
            (8.0, "2"),
            (15.0, "3"),
            (25.0, "3"),
            (30.0, "4"),
            (40.0, "4"),
            (40.1, "DANGER"),
            (80.0, "DANGER"),
        ],
    )
    def test_ppe_levels(self, energy, expected_level):
        level, desc = ArcFlashEngine.determine_ppe_level(energy)
        assert level == expected_level
        assert len(desc) > 0


class TestFullCalculationWorkflow:
    """Test full calculate() method and ArcFlashResult."""

    def test_calculate_returns_result_dataclass(self, engine):
        res = engine.calculate(
            voltage_kv=0.48,
            bolted_fault_current_ka=25.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
            electrode_config=ElectrodeConfig.VCB,
            enclosure_type=EnclosureType.BOX,
        )
        assert isinstance(res, ArcFlashResult)
        assert res.incident_energy_cal_cm2 > 0
        assert res.arc_flash_boundary_mm > 0
        assert res.arc_flash_boundary_in >= 0
        assert res.arc_current_ka > 0
        assert res.reduced_arc_current_ka > 0
        assert res.method == "IEEE 1584-2018"
        assert res.electrode_configuration == "VCB"
        assert res.enclosure_type == "box"
        assert res.ppe_level in ("0", "1", "2", "3", "4", "DANGER")
        assert res.voltage_kv == 0.48
        assert res.bolted_fault_current_ka == 25.0
        assert res.arc_duration_sec == 0.1
        assert res.working_distance_mm == 457.0


class TestRalphLeeMethod:
    """Test Ralph Lee method for voltages outside IEEE 1584 scope."""

    def test_high_voltage_ralph_lee(self):
        res = ArcFlashEngine.ralph_lee_method(
            voltage_kv=34.5,
            bolted_fault_current_ka=15.0,
            arc_duration_sec=0.1,
            working_distance_mm=914.0,
        )
        assert isinstance(res, ArcFlashResult)
        assert res.incident_energy_cal_cm2 > 0
        assert res.arc_flash_boundary_mm > 0
        assert "Ralph Lee" in res.method
        assert res.ppe_level in ("0", "1", "2", "3", "4", "DANGER")
        assert res.voltage_kv == 34.5


class TestArcFlashCalcWrapper:
    """Test convenience wrapper functions in fault_analysis.arc_flash_calc."""

    def test_calculate_arc_flash_standard(self):
        from fault_analysis.arc_flash_calc import calculate_arc_flash

        res = calculate_arc_flash(
            voltage_kv=0.48,
            bolted_fault_current_ka=25.0,
            arc_duration_sec=0.1,
            working_distance_mm=457.0,
            enclosure_type="box",
            electrode_config="VCB",
        )
        assert isinstance(res, dict)
        assert res["incident_energy_cal_per_cm2"] > 0
        assert res["arc_flash_boundary_mm"] > 0
        assert res["method"] == "IEEE 1584-2018"
        assert "ppe_level" in res

    def test_calculate_arc_flash_low_voltage(self):
        from fault_analysis.arc_flash_calc import calculate_arc_flash

        res = calculate_arc_flash(
            voltage_kv=0.12,
            bolted_fault_current_ka=10.0,
            arc_duration_sec=0.1,
            working_distance_mm=300.0,
        )
        assert isinstance(res, dict)
        assert res["incident_energy_cal_per_cm2"] > 0
        assert "Ralph Lee" in res["method"]

    def test_validate_arc_flash_input(self):
        from fault_analysis.arc_flash_calc import _validate_arc_flash_input

        # Valid input -> empty error list
        errs = _validate_arc_flash_input(0.48, 25.0, 0.1, 457.0, "box", "VCB")
        assert len(errs) == 0

        # Invalid voltage, duration, enclosure, electrode
        errs = _validate_arc_flash_input(-1.0, -5.0, -0.1, 0, "invalid_enc", "INVALID_ELEC")
        assert len(errs) >= 4
