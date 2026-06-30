"""
Unit tests for worker/tasks.py — Celery task wrappers.
Covers: happy path, failure paths, ETAP disabled, payload parsing.
All tests mock the heavy backends (study engine, ETAP COM, Redis broker).
"""

import time
import uuid
from unittest.mock import MagicMock, patch

import pytest
pytest.importorskip("celery")

from services.study_service import StudyResult

# ─── Helpers ────────────────────────────────────────────────────────────────


def _fake_study_result(**overrides) -> StudyResult:
    defaults = {
        "success": True,
        "data": {"converged": True},
        "warnings": [],
        "errors": [],
        "execution_time_sec": 0.05,
        "trace_id": "test-trace",
        "task_id": "test-task",
        "study_type": "load_flow",
        "provider": "native",
    }
    defaults.update(overrides)
    return StudyResult(**defaults)


# ─── execute_engineering_study_task ─────────────────────────────────────────


class TestExecuteEngineeringStudyTask:
    """Test the Celery task that wraps execute_study_logic."""

    @patch("worker.tasks.current_task")
    @patch("worker.tasks.execute_study_logic")
    def test_happy_path(self, mock_exec, mock_current_task):
        """Task should call execute_study_logic and return model_dump()."""
        from worker.tasks import execute_engineering_study_task

        mock_exec.return_value = _fake_study_result()
        mock_current_task.update_state = MagicMock()

        study_data = {
            "study_type": "load_flow",
            "data": {
                "study_type": "load_flow",
                "system": {
                    "base_mva": 100.0,
                    "buses": [
                        {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
                        {"bus_id": 2, "bus_type": "pq", "load_power_real": 0.5},
                    ],
                    "lines": [
                        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05},
                    ],
                },
            },
        }

        # Celery tasks with bind=True: when calling directly (not .delay()),
        # the task object's .run() is called, so we call the underlying function.
        result = execute_engineering_study_task.run(study_data)

        assert mock_exec.called
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["study_type"] == "load_flow"

    @patch("worker.tasks.current_task")
    @patch("worker.tasks.execute_study_logic")
    def test_failure_propagates(self, mock_exec, mock_current_task):
        """If execute_study_logic raises, the task should re-raise."""
        from worker.tasks import execute_engineering_study_task

        mock_exec.side_effect = RuntimeError("Engine exploded")
        mock_current_task.update_state = MagicMock()

        study_data = {
            "study_type": "load_flow",
            "data": {"study_type": "load_flow"},
        }

        with pytest.raises(RuntimeError, match="Engine exploded"):
            execute_engineering_study_task.run(study_data)

    @patch("worker.tasks.current_task")
    @patch("worker.tasks.execute_study_logic")
    def test_payload_dict_parsed_as_study_request(self, mock_exec, mock_current_task):
        """The 'data' key should be unpacked into a StudyRequest."""
        from services.study_service import StudyRequest
        from worker.tasks import execute_engineering_study_task

        mock_exec.return_value = _fake_study_result()
        mock_current_task.update_state = MagicMock()

        study_data = {
            "study_type": "load_flow",
            "data": {"study_type": "load_flow"},
            "trace_id": "custom-trace",
        }

        execute_engineering_study_task.run(study_data)

        # Verify execute_study_logic received a StudyRequest
        call_args = mock_exec.call_args
        payload = call_args[0][0]
        assert isinstance(payload, StudyRequest)
        assert payload.study_type == "load_flow"


# ─── execute_etap_integration_task ──────────────────────────────────────────


class TestExecuteEtapIntegrationTask:
    """Test the ETAP COM integration Celery task."""

    @patch("worker.tasks.current_task")
    def test_etap_disabled_returns_error(self, mock_current_task):
        """When USE_ETAP is false, the task should return an error dict."""
        from worker.tasks import execute_etap_integration_task

        mock_current_task.update_state = MagicMock()
        result = execute_etap_integration_task.run(
            {"command": "run_load_flow", "project_path": "/fake.etap"},
        )
        assert "error" in result
        assert "disabled" in result["error"].lower()

    @patch("worker.tasks.current_task")
    @patch.dict("os.environ", {"USE_ETAP": "true"})
    def test_etap_enabled_calls_provider(self, mock_current_task):
        """When USE_ETAP is true, the task should attempt to call the provider."""
        from worker.tasks import execute_etap_integration_task

        mock_current_task.update_state = MagicMock()

        # Patch the factory function inside the task
        with patch("etap_integration.etap_provider.get_etap_provider") as mock_factory:
            mock_provider = MagicMock()
            mock_provider.execute_command.return_value = {"status": "ok"}
            mock_factory.return_value = mock_provider

            result = execute_etap_integration_task.run(
                {"command": "run_load_flow"},
            )
            assert isinstance(result, dict)


# ─── process_large_calculation_task ─────────────────────────────────────────


class TestProcessLargeCalculationTask:
    """Test the heavy-computation Celery task."""

    @patch("worker.tasks.current_task")
    @patch("worker.tasks.np", create=True)
    def test_numpy_computation(self, mock_np, mock_current_task):
        """Verify the task performs matrix operations with numpy."""
        from worker.tasks import process_large_calculation_task

        # Mock numpy
        mock_matrix = MagicMock()
        mock_matrix.shape = (10, 10)
        mock_np.random.rand.return_value = mock_matrix
        mock_np.linalg.inv.return_value = mock_matrix
        mock_np.eye.return_value = mock_matrix
        mock_current_task.update_state = MagicMock()

        result = process_large_calculation_task.run(
            {"type": "matrix_inv", "size": 10, "iterations": 2},
        )

        assert result["completed"] is True
        assert result["size"] == 10
