"""
tests/test_production_blockers_regression.py
============================================
Comprehensive regression test suite verifying resolution of production blockers
and physical engineering correctness:

1. Exact approval payload binding & concurrent replay prevention (api/approvals.py, services/execution_orchestrator.py)
2. MathGuard independent recompute & trusted calculator registry security (agents/ahmed_etap_orchestrator.py)
3. Engineering benchmark integrity (engine/benchmarks/ieee_cases.py, IEEE 1584 arc gap, IEC 62933 BESS authoritative constants)
4. Fault analysis reference-bus handling & sequence network validation (fault_analysis/fault.py, engine/engine.py, agents/registry.py)
5. Modbus telemetry data quality & datastore update semantics (scada_protocols/modbus/server.py)
6. CUA dual confirmation enforcement & external-action safety (agents/cua_base_executor.py)
7. Secrets scanner pattern expansion & match preview masking (security/secrets_manager.py)
8. Canonical execution architecture & fail-closed validation guarantees
"""

from __future__ import annotations

import asyncio
import copy
import math
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from agents.ahmed_etap_orchestrator import (
    AhmedETAPSkillAgent,
    MathGuard,
    ProjectRef,
    TrustedCalculator,
    TrustedCalculatorRegistry,
)
from agents.cua_base_executor import (
    BaseCUAExecutor,
    CUAAction,
    CUAExecutionResult,
    CUAStepResult,
)
from agents.life_safety import SafetyCheckResult, life_safety_guard
from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    ShortCircuitAgent,
    StudyType,
)
from api.approvals import (
    PendingAction,
    build_canonical_execution_payload,
    compute_args_hash,
    normalize_payload_dict,
    transition_pending_action_final,
    transition_pending_action_to_executing,
)
from core_model import Bus, Line, System
from engine.engine import PowerSystemEngine
from fault_analysis.fault import FaultAnalyzer
from load_flow.load_flow import LoadFlowSolver
from scada_protocols.common.config import ModbusConfig
from scada_protocols.modbus.register_map import RegisterEntry
from scada_protocols.modbus.server import ModbusServerAdapter
from security.secrets_manager import (
    EnvironmentValidator,
    _mask_secret_preview,
)

# ============================================================================
# 1. Exact Approval Payload Matching & Replay Prevention
# ============================================================================


