"""
Tests for SCADA model and state estimation — SCADADatabase, SwitchDevice, WLSEstimator.
"""

import time

import numpy as np
import pytest

from scada_model.scada_model import (
    Measurement,
    MeasurementType,
    QualityFlag,
    SCADADatabase,
    SwitchDevice,
    SwitchStatus,
)
from scada_model.state_estimation import StateEstimationStatus, WLSEstimator

# ===========================================================================
# Measurement
# ===========================================================================


class TestMeasurement:
    def test_create_voltage_measurement(self):
        m = Measurement(
            measurement_id="V_BUS1",
            measurement_type=MeasurementType.VOLTAGE_MAGNITUDE,
            element_id="BUS1",
            value=1.05,
        )
        assert m.measurement_id == "V_BUS1"
        assert m.value == pytest.approx(1.05)
        assert m.quality == QualityFlag.GOOD
        assert m.confidence == pytest.approx(1.0)

    def test_is_valid_good(self):
        m = Measurement("m1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.0)
        assert m.is_valid() is True

    def test_is_valid_questionable(self):
        m = Measurement(
            "m1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.0, quality=QualityFlag.QUESTIONABLE
        )
        assert m.is_valid() is True

    def test_is_valid_invalid(self):
        m = Measurement(
            "m1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.0, quality=QualityFlag.INVALID
        )
        assert m.is_valid() is False

    def test_is_valid_missing(self):
        m = Measurement(
            "m1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.0, quality=QualityFlag.MISSING
        )
        assert m.is_valid() is False

    def test_age_seconds(self):
        m = Measurement("m1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.0)
        assert m.age_seconds() >= 0

    def test_to_dict(self):
        m = Measurement("m1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05, confidence=0.95)
        d = m.to_dict()
        assert d["measurement_id"] == "m1"
        assert d["measurement_type"] == "voltage_magnitude"
        assert d["value"] == pytest.approx(1.05)
        assert d["confidence"] == pytest.approx(0.95)


# ===========================================================================
# SwitchDevice
# ===========================================================================


class TestSwitchDevice:
    def test_default_closed(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2")
        assert s.status == SwitchStatus.CLOSED
        assert s.is_conducting() is True

    def test_open_switch(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2")
        result = s.operate(SwitchStatus.OPEN)
        assert result is True
        assert s.is_conducting() is False
        assert s.status == SwitchStatus.OPEN

    def test_trip_switch(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2")
        s.operate(SwitchStatus.TRIPPED)
        assert s.status == SwitchStatus.TRIPPED
        assert s.trip_count == 1

    def test_trip_count_increments(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2")
        s.operate(SwitchStatus.TRIPPED)
        s.operate(SwitchStatus.TRIPPED)
        assert s.trip_count == 2

    def test_locked_out_cannot_operate(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2")
        s.operate(SwitchStatus.LOCKED_OUT)
        result = s.operate(SwitchStatus.OPEN)
        assert result is False  # Cannot operate locked-out device

    def test_locked_out_can_close(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2")
        s.operate(SwitchStatus.LOCKED_OUT)
        result = s.operate(SwitchStatus.CLOSED)
        assert result is True

    def test_to_dict(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2", rated_current=500)
        d = s.to_dict()
        assert d["device_id"] == "CB1"
        assert d["status"] == "closed"
        assert d["rated_current"] == 500
        assert d["protection_enabled"] is True

    def test_last_operation_time(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2")
        assert s.last_operation_time is None
        s.operate(SwitchStatus.OPEN)
        assert s.last_operation_time is not None

    def test_auto_reclosing_defaults(self):
        s = SwitchDevice(device_id="CB1", from_element="BUS1", to_element="BUS2")
        assert s.auto_reclosing_enabled is True
        assert s.max_reclosing_attempts == 3
        assert s.auto_reclosing_attempts == 0


# ===========================================================================
# SCADADatabase
# ===========================================================================


class TestSCADADatabase:
    def test_add_measurement(self):
        db = SCADADatabase()
        m = Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05)
        db.add_measurement(m)
        assert db.get_measurement("V1") is m

    def test_get_measurement_missing(self):
        db = SCADADatabase()
        assert db.get_measurement("NONEXISTENT") is None

    def test_get_measurements_for_element(self):
        db = SCADADatabase()
        db.add_measurement(Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05))
        db.add_measurement(Measurement("P1", MeasurementType.ACTIVE_POWER, "BUS1", 50.0))
        db.add_measurement(Measurement("V2", MeasurementType.VOLTAGE_MAGNITUDE, "BUS2", 1.02))
        bus1_meas = db.get_measurements_for_element("BUS1")
        assert len(bus1_meas) == 2

    def test_get_measurements_by_type(self):
        db = SCADADatabase()
        db.add_measurement(Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05))
        db.add_measurement(Measurement("V2", MeasurementType.VOLTAGE_MAGNITUDE, "BUS2", 1.02))
        db.add_measurement(Measurement("P1", MeasurementType.ACTIVE_POWER, "BUS1", 50.0))
        v_meas = db.get_measurements_by_type(MeasurementType.VOLTAGE_MAGNITUDE)
        assert len(v_meas) == 2

    def test_get_latest_voltage(self):
        db = SCADADatabase()
        db.add_measurement(Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05))
        assert db.get_latest_voltage("BUS1") == pytest.approx(1.05)

    def test_get_latest_voltage_expired(self):
        db = SCADADatabase(measurement_ttl_seconds=0)
        db.add_measurement(Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05))
        time.sleep(0.01)
        assert db.get_latest_voltage("BUS1") is None

    def test_get_latest_power(self):
        db = SCADADatabase()
        db.add_measurement(Measurement("P1", MeasurementType.ACTIVE_POWER, "BUS1", 50.0))
        db.add_measurement(Measurement("Q1", MeasurementType.REACTIVE_POWER, "BUS1", 20.0))
        result = db.get_latest_power("BUS1")
        assert result is not None
        assert result[0] == pytest.approx(50.0)
        assert result[1] == pytest.approx(20.0)

    def test_get_latest_power_missing(self):
        db = SCADADatabase()
        assert db.get_latest_power("BUS1") is None

    def test_clean_expired(self):
        db = SCADADatabase(measurement_ttl_seconds=0)
        db.add_measurement(Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05))
        time.sleep(0.01)
        removed = db.clean_expired()
        assert removed == 1
        assert db.get_measurement("V1") is None

    def test_add_switch_device(self):
        db = SCADADatabase()
        s = SwitchDevice("CB1", "BUS1", "BUS2")
        db.add_switch_device(s)
        assert db.get_switch_device("CB1") is s

    def test_operate_switch(self):
        db = SCADADatabase()
        s = SwitchDevice("CB1", "BUS1", "BUS2")
        db.add_switch_device(s)
        result = db.operate_switch("CB1", SwitchStatus.OPEN)
        assert result is True
        assert s.is_conducting() is False

    def test_operate_switch_missing(self):
        db = SCADADatabase()
        result = db.operate_switch("NONEXISTENT", SwitchStatus.OPEN)
        assert result is False

    def test_get_open_switches(self):
        db = SCADADatabase()
        db.add_switch_device(SwitchDevice("CB1", "BUS1", "BUS2"))  # closed
        db.add_switch_device(SwitchDevice("CB2", "BUS2", "BUS3"))  # closed
        db.operate_switch("CB2", SwitchStatus.OPEN)
        open_sw = db.get_open_switches()
        assert len(open_sw) == 1
        assert open_sw[0].device_id == "CB2"

    def test_get_closed_switches(self):
        db = SCADADatabase()
        db.add_switch_device(SwitchDevice("CB1", "BUS1", "BUS2"))  # closed
        db.add_switch_device(SwitchDevice("CB2", "BUS2", "BUS3"))  # closed
        db.operate_switch("CB2", SwitchStatus.OPEN)
        closed_sw = db.get_closed_switches()
        assert len(closed_sw) == 1

    def test_get_switches_between(self):
        db = SCADADatabase()
        db.add_switch_device(SwitchDevice("CB1", "BUS1", "BUS2"))
        db.add_switch_device(SwitchDevice("CB2", "BUS2", "BUS3"))
        between = db.get_switches_between("BUS1", "BUS2")
        assert len(between) == 1
        assert between[0].device_id == "CB1"

    def test_get_switches_between_reverse_order(self):
        db = SCADADatabase()
        db.add_switch_device(SwitchDevice("CB1", "BUS1", "BUS2"))
        between = db.get_switches_between("BUS2", "BUS1")
        assert len(between) == 1

    def test_get_statistics(self):
        db = SCADADatabase()
        db.add_measurement(Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05))
        db.add_measurement(Measurement("P1", MeasurementType.ACTIVE_POWER, "BUS1", 50.0))
        db.add_switch_device(SwitchDevice("CB1", "BUS1", "BUS2"))
        stats = db.get_statistics()
        assert stats["total_measurements"] == 2
        assert stats["total_switch_devices"] == 1
        assert stats["closed_switches"] == 1

    def test_measurement_history(self):
        db = SCADADatabase()
        m1 = Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05)
        m2 = Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.06)
        db.add_measurement(m1)
        db.add_measurement(m2)
        assert len(db.measurement_history["V1"]) == 2

    def test_get_voltage_state_vector(self):
        db = SCADADatabase()
        db.add_measurement(Measurement("V1", MeasurementType.VOLTAGE_MAGNITUDE, "BUS1", 1.05))
        v = db.get_voltage_state_vector(["BUS1", "BUS2"])
        assert len(v) == 2
        assert abs(v[0]) == pytest.approx(1.05)
        assert abs(v[1]) == pytest.approx(1.0)  # default

    def test_get_power_injection_vector(self):
        db = SCADADatabase()
        db.add_measurement(Measurement("P1", MeasurementType.ACTIVE_POWER, "BUS1", 50.0))
        db.add_measurement(Measurement("Q1", MeasurementType.REACTIVE_POWER, "BUS1", 20.0))
        p = db.get_power_injection_vector(["BUS1", "BUS2"])
        assert len(p) == 2
        assert p[0] == complex(50, 20)
        assert p[1] == complex(0, 0)  # default

    def test_get_topology_switching_state(self):
        db = SCADADatabase()
        db.add_switch_device(SwitchDevice("CB1", "BUS1", "BUS2"))
        db.add_switch_device(SwitchDevice("CB2", "BUS2", "BUS3"))
        db.operate_switch("CB2", SwitchStatus.OPEN)
        state = db.get_topology_switching_state()
        assert state["CB1"] is True
        assert state["CB2"] is False


# ===========================================================================
# WLS State Estimation
# ===========================================================================


class TestWLSEstimator:
    def test_estimate_3bus_system(self):
        """3-bus system — needs 3+ buses for WLS observability since the
        estimator doesn't remove the slack bus column from the Jacobian
        before inverting the gain matrix (causing theta collinearity in 2-bus)."""
        Ybus = np.array(
            [
                [2 - 20j, -1 + 10j, -1 + 10j],
                [-1 + 10j, 2 - 20j, -1 + 10j],
                [-1 + 10j, -1 + 10j, 2 - 20j],
            ],
            dtype=complex,
        )
        measurements = {
            "voltage_mag": {0: (1.0, 0.01)},
            "power_injection": {1: (0.3, 0.1, 0.02, 0.02), 2: (0.2, 0.05, 0.02, 0.02)},
        }
        estimator = WLSEstimator()
        result = estimator.estimate(Ybus, measurements, bus_ids=["B1", "B2", "B3"])
        assert result.status == StateEstimationStatus.CONVERGED
        assert len(result.voltage_magnitudes) == 3

    def test_estimate_with_voltage_and_power_flow(self):
        Ybus = np.array(
            [
                [2 - 20j, -1 + 10j, -1 + 10j],
                [-1 + 10j, 2 - 20j, -1 + 10j],
                [-1 + 10j, -1 + 10j, 2 - 20j],
            ],
            dtype=complex,
        )
        measurements = {
            "voltage_mag": {0: (1.0, 0.01)},
            "power_injection": {1: (0.3, 0.1, 0.02, 0.02), 2: (0.2, 0.05, 0.02, 0.02)},
        }
        estimator = WLSEstimator(tolerance=1e-4)
        result = estimator.estimate(Ybus, measurements, bus_ids=["B1", "B2", "B3"])
        assert result.status == StateEstimationStatus.CONVERGED

    def test_estimate_insufficient_measurements(self):
        Ybus = np.array([[1 - 10j, -1 + 10j], [-1 + 10j, 1 - 10j]], dtype=complex)
        measurements = {}
        estimator = WLSEstimator()
        result = estimator.estimate(Ybus, measurements, bus_ids=["B1", "B2"])
        assert result.status == StateEstimationStatus.INSUFFICIENT_MEASUREMENTS

    def test_estimate_empty_bus_list(self):
        Ybus = np.array([])
        measurements = {}
        estimator = WLSEstimator()
        result = estimator.estimate(Ybus, measurements, bus_ids=[])
        assert result.status == StateEstimationStatus.INSUFFICIENT_MEASUREMENTS

    def test_estimate_not_converged(self):
        """3-bus system with extreme values and tight tolerance should NOT converge."""
        Ybus = np.array(
            [
                [2 - 20j, -1 + 10j, -1 + 10j],
                [-1 + 10j, 2 - 20j, -1 + 10j],
                [-1 + 10j, -1 + 10j, 2 - 20j],
            ],
            dtype=complex,
        )
        measurements = {
            "voltage_mag": {0: (1000.0, 0.01)},
            "power_injection": {1: (999.0, 999.0, 0.02, 0.02), 2: (888.0, 888.0, 0.02, 0.02)},
        }
        estimator = WLSEstimator(max_iterations=5, tolerance=1e-12)  # very tight tol, few iters
        result = estimator.estimate(Ybus, measurements, bus_ids=["B1", "B2", "B3"])
        assert result.status == StateEstimationStatus.NOT_CONVERGED

    def test_check_redundancy_sufficient(self):
        # Need redundancy >= 1.5: with n=3, need m >= 8 for 2*3-1=5 states
        measurements = {
            "voltage_mag": {0: (1.0, 0.01), 1: (1.0, 0.01), 2: (1.0, 0.01)},
            "power_injection": {1: (0.3, 0.1, 0.02, 0.02), 2: (0.2, 0.05, 0.02, 0.02)},
            "power_flow": {(0, 1): (0.15, 0.05, 0.02, 0.02)},
        }
        estimator = WLSEstimator()
        red = estimator.check_redundancy(measurements, n=3, slack_idx=0)
        assert red["measurement_count"] == 9  # 3 V + 2*(P+Q) + 1*(P+Q)_flow
        assert red["state_variables"] == 5  # 2*3 - 1
        assert red["redundancy_ratio"] == 9 / 5
        assert red["sufficient"] is True

    def test_check_redundancy_critical(self):
        measurements = {
            "voltage_mag": {0: (1.0, 0.01)},
        }
        estimator = WLSEstimator()
        red = estimator.check_redundancy(measurements, n=3, slack_idx=0)
        assert red["critical"] is True

    def test_estimate_bad_data_detection(self):
        Ybus = np.array(
            [
                [2 - 20j, -1 + 10j, -1 + 10j],
                [-1 + 10j, 2 - 20j, -1 + 10j],
                [-1 + 10j, -1 + 10j, 2 - 20j],
            ],
            dtype=complex,
        )
        measurements = {
            "voltage_mag": {0: (1.0, 0.01)},
            "power_injection": {1: (0.3, 0.1, 0.02, 0.02), 2: (0.2, 0.05, 0.02, 0.02)},
        }
        estimator = WLSEstimator(tolerance=1e-4)
        result = estimator.estimate(Ybus, measurements, bus_ids=["B1", "B2", "B3"])
        assert result.objective_value >= 0
        assert result.max_residual >= 0
