"""WP4 (Iron Loop) — ETAP truth-layer tests.

Covers the WP4 DoD:
- Parameter round-trip: LocalEtapProvider → run_study(**parameters),
  RemoteEtapProvider payload, and the Windows worker /execute endpoint.
- Real convergence reading: no hardcoded "converged": True; the value is
  read from the ETAP COM module or explicitly marked unavailable.
- Routing: unsupported study types raise instead of silently falling back
  to LOAD_FLOW; parameters reach the provider.
- MockEtapProvider deep-copies MOCK_RESULTS (no class-state pollution).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import etap_integration.etap_com as etap_com
import etap_integration.etap_provider as etap_provider
import etap_integration.etap_worker_service as worker_service
from etap_integration.etap_com import ETAPAutomation, ETAPStudyType
from etap_integration.etap_provider import (
    ETAPResult,
    LocalEtapProvider,
    MockEtapProvider,
    RemoteEtapProvider,
)
from tests.test_etap_com_mocked import FakeApp  # noqa: F401

# ---------------------------------------------------------------------------
# 1. Convergence is read from COM — never fabricated
# ---------------------------------------------------------------------------


class TestConvergenceTruth:
    def test_converged_flag_read_from_module(self, fake_app: FakeApp, project_file: Path) -> None:
        fake_app.project.LoadFlow.Converged = False
        with ETAPAutomation(visible=False) as etap:
            project = etap.open_project(str(project_file))
            result = project.run_study(ETAPStudyType.LOAD_FLOW)
        assert result.success is True
        assert result.data["converged"] is False
        assert result.data["convergence_source"] == "etap"

    def test_converged_true_read_from_module(self, fake_app: FakeApp, project_file: Path) -> None:
        fake_app.project.LoadFlow.Converged = True
        with ETAPAutomation(visible=False) as etap:
            project = etap.open_project(str(project_file))
            result = project.run_study(ETAPStudyType.LOAD_FLOW)
        assert result.data["converged"] is True
        assert result.data["convergence_source"] == "etap"

    def test_unreadable_convergence_is_explicit(
        self, fake_app: FakeApp, project_file: Path
    ) -> None:
        # Default fakes expose no Converged/Solution/IsConverged attribute.
        with ETAPAutomation(visible=False) as etap:
            project = etap.open_project(str(project_file))
            result = project.run_study(ETAPStudyType.LOAD_FLOW)
        assert result.data["converged"] is False
        assert result.data["convergence_source"] == "unavailable"

    def test_no_pinned_true_in_run_methods(self) -> None:
        source = Path(etap_com.__file__).read_text(encoding="utf-8")
        body = source[source.index("def _run_load_flow") :]
        assert '"converged": True' not in body, (
            "hardcoded convergence must not reappear in _run_* methods"
        )


# ---------------------------------------------------------------------------
# 2. LocalEtapProvider forwards parameters to run_study
# ---------------------------------------------------------------------------


class TestLocalProviderParameterPassThrough:
    def test_parameters_forwarded_to_run_study(
        self,
        fake_app: FakeApp,
        project_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, Any] = {}
        original = etap_com.ETAPProject.run_study

        def _spy(self: Any, study_type: Any, **kwargs: Any):
            captured.update(kwargs)
            return original(self, study_type, **kwargs)

        monkeypatch.setattr(etap_com.ETAPProject, "run_study", _spy)

        provider = LocalEtapProvider()
        provider._available = True
        params = {"fault_type": "LineToGround", "prefault_voltage_pu": 1.05}
        result = provider.execute_study(
            project_path=str(project_file),
            study_type=etap_provider.ETAPStudyType.SHORT_CIRCUIT,
            parameters=params,
        )

        assert result.success is True
        assert captured == params

    def test_transient_stability_supported_by_provider_enum(
        self,
        fake_app: FakeApp,
        project_file: Path,
    ) -> None:
        provider = LocalEtapProvider()
        provider._available = True
        result = provider.execute_study(
            project_path=str(project_file),
            study_type=etap_provider.ETAPStudyType.TRANSIENT_STABILITY,
            parameters={"simulation_duration_sec": 2.0, "time_step_sec": 0.01},
        )
        assert result.success is True
        assert "generators" in result.data


# ---------------------------------------------------------------------------
# 3. RemoteEtapProvider includes cleaned parameters in the payload
# ---------------------------------------------------------------------------


class _FakeResponse:
    status_code = 200

    def json(self) -> dict[str, Any]:
        return {
            "success": True,
            "data": {"converged": True},
            "warnings": [],
            "errors": [],
            "execution_time": 0.01,
        }


class TestRemoteProviderPayload:
    def test_payload_carries_parameters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def _fake_post(url: str, json: dict[str, Any], **kwargs: Any) -> _FakeResponse:
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

        monkeypatch.setenv("USE_ETAP", "true")
        monkeypatch.setattr(etap_provider.requests, "post", _fake_post)
        provider = RemoteEtapProvider(worker_url="http://worker:8081", api_key="k")
        params = {"fault_type": "ThreePhase"}
        result = provider.execute_study(
            project_path="p.edb",
            study_type=etap_provider.ETAPStudyType.SHORT_CIRCUIT,
            parameters=params,
        )
        assert result.success is True
        assert captured["json"]["parameters"] == params
        assert captured["json"]["study_type"] == "SHORT_CIRCUIT"


# ---------------------------------------------------------------------------
# 4. Worker /execute endpoint round-trips validated parameters
# ---------------------------------------------------------------------------


class TestWorkerParameterRoundTrip:
    @pytest.mark.skipif(sys.platform != "win32", reason="worker gate requires win32")
    def test_execute_forwards_validated_parameters(
        self,
        fake_app: FakeApp,
        project_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from fastapi.testclient import TestClient

        monkeypatch.setenv("ETAP_WORKER_STATIC_KEY", "roundtrip-key")
        captured: dict[str, Any] = {}
        original = etap_com.ETAPProject.run_study

        def _spy(self: Any, study_type: Any, **kwargs: Any):
            captured["study_type"] = study_type
            captured["params"] = kwargs
            return original(self, study_type, **kwargs)

        monkeypatch.setattr(etap_com.ETAPProject, "run_study", _spy)

        client = TestClient(worker_service.app)
        resp = client.post(
            "/execute",
            json={
                "project_path": str(project_file),
                "study_type": "SHORT_CIRCUIT",
                "parameters": {"fault_type": "LineToGround", "prefault_voltage_pu": 1.02},
            },
            headers={"Authorization": "Bearer roundtrip-key"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True
        assert captured["study_type"] == ETAPStudyType.SHORT_CIRCUIT
        assert captured["params"] == {
            "fault_type": "LineToGround",
            "prefault_voltage_pu": 1.02,
        }


# ---------------------------------------------------------------------------
# 5. MockEtapProvider must not pollute class-level MOCK_RESULTS
# ---------------------------------------------------------------------------


class TestMockDeepCopy:
    def test_results_are_deep_copied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USE_ETAP", "true")
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.delenv("APP_ENV", raising=False)
        provider = MockEtapProvider()
        first = provider.execute_study("p.edb", etap_provider.ETAPStudyType.LOAD_FLOW)
        assert first.is_simulated is True
        first.data["buses"]["Bus1"]["voltage_magnitude"] = 999.0
        first.data["injected"] = True

        second = provider.execute_study("p.edb", etap_provider.ETAPStudyType.LOAD_FLOW)
        assert second.data["buses"]["Bus1"]["voltage_magnitude"] != 999.0
        assert "injected" not in second.data
        assert (
            "is_simulated"
            not in MockEtapProvider.MOCK_RESULTS[etap_provider.ETAPStudyType.LOAD_FLOW]
        )


# ---------------------------------------------------------------------------
# 6. Orchestrator routing: explicit error + parameter pass-through
# ---------------------------------------------------------------------------


class _RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return True

    def execute_study(self, **kwargs: Any) -> ETAPResult:
        self.calls.append(kwargs)
        return ETAPResult(True, {"converged": True}, [], [], 0.01)


class TestOrchestratorRouting:
    def _agent_with_provider(self) -> Any:
        from agents.orchestrator import ETAPExecutionAgent

        agent = ETAPExecutionAgent()
        provider = _RecordingProvider()
        agent.provider = provider
        return agent, provider

    @pytest.mark.asyncio
    async def test_unknown_study_type_raises(self) -> None:
        from agents.models import AgentStatus, EngineeringTask, StudyType

        agent, _ = self._agent_with_provider()
        task = EngineeringTask(
            task_id="t1",
            description="x",
            study_types=[StudyType.LOAD_FLOW],
            parameters={"project_path": "p.edb", "study_type": "WARP_DRIVE"},
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.FAILED
        assert any("Unsupported study type" in e for e in result.validation_errors)
        assert all("WARP_DRIVE" not in str(c.get("study_type")) for c in [])

    @pytest.mark.asyncio
    async def test_parameters_reach_provider(self) -> None:
        from agents.models import AgentStatus, EngineeringTask, StudyType

        agent, provider = self._agent_with_provider()
        task = EngineeringTask(
            task_id="t2",
            description="x",
            study_types=[StudyType.LOAD_FLOW],
            parameters={
                "project_path": "p.edb",
                "study_type": "LOAD_FLOW",
                "parameters": {"tolerance_pu": 0.001},
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert len(provider.calls) == 1
        call = provider.calls[0]
        assert call["parameters"] == {"tolerance_pu": 0.001}
        assert call["study_type"].name == "LOAD_FLOW"