class TestApprovalPayloadBinding:
    """Verifies Item 1: Strict payload normalization, exact hash matching,
    and concurrent execution replay prevention."""

    def test_normalize_payload_dict_deterministic(self):
        """Dict key order differences produce identical normalized representation."""
        d1 = {"b": 2, "a": 1, "c": {"z": 26, "y": 25}, "items": [3, 2, 1]}
        d2 = {"a": 1, "c": {"y": 25, "z": 26}, "b": 2, "items": [3, 2, 1]}
        assert normalize_payload_dict(d1) == normalize_payload_dict(d2)
        assert compute_args_hash(d1) == compute_args_hash(d2)

    def test_normalize_payload_preserves_values_and_detects_tampering(self):
        """Altering any payload parameter alters the computed args hash."""
        original = {"bus_id": "BUS-1", "action": "trip", "tolerance": 0.05}
        tampered = {"bus_id": "BUS-1", "action": "trip", "tolerance": 0.06}
        assert compute_args_hash(original) != compute_args_hash(tampered)

    def test_build_canonical_execution_payload(self):
        """Build canonical execution payload filters non-canonical ephemeral transit fields."""
        raw = {
            "bus_id": "BUS-2",
            "voltage_pu": 1.02,
            "trace_id": "trace-12345",
            "request_id": "req-999",
            "timestamp": 123456789,
        }
        canonical = build_canonical_execution_payload("etap_breaker_operation", raw)
        assert canonical["tool"] == "etap_breaker_operation"
        assert "bus_id" in canonical["args"]
        assert "voltage_pu" in canonical["args"]
        assert "trace_id" not in canonical["args"]
        assert "request_id" not in canonical["args"]
        assert "timestamp" not in canonical["args"]

    @pytest.mark.asyncio
    async def test_atomic_transition_to_executing_prevents_replay(self):
        """Action cannot be transitioned to executing more than once (prevents concurrent replay)."""
        args = {"breaker_id": "CB-101", "command": "OPEN"}
        act_hash = compute_args_hash(args)
        action_id = f"act-test-replay-{uuid.uuid4().hex[:6]}"
        action = PendingAction(
            id=action_id,
            session_id="sess_1",
            tool="etap_breaker_operation",
            args=args,
            args_hash=act_hash,
            risk_class="critical",
            status="approved",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            requested_by_user_id="operator_a",
        )
        from api.database import Base, async_session, engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session() as session:
            session.add(action)
            await session.commit()

        # First execution transition succeeds
        ok, err, rec = await transition_pending_action_to_executing(action_id, act_hash)
        assert ok is True
        assert rec is not None
        assert rec.status == "executing"

        # Concurrent or second attempt to transition MUST fail
        ok2, err2, rec2 = await transition_pending_action_to_executing(action_id, act_hash)
        assert ok2 is False
        assert err2 == "APPROVAL_ALREADY_CONSUMED"

    @pytest.mark.asyncio
    async def test_transition_pending_action_final_seals_status(self):
        """Once action transitions to a final status, it cannot be executed again."""
        args = {"breaker_id": "CB-102", "command": "CLOSE"}
        act_hash = compute_args_hash(args)
        action_id = f"act-test-final-{uuid.uuid4().hex[:6]}"
        action = PendingAction(
            id=action_id,
            session_id="sess_2",
            tool="etap_breaker_operation",
            args=args,
            args_hash=act_hash,
            risk_class="critical",
            status="approved",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            requested_by_user_id="operator_b",
        )
        from api.database import Base, async_session, engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session() as session:
            session.add(action)
            await session.commit()

        ok, err, rec = await transition_pending_action_to_executing(action_id, act_hash)
        assert ok is True

        final_ok = await transition_pending_action_final(action_id, "completed")
        assert final_ok is True

        # Second transition to executing must fail
        ok2, err2, rec2 = await transition_pending_action_to_executing(action_id, act_hash)
        assert ok2 is False
        assert err2 == "APPROVAL_ALREADY_CONSUMED"


# ============================================================================
# 2. MathGuard Independent Recompute & Trusted Registry Security
# ============================================================================


