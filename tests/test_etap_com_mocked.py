"""
tests/test_etap_com_mocked.py — WP0 safety net: mocked-COM regression baseline.

Patches ``win32com.client.Dispatch`` with a fake ETAP object tree so the full
COM code path in ``etap_integration.etap_com`` is exercised on any platform
with zero ETAP installation. Covers:

1. ``run_study`` routing for every study type declared in ``ETAPStudyType``
   that has a handler wired in ``ETAPProject.run_study``.
2. Parameter schemas (``STUDY_TYPE_PARAMETER_SCHEMAS``): unknown keys,
   out-of-range values, wrong types, and valid pass-through.
3. Project path guards: extension, length, UNC rejection, traversal escape,
   and allowed-directory enforcement.

These tests must stay green BEFORE any behavior change (regression baseline).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import etap_integration.etap_com as etap_com
from etap_integration.etap_com import (
    ETAPAutomation,
    ETAPStudyType,
    STUDY_TYPE_PARAMETER_SCHEMAS,
)


# ---------------------------------------------------------------------------
# Fake ETAP COM object tree
# ---------------------------------------------------------------------------


class _Rec:
    """Mixin recording Calculate() invocations."""

    def __init__(self) -> None:
        self.calculate_calls = 0

    def Calculate(self) -> None:  # noqa: N802 - mirrors COM naming
        self.calculate_calls += 1


class FakeBus:
    def __init__(self, bus_id: str) -> None:
        self.ID = bus_id
        self.Name = f"Bus {bus_id}"
        self.KV = 20.0
        self.BusType = "PQ"
        self.VoltageMag = 1.02
        self.VoltageAng = -1.5
        self.PMW = 42.0
        self.QMVAR = 11.0
        self.I3PhaseKA = 18.4
        self.ILGKA = 16.1
        self.ILLKA = 15.7
        self.IDLGKA = 17.0
        self.VTHD = 2.9
        self.ITHD = 4.1
        self.DominantHarmonic = 5


class FakeBranch:
    def __init__(self, branch_id: str) -> None:
        self.ID = branch_id
        self.PFrom = 48.5
        self.QFrom = 9.5
        self.PTo = 47.9
        self.QTo = 9.1
        self.Current = 0.49


class FakeEquipment:
    def __init__(self, equip_id: str) -> None:
        self.ID = equip_id
        self.IncidentEnergy = 4.2
        self.ArcFlashBoundary = 0.9
        self.PPELevel = "2"
        self.ArcDuration = 0.41


class FakeGenerator:
    def __init__(self, gen_id: str) -> None:
        self.ID = gen_id
        self.PMW = 55.0
        self.QMVAR = 12.0
        self.Cost = 140.0
        self.RotorAngle = 33.0
        self.RotorAngleTrajectory = None
        self.TimeTrajectory = None
        self.CriticalClearingTime = 0.37


class FakeMotor:
    def __init__(self, motor_id: str) -> None:
        self.ID = motor_id
        self.StartingCurrentMult = 5.8
        self.AccelTime = 2.7
        self.MinVoltagePU = 0.79
        self.SpeedPercent = 100.0


class FakeCable:
    def __init__(self, cable_id: str) -> None:
        self.ID = cable_id
        self.Ampacity = 315.0
        self.DeratedAmpacity = 288.0
        self.KV = 11.0


class FakeCoordEntry:
    def __init__(self) -> None:
        self.FaultCurrent = 4.5
        self.PrimaryTime = 0.21
        self.BackupTime = 0.66
        self.CTI = 0.45
        self.Coordinated = True


class FakeRelay:
    def __init__(self, relay_id: str) -> None:
        self.ID = relay_id
        self.CurveType = "very_inverse"
        self.TMS = 0.3
        self.CoordinationResults = [FakeCoordEntry()]


class FakeLoadFlowModule(_Rec):
    Iterations = 4


class FakeShortCircuitModule(_Rec):
    def __init__(self) -> None:
        super().__init__()
        self.FaultType = "ThreePhase"


class FakeArcFlashModule(_Rec):
    def __init__(self) -> None:
        super().__init__()
        self.WorkingDistance = 0.0


class FakeOpfModule(_Rec):
    TotalLosses = 2.1
    Objective = "Minimize Cost"


class FakeMotorStartingModule(_Rec):
    StartingMethod = "Across-the-Line"


class FakeTransientStabilityModule(_Rec):
    pass


class FakeGroundGridModule(_Rec):
    SoilResistivity = 120.0
    SurfaceThickness = 0.15
    GridResistance = 0.62
    MeshVoltage = 310.0
    StepVoltage = 250.0
    GPR = 1150.0
    RodCount = 12
    TouchVoltageLimit = 500.0
    StepVoltageLimit = 750.0
    TouchCompliant = True
    StepCompliant = True


class FakeReliabilityModule(_Rec):
    CustomersServed = 2000
    SustainedOutages = 4
    MomentaryOutages = 3
    TotalOutageHours = 180.0


class FakeProtectionModule(_Rec):
    pass


class FakeProject:
    def __init__(self) -> None:
        self.Name = "WP0FAKE"
        self.LoadFlow = FakeLoadFlowModule()
        self.ShortCircuit = FakeShortCircuitModule()
        self.ArcFlash = FakeArcFlashModule()
        self.Harmonic = _Rec()
        self.OptimalPowerFlow = FakeOpfModule()
        self.MotorStarting = FakeMotorStartingModule()
        self.TransientStability = FakeTransientStabilityModule()
        self.GroundGrid = FakeGroundGridModule()
        self.Reliability = FakeReliabilityModule()
        self.ProtectionCoordination = FakeProtectionModule()
        self.Buses = [FakeBus("BUS1"), FakeBus("BUS2"), FakeBus("BUS3")]
        self.Branches = [FakeBranch("LINE1-2"), FakeBranch("LINE2-3")]
        self.Equipment = [FakeEquipment("SWGR-1")]
        self.Generators = [FakeGenerator("GEN1")]
        self.Motors = [FakeMotor("MTR1")]
        self.Cables = [FakeCable("CBL1")]
        self.Relays = [FakeRelay("R1"), FakeRelay("R2")]


class FakeApp:
    def __init__(self) -> None:
        self.Visible = False
        self.Timeout = 0
        self.project = FakeProject()
        self.quit_called = False

    def OpenProject(self, path: str) -> FakeProject | None:  # noqa: N802
        return self.project if Path(path).exists() else None

    def NewProject(self) -> FakeProject:  # noqa: N802
        return FakeProject()

    def Quit(self) -> None:
        self.quit_called = True


@pytest.fixture
def fake_app(monkeypatch: pytest.MonkeyPatch) -> FakeApp:
    """Wire a fake ETAP application into etap_com's COM entry points."""
    app = FakeApp()

    def _dispatch(_prog_id: str, *args: Any, **kwargs: Any) -> FakeApp:
        return app

    if hasattr(etap_com, "win32com"):
        monkeypatch.setattr(etap_com.win32com.client, "Dispatch", _dispatch)
    else:
        fake_win32 = type(
            "win32com", (), {"client": type("client", (), {"Dispatch": staticmethod(_dispatch)})}
        )
        monkeypatch.setattr(etap_com, "win32com", fake_win32, raising=False)
    if hasattr(etap_com, "pythoncom"):
        monkeypatch.setattr(etap_com.pythoncom, "CoInitialize", lambda: None)
    else:
        fake_pythoncom = type(
            "pythoncom", (), {"CoInitialize": staticmethod(lambda: None), "com_error": RuntimeError}
        )
        monkeypatch.setattr(etap_com, "pythoncom", fake_pythoncom, raising=False)
    monkeypatch.setattr(etap_com, "WIN32_AVAILABLE", True)
    return app