class TestMathGuardIndependentRecompute:
    """Verifies Item 2: MathGuard independent power flow solving, caller authorization,
    and study_type binding."""

    def test_untrusted_calculator_registration_rejected(self):
        """Attempts to register trusted calculators without authorization fail."""
        calc = TrustedCalculator(
            calculator_id="unauth_calc",
            study_type="load_flow",
            quantity_kind="voltage",
            unit="pu",
            fn=lambda: 1.0,
        )
        with patch("agents.ahmed_etap_orchestrator.TrustedCalculatorRegistry._is_caller_authorized", return_value=False):
            with pytest.raises(PermissionError) as excinfo:
                TrustedCalculatorRegistry.register(calc)
            assert "prohibited" in str(excinfo.value).lower()

    def test_untrusted_calculator_create_rejected(self):
        """Direct creation from unauthorized external callers raises PermissionError."""
        with patch("agents.ahmed_etap_orchestrator.TrustedCalculatorRegistry._is_caller_authorized", return_value=False):
            with pytest.raises(PermissionError) as excinfo:
                TrustedCalculatorRegistry.create(
                    calculator_id="unauth_calc",
                    study_type="load_flow",
                    quantity_kind="voltage",
                    unit="pu",
                    fn=lambda: 1.0,
                )
            assert "prohibited" in str(excinfo.value).lower()

    def test_mathguard_study_type_mismatch_rejected(self):
        """MathGuard rejects validation when executed with mismatched study_type."""
        guard = MathGuard(tolerance_pct=0.01)
        calc = TrustedCalculatorRegistry.create(
            calculator_id="lf_calc",
            study_type="load_flow",
            quantity_kind="voltage",
            unit="pu",
            fn=lambda: 1.0,
        )
        result = guard.validate(
            claim_value=1.0,
            recompute=calc,
            quantity_kind="voltage",
            claim_unit="pu",
            study_type="short_circuit",
        )
        assert result.passed is False
        assert "STUDY_TYPE_MISMATCH" in result.reason

    def test_domain_recompute_performs_genuine_solving_not_slack_copy(self):
        """_build_domain_recompute runs LoadFlowSolver; altering impedance alters result."""
        # Create 2-bus system: Bus1 (slack, 1.0 pu), Bus2 (PQ load, P=0.5 pu)
        sys1 = System(base_mva=100.0)
        sys1.add_bus(Bus("B1", base_kv=13.8, bus_type="slack"))
        sys1.add_bus(Bus("B2", base_kv=13.8, bus_type="pq", load_power=complex(0.5, 0.2)))
        line1 = Line("L1", sys1.buses["B1"], sys1.buses["B2"], z1=complex(0.05, 0.2))
        sys1.add_line(line1)

        calc1 = AhmedETAPSkillAgent._build_domain_recompute(
            "load_flow", {"system": sys1, "bus_id": "B2"}, ProjectRef()
        )
        assert calc1 is not None
        v_b2_sys1 = calc1()
        assert v_b2_sys1 is not None
        # Must not be equal to slack voltage (must exhibit voltage drop across impedance)
        assert v_b2_sys1 < 1.0

        # Change line impedance to higher reactance: voltage drop must increase (v_b2 decreases)
        sys2 = copy.deepcopy(sys1)
        sys2.lines[0].z1 = complex(0.05, 0.5)
        sys2.Ybus_seq.clear()
        calc2 = AhmedETAPSkillAgent._build_domain_recompute(
            "load_flow", {"system": sys2, "bus_id": "B2"}, ProjectRef()
        )
        assert calc2 is not None
        v_b2_sys2 = calc2()
        assert v_b2_sys2 < v_b2_sys1


# ============================================================================
# 3. Engineering Benchmark Integrity
# ============================================================================


class TestBenchmarkIntegrity:
    """Verifies Item 3: Authoritative IEEE/IEC benchmark constants and physical inputs."""

    def test_bess_iec_62933_authoritative_constants(self):
        """IEC 62933 BESS benchmark uses authoritative physical baseline constants."""
        from engine.benchmarks.ieee_cases import calculate_iec_62933_bess_benchmark

        res = calculate_iec_62933_bess_benchmark()
        assert "IEC 62933" in res["standard"]
        assert res["case1_sizing_8760h"]["passed"] is True
        # Verify authoritative independent expected values
        assert math.isclose(res["case3_tou_arbitrage_dispatch"]["expected_daily_net_revenue_$"], 323.5448, rel_tol=1e-4)
        assert math.isclose(res["case5_independent_external_reference"]["subcase_b_tou_arbitrage"]["expected_charge_cost_$"], 32.9445, rel_tol=1e-4)
        assert math.isclose(res["case5_independent_external_reference"]["subcase_b_tou_arbitrage"]["expected_net_revenue_$"], 103.5387, rel_tol=1e-4)

    def test_ieee_1584_incident_energy_explicit_arc_gap(self):
        """IEEE 1584 benchmark supplies explicit arc_gap_mm per Table 8."""
        from engine.benchmarks.ieee_cases import calculate_ieee_1584_incident_energy_benchmark

        # MV switchgear benchmark: 13.8 kV, 152.4 mm (6 in) gap per Table 8
        res_mv = calculate_ieee_1584_incident_energy_benchmark(
            bolted_fault_current_ka=25.0,
            voltage_kv=13.8,
            arc_duration_sec=0.1,
            working_distance_mm=914.4,
            arc_gap_mm=152.4,
        )
        assert res_mv["incident_energy_cal_cm2"] > 0.0
        assert res_mv["arc_flash_boundary_mm"] > 0.0

        # LV MCC benchmark: 0.48 kV, 32.0 mm gap per Table 8
        res_lv = calculate_ieee_1584_incident_energy_benchmark(
            bolted_fault_current_ka=25.0,
            voltage_kv=0.48,
            arc_duration_sec=0.1,
            working_distance_mm=457.2,
            arc_gap_mm=32.0,
        )
        assert res_lv["incident_energy_cal_cm2"] > 0.0
        assert res_lv["arc_flash_boundary_mm"] > 0.0


# ============================================================================
# 4. Fault Analysis Reference Bus & Sequence Network Validation
# ============================================================================


class TestFaultAnalysisReferenceBus:
    """Verifies Item 4: Reference bus handling, sorted bus index mapping,
    and fail-closed behavior for missing or multiple slack buses."""

    @pytest.fixture
    def three_bus_system(self):
        """3-bus network with Slack at Bus2 to verify non-zero slack index."""
        sys = System(base_mva=100.0)
        sys.add_bus(Bus("B1", base_kv=11.0, bus_type="pq"))
        sys.add_bus(Bus("B2", base_kv=11.0, bus_type="slack"))
        sys.add_bus(Bus("B3", base_kv=11.0, bus_type="pq"))
        sys.add_line(Line("L1", sys.buses["B1"], sys.buses["B2"], z1=complex(0.01, 0.05)))
        sys.add_line(Line("L2", sys.buses["B2"], sys.buses["B3"], z1=complex(0.01, 0.05)))
        sys.add_line(Line("L3", sys.buses["B1"], sys.buses["B3"], z1=complex(0.02, 0.10)))
        return sys

    def test_fault_analyzer_slack_at_non_zero_index(self):
        """FaultAnalyzer accepts and correctly uses slack bus index at non-zero index."""
        z = complex(0.01, 0.05)
        y = 1.0 / z
        Y = np.zeros((3, 3), dtype=complex)
        for i, j in [(0, 1), (1, 2), (0, 2)]:
            Y[i, i] += y
            Y[j, j] += y
            Y[i, j] -= y
            Y[j, i] -= y
        # Bus 2 is slack
        fa = FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0, slack_bus_index=2)
        assert fa.slack_bus_index == 2

    def test_fault_analyzer_invalid_slack_index_raises(self):
        """Slack bus index outside [0, n) raises ValueError."""
        Y = np.eye(3, dtype=complex)
        with pytest.raises(ValueError) as excinfo:
            FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0, slack_bus_index=5)
        assert "Invalid slack_bus_index" in str(excinfo.value)

        with pytest.raises(ValueError):
            FaultAnalyzer(Y, base_mva=100.0, base_kv=11.0, slack_bus_index=-1)

    def test_engine_missing_slack_bus_raises_fail_closed(self):
        """Fault analysis on system with no slack bus raises ValueError fail-closed."""
        eng = PowerSystemEngine()
        sys = System(base_mva=100.0)
        # All PQ buses — no slack
        sys.add_bus(Bus("B1", base_kv=11.0, bus_type="pq"))
        sys.add_bus(Bus("B2", base_kv=11.0, bus_type="pq"))
        sys.add_line(Line("L1", sys.buses["B1"], sys.buses["B2"], z1=complex(0.01, 0.05)))
        eng.system = sys

        with pytest.raises(ValueError) as excinfo:
            eng.run_fault_analysis("three_phase", "B1")
        assert "No slack bus defined" in str(excinfo.value)

    def test_engine_multiple_slack_buses_raises_fail_closed(self):
        """Fault analysis on system with multiple slack buses raises ValueError fail-closed."""
        eng = PowerSystemEngine()
        sys = System(base_mva=100.0)
        sys.add_bus(Bus("B1", base_kv=11.0, bus_type="slack"))
        sys.add_bus(Bus("B2", base_kv=11.0, bus_type="slack"))
        sys.add_line(Line("L1", sys.buses["B1"], sys.buses["B2"], z1=complex(0.01, 0.05)))
        eng.system = sys

        with pytest.raises(ValueError) as excinfo:
            eng.run_fault_analysis("three_phase", "B1")
        assert "Multiple slack buses defined" in str(excinfo.value)

    def test_engine_invalid_bus_id_raises_fail_closed(self, three_bus_system):
        """Fault analysis on non-existent bus_id raises ValueError before matrix building."""
        eng = PowerSystemEngine()
        eng.system = three_bus_system

        with pytest.raises(ValueError) as excinfo:
            eng.run_fault_analysis("three_phase", "B_NON_EXISTENT")
        assert "not found in system buses" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_short_circuit_agent_sorted_bus_mapping(self, three_bus_system):
        """ShortCircuitAgent correctly uses sorted bus indexing and resolves slack bus."""
        agent = ShortCircuitAgent()
        task = EngineeringTask(
            task_id="sc_sorted_bus_test",
            description="Test sorted bus indexing in ShortCircuitAgent",
            study_types=[StudyType.SHORT_CIRCUIT],
            parameters={
                "system": three_bus_system,
                "base_kv": 11.0,
                "fault_buses": ["B1", "B3"],
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.COMPLETED
        assert "B1" in res.data["fault_results"]
        assert "B3" in res.data["fault_results"]
        assert res.data["fault_results"]["B1"]["three_phase"]["fault_current_ka"] > 0.0

    @pytest.mark.asyncio
    async def test_short_circuit_agent_invalid_fault_bus_raises(self, three_bus_system):
        """ShortCircuitAgent raises ValueError when requested fault bus is invalid."""
        agent = ShortCircuitAgent()
        task = EngineeringTask(
            task_id="sc_invalid_bus_test",
            description="Test invalid bus rejection in ShortCircuitAgent",
            study_types=[StudyType.SHORT_CIRCUIT],
            parameters={
                "system": three_bus_system,
                "base_kv": 11.0,
                "fault_buses": ["INVALID_BUS_NAME"],
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("Fault bus 'INVALID_BUS_NAME' not found" in str(err) for err in res.validation_errors)


# ============================================================================
# 5. Modbus Telemetry Data Quality & Datastore Update Semantics
# ============================================================================


class TestModbusTelemetryQuality:
    """Verifies Item 5: Telemetry freshness, non-synthetic initialization,
    and datastore update semantics."""

    def test_failed_initial_snapshot_does_not_populate_synthetic_zeros(self):
        """Failed initial provider snapshot leaves latest_snapshot empty and is_stale True."""
        reg_map = [
            RegisterEntry(
                name="BUS1_V",
                element_id="B1",
                measurement_type="voltage_magnitude",
                address=0,
                function_code=3,
                data_type="float32",
                scale=1.0,
                offset=0.0,
            )
        ]
        cfg = ModbusConfig(
            enabled=True,
            role="server",
            server_host="127.0.0.1",
            server_port=5099,
            server_unit_id=1,
            register_map=[r.__dict__ for r in reg_map],
        )
        server = ModbusServerAdapter(cfg)

        def failing_provider():
            raise RuntimeError("SCADA link down")

        server.set_provider(failing_provider)
        server.start_server()
        try:
            # Latest snapshot must NOT contain synthetic 0.0
            assert "BUS1_V" not in server.latest_snapshot
            assert server.is_stale is True
        finally:
            server.stop_server()

    def test_successful_provider_updates_snapshot_and_freshness(self):
        """Valid telemetry sets latest_snapshot and marks data fresh."""
        reg_map = [
            RegisterEntry(
                name="BUS1_V",
                element_id="B1",
                measurement_type="voltage_magnitude",
                address=0,
                function_code=3,
                data_type="float32",
                scale=1.0,
                offset=0.0,
            )
        ]
        cfg = ModbusConfig(
            enabled=True,
            role="server",
            server_host="127.0.0.1",
            server_port=5098,
            server_unit_id=1,
            register_map=[r.__dict__ for r in reg_map],
        )
        server = ModbusServerAdapter(cfg)
        server.set_provider(lambda: {"BUS1_V": 1.025})
        server.start_server()
        try:
            assert server.latest_snapshot.get("BUS1_V") == 1.025
            assert server.is_stale is False
        finally:
            server.stop_server()


# ============================================================================
# 6. CUA Dual Confirmation Enforcement
# ============================================================================


class TestCUADualConfirmationSafety:
    """Verifies Item 6: Enforcing distinct dual confirmation when required
    and rejecting single self-confirmation before action execution."""

    class MockExecutor(BaseCUAExecutor):
        def __init__(self, **kwargs):
            import tempfile
            self.temp_dir = tempfile.TemporaryDirectory()
            super().__init__(audit_dir=self.temp_dir.name, **kwargs)
            self.executed_actions = []

        def check_dependencies(self) -> dict[str, Any]:
            return {"all_available": True, "missing": []}

        def _capture_screenshot_hook(self, step_number: int, phase: str, **kwargs):
            return "dummy_screenshot_path.png"

        def _execute_action_hook(self, action: CUAAction, **kwargs):
            self.executed_actions.append(action)
            return None

        def _wait_settle(self) -> None:
            pass

        def _cleanup_on_exit(self) -> None:
            self.temp_dir.cleanup()

    def test_dual_confirmation_rejected_in_single_operator_mode(self):
        """Action requiring dual confirmation fails closed in single-operator mode."""
        executor = self.MockExecutor()
        action_dict = {
            "source": "gemini",
            "next_action": {
                "type": "click",
                "x": 100,
                "y": 100,
                "target": "Modify Protection Relay Settings",
            },
        }

        with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=action_dict):
            with patch.object(
                life_safety_guard,
                "pre_action_check",
                return_value=SafetyCheckResult(
                    blocked=False,
                    requires_dual_confirmation=True,
                    safety_level="dual_confirmation",
                    timestamp=datetime.now(timezone.utc),
                ),
            ):
                result: CUAExecutionResult = executor.execute_loop(
                    objective=f"Modify relay settings {uuid.uuid4().hex[:8]}",
                    max_steps=1,
                    mode="control",
                    single_operator_mode=True,  # Single operator attempting dual confirmation action
                    require_confirmation=True,
                    on_confirmation_request=lambda p: True,
                    bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
                )

        assert result.success is False
        assert "dual confirmation required" in (result.aborted_reason or "").lower()
        assert len(executor.executed_actions) == 0

    def test_dual_confirmation_requires_two_distinct_approvers(self):
        """Dual confirmation rejects single approver even when callback returns True."""
        executor = self.MockExecutor()
        action_dict = {
            "source": "gemini",
            "next_action": {
                "type": "click",
                "x": 100,
                "y": 100,
                "target": "Trip Substation Main Breaker",
            },
        }

        def single_human_approval_callback(payload):
            # Only 1 approver provided
            payload["confirmations"] = ["operator_1"]
            return True

        with patch("integrations.resilience.hybrid_vision.analyze_screenshot", return_value=action_dict):
            with patch.object(
                life_safety_guard,
                "pre_action_check",
                return_value=SafetyCheckResult(
                    blocked=False,
                    requires_dual_confirmation=True,
                    safety_level="dual_confirmation",
                    timestamp=datetime.now(timezone.utc),
                ),
            ):
                result: CUAExecutionResult = executor.execute_loop(
                    objective=f"Trip breaker single {uuid.uuid4().hex[:8]}",
                    max_steps=1,
                    mode="control",
                    single_operator_mode=False,
                    require_confirmation=True,
                    on_confirmation_request=single_human_approval_callback,
                    bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
                )

        assert result.success is False
        assert "two distinct approvers required" in (result.aborted_reason or "").lower()
        assert len(executor.executed_actions) == 0

    def test_dual_confirmation_succeeds_with_two_distinct_approvers(self):
        """Dual confirmation succeeds when two distinct operators confirm."""
        executor = self.MockExecutor()
        action_dict_1 = {
            "source": "gemini",
            "next_action": {
                "type": "click",
                "x": 100,
                "y": 100,
                "target": "Trip Substation Main Breaker",
            },
        }
        action_done = {"source": "gemini", "next_action": {"type": "done"}}

        def dual_approval_callback(payload):
            # Two distinct approvers
            payload["confirmations"] = ["operator_1", "operator_2"]
            return True

        with patch(
            "integrations.resilience.hybrid_vision.analyze_screenshot",
            side_effect=[action_dict_1, action_done],
        ):
            with patch.object(
                life_safety_guard,
                "pre_action_check",
                return_value=SafetyCheckResult(
                    blocked=False,
                    requires_dual_confirmation=True,
                    safety_level="dual_confirmation",
                    timestamp=datetime.now(timezone.utc),
                ),
            ):
                result: CUAExecutionResult = executor.execute_loop(
                    objective=f"Trip breaker with dual control {uuid.uuid4().hex[:8]}",
                    max_steps=2,
                    mode="control",
                    single_operator_mode=False,
                    require_confirmation=True,
                    on_confirmation_request=dual_approval_callback,
                    bounds={"min_x": 0, "min_y": 0, "max_x": 1920, "max_y": 1080},
                    allow_unverified=True,
                )

        assert result.success is True
        assert len(executor.executed_actions) == 1
        audit = result.steps[0].to_audit_dict()
        assert audit["dual_confirmed"] is True
        assert audit["self_approved"] is False


# ============================================================================
# 7. Secrets Scanner Expansion & Masking
# ============================================================================


class TestSecretsScannerImprovements:
    """Verifies Item 7: Pattern coverage expansion and secret masking in previews."""

    def test_match_preview_masking(self):
        """_mask_secret_preview masks secret tokens and values without leaking raw text."""
        raw_key = 'api_key = "sk-1234567890abcdef1234567890"'
        preview = _mask_secret_preview(raw_key)
        assert "sk-1234567890abcdef1234567890" not in preview
        assert "***" in preview or "*" in preview

        bare_token = "ghp_1234567890abcdef1234567890"
        bare_preview = _mask_secret_preview(bare_token)
        assert bare_token not in bare_preview
        assert "*" in bare_preview

    def test_scanner_detects_secrets_in_expanded_file_types(self, tmp_path: Path):
        """Default patterns scan .json, .sh, .toml, .lock, .dockerfile files."""
        # Create a shell script with an API key
        sh_file = tmp_path / "deploy.sh"
        sh_file.write_text('export OPENAI_API_KEY="sk-abcdefghijklmnopqrstuvwxyz123456789"\n')

        # Create a toml file with a secret
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('secret = "somesecrettoken1234567890abcdef"\n')

        validator = EnvironmentValidator()
        with patch.object(Path, "cwd", return_value=tmp_path):
            findings = validator.check_for_hardcoded_secrets()

        assert len(findings) >= 2
        # Verify previews are masked
        for f in findings:
            assert "sk-abcdefghijklmnopqrstuvwxyz123456789" not in f["match_preview"]
            assert "somesecrettoken1234567890abcdef" not in f["match_preview"]
            assert "*" in f["match_preview"]