@pytest.fixture
def project_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a contained .edb placeholder inside the working directory."""
    target = Path.cwd() / "__wp0_fake_project__.edb"
    target.write_text("fake-edb", encoding="utf-8")
    try:
        yield target
    finally:
        target.unlink(missing_ok=True)


def _run(fake_app: FakeApp, project_file: Path, study_type: ETAPStudyType, **params: Any):
    with ETAPAutomation(visible=False) as etap:
        project = etap.open_project(str(project_file))
        assert project is not None, "fake app must open an existing .edb path"
        return project.run_study(study_type, **params)


# ---------------------------------------------------------------------------
# 1. run_study routing across study types
# ---------------------------------------------------------------------------


class TestRunStudyRouting:
    def test_load_flow(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.LOAD_FLOW)
        assert result.success is True
        assert result.errors == []
        assert fake_app.project.LoadFlow.calculate_calls == 1
        assert set(result.data["buses"]) == {"BUS1", "BUS2", "BUS3"}
        assert result.data["iterations"] == 4
        assert set(result.data["branches"]) == {"LINE1-2", "LINE2-3"}

    def test_short_circuit(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(
            fake_app,
            project_file,
            ETAPStudyType.SHORT_CIRCUIT,
            fault_type="LineToGround",
        )
        assert result.success is True
        assert fake_app.project.ShortCircuit.FaultType == "LineToGround"
        bus1 = result.data["fault_currents"]["BUS1"]
        assert bus1["three_phase_ka"] == pytest.approx(18.4)
        assert bus1["line_to_ground_ka"] == pytest.approx(16.1)

    def test_arc_flash(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(
            fake_app,
            project_file,
            ETAPStudyType.ARC_FLASH,
            working_distance_mm=610,
        )
        assert result.success is True
        equip = result.data["equipment_results"]["SWGR-1"]
        assert equip["ppe_level"] == "2"
        assert result.data["standard"].startswith("IEEE 1584")

    def test_harmonic_analysis(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.HARMONIC_ANALYSIS)
        assert result.success is True
        assert result.data["buses"]["BUS1"]["voltage_thd_percent"] == pytest.approx(2.9)

    def test_optimal_power_flow(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.OPTIMAL_POWER_FLOW)
        assert result.success is True
        gen = result.data["generators"]["GEN1"]
        assert gen["active_power_mw"] == pytest.approx(55.0)
        assert result.data["total_system_loss_mw"] == pytest.approx(2.1)

    def test_motor_starting(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.MOTOR_STARTING)
        assert result.success is True
        motor = result.data["motors"]["MTR1"]
        assert motor["starting_current_multiplier"] == pytest.approx(5.8)
        assert result.data["starting_method"] == "Across-the-Line"

    def test_transient_stability(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.TRANSIENT_STABILITY)
        assert result.success is True
        gen = result.data["generators"]["GEN1"]
        assert gen["max_angle_deg"] == pytest.approx(33.0)
        assert result.data["stable"] is True

    def test_protection_coordination(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.PROTECTION_COORDINATION)
        assert result.success is True
        pair = result.data["relay_pairs"]["R1"]
        assert pair["all_coordinated"] is True
        assert result.data["relay_pairs"]["R2"]["tms"] == pytest.approx(0.3)

    def test_ground_grid(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.GROUND_GRID)
        assert result.success is True
        assert result.data["grid_resistance_ohm"] == pytest.approx(0.62)
        assert result.data["compliance"]["touch_ok"] is True

    def test_reliability(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.RELIABILITY)
        assert result.success is True
        indices = result.data["indices"]
        assert indices["SAIFI"] == pytest.approx(0.002)
        assert indices["SAIDI"] == pytest.approx(0.09)

    def test_cable_ampacity(self, fake_app: FakeApp, project_file: Path) -> None:
        result = _run(fake_app, project_file, ETAPStudyType.CABLE_AMACITY)
        assert result.success is True
        cable = result.data["cables"]["CBL1"]
        assert cable["derated_ampacity_a"] == pytest.approx(288.0)

    def test_open_project_missing_file_returns_none(
        self, fake_app: FakeApp, project_file: Path
    ) -> None:
        with ETAPAutomation(visible=False) as etap:
            assert etap.open_project(str(project_file)) is not None
            missing = project_file.with_name("__missing__.edb")
            assert etap.open_project(str(missing)) is None

    def test_run_study_requires_open_project(self, fake_app: FakeApp) -> None:
        project = etap_com.ETAPProject(FakeProject(), "unused.edb")
        project.is_open = False
        with pytest.raises(RuntimeError, match="not open"):
            project.run_study(ETAPStudyType.LOAD_FLOW)


# ---------------------------------------------------------------------------
# 2. Parameter schemas
# ---------------------------------------------------------------------------


class TestParameterSchemas:
    def test_every_schema_type_has_declared_entries(self) -> None:
        covered = {
            ETAPStudyType.LOAD_FLOW,
            ETAPStudyType.SHORT_CIRCUIT,
            ETAPStudyType.ARC_FLASH,
            ETAPStudyType.HARMONIC_ANALYSIS,
            ETAPStudyType.OPTIMAL_POWER_FLOW,
            ETAPStudyType.MOTOR_STARTING,
            ETAPStudyType.MOTOR_ACCELERATION,
            ETAPStudyType.PROTECTION_COORDINATION,
            ETAPStudyType.TRANSIENT_STABILITY,
            ETAPStudyType.CABLE_AMACITY,
            ETAPStudyType.GROUND_GRID,
            ETAPStudyType.RELIABILITY,
        }
        assert set(STUDY_TYPE_PARAMETER_SCHEMAS) == covered

    def test_unknown_parameter_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown parameter 'bogus_key'"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.LOAD_FLOW, {"bogus_key": 1}
            )

    def test_out_of_range_integer_rejected(self) -> None:
        with pytest.raises(ValueError, match="above maximum"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.LOAD_FLOW, {"max_iterations": 5000}
            )

    def test_invalid_enum_choice_rejected(self) -> None:
        with pytest.raises(ValueError, match="not in allowed"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.LOAD_FLOW, {"method": "psychic"}
            )

    def test_wrong_scalar_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be numeric"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.LOAD_FLOW, {"tolerance": "loose"}
            )

    def test_numeric_range_rejected_for_short_circuit(self) -> None:
        with pytest.raises(ValueError, match="above maximum"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.SHORT_CIRCUIT, {"prefault_voltage_pu": 2.0}
            )

    def test_below_minimum_rejected_for_arc_flash(self) -> None:
        with pytest.raises(ValueError, match="below minimum"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.ARC_FLASH, {"working_distance_mm": 10}
            )

    def test_boolean_type_enforced(self) -> None:
        with pytest.raises(ValueError, match="must be boolean"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.HARMONIC_ANALYSIS, {"include_interharmonics": "yes"}
            )

    def test_list_type_enforced(self) -> None:
        with pytest.raises(ValueError, match="must be a list"):
            ETAPAutomation._validate_study_parameters(
                ETAPStudyType.TRANSIENT_STABILITY, {"event_list": "fault@1s"}
            )

    def test_non_dict_params_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be a dict"):
            ETAPAutomation._validate_study_parameters(ETAPStudyType.LOAD_FLOW, ["x"])

    def test_non_enum_study_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be ETAPStudyType"):
            ETAPAutomation._validate_study_parameters("LOAD_FLOW", {})

    def test_valid_parameters_pass_through(self) -> None:
        params = {
            "method": "newton_raphson",
            "max_iterations": 30,
            "tolerance": 1e-06,
        }
        validated = ETAPAutomation._validate_study_parameters(
            ETAPStudyType.LOAD_FLOW, params
        )
        assert validated == params


# ---------------------------------------------------------------------------
# 3. Project path guards
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_app")
class TestPathGuards:
    def _automation(self) -> ETAPAutomation:
        return ETAPAutomation(visible=False)

    def test_relative_edb_under_cwd_accepted(self) -> None:
        assert self._automation()._validate_project_path("networks/demo.edb") is True

    def test_absolute_edb_under_cwd_accepted(self) -> None:
        candidate = Path.cwd() / "networks" / "demo.edb"
        assert self._automation()._validate_project_path(str(candidate)) is True

    def test_missing_extension_rejected(self) -> None:
        assert self._automation()._validate_project_path("networks/demo.oti") is False

    def test_empty_and_non_string_rejected(self) -> None:
        auto = self._automation()
        assert auto._validate_project_path("") is False
        assert auto._validate_project_path(None) is False
        assert auto._validate_project_path(123) is False

    def test_unc_path_rejected(self) -> None:
        assert self._automation()._validate_project_path(r"\\server\share\p.edb") is False

    def test_traversal_escape_rejected(self) -> None:
        assert self._automation()._validate_project_path(r"..\..\..\evil.edb") is False

    def test_overlong_path_rejected(self) -> None:
        auto = self._automation()
        deep = "a" * 5000
        assert auto._validate_project_path(f"{deep}.edb") is False

    def test_allowed_directory_enforcement(self, tmp_path: Path) -> None:
        allowed_dir = Path.cwd() / "__wp0_allowed_dir__"
        other_dir = Path.cwd() / "__wp0_other_dir__"
        allowed_dir.mkdir(exist_ok=True)
        other_dir.mkdir(exist_ok=True)
        try:
            auto = self._automation()
            auto.add_allowed_project_directory(str(allowed_dir))
            assert auto._validate_project_path(str(allowed_dir / "ok.edb")) is True
            assert auto._validate_project_path(str(other_dir / "bad.edb")) is False
        finally:
            allowed_dir.rmdir()
            other_dir.rmdir()


# ---------------------------------------------------------------------------
# 4. Convenience wrapper
# ---------------------------------------------------------------------------


class TestRunEtapStudyWrapper:
    def test_run_etap_study_end_to_end(
        self, fake_app: FakeApp, project_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = etap_com.run_etap_study(
            str(project_file), ETAPStudyType.LOAD_FLOW, tolerance=0.001
        )
        assert result.success is True
        assert result.study_type == ETAPStudyType.LOAD_FLOW.value
        assert fake_app.project.LoadFlow.calculate_calls == 1
