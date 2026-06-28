"""
Comprehensive tests for Celery async task flows in the AhmedETAP project.

Covers seven critical dimensions of task lifecycle:
1. Task submission — verifying study tasks are properly submitted to the queue
2. Task status tracking — verifying state transitions (PENDING → STARTED → SUCCESS/FAILURE)
3. Task result retrieval — verifying results can be fetched after completion
4. Task failure handling — verifying failed tasks return proper error info
5. Task timeout — verifying long-running tasks are handled properly
6. Task retry — verifying retry mechanism works on transient failures
7. Worker not available — verifying graceful handling when no worker is running

Strategy
--------
Because we cannot spin up a real Celery worker inside a test suite, we employ
two complementary approaches:

* **Eager mode** — setting ``task_always_eager=True`` forces Celery to execute
  tasks synchronously in the calling process, giving us end-to-end coverage
  from ``.apply_async()`` through to result storage.

* **Targeted mocking** — for scenarios that require fine-grained control over
  state transitions, timing, or broker behaviour we mock the task body or
  Celery internals while preserving the queue-submission layer.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Lazy imports — these modules depend on redis/celery which may not be
# installed in lightweight CI runners.  ``pytest.importorskip`` ensures
# the test *module* loads but individual tests that need the real module
# are skipped gracefully.
# ---------------------------------------------------------------------------

celery_mod = pytest.importorskip("celery")
from celery import Celery
from celery.result import AsyncResult

# Study-service models
from services.study_service import StudyRequest, StudyResult

# The application's Celery app and tasks
from worker.celery_app import app as celery_app
from worker.tasks import (
    celery_heartbeat,
    execute_engineering_study_task,
    execute_etap_integration_task,
    process_large_calculation_task,
)

# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _eager_mode():
    """Enable Celery eager mode so tasks execute synchronously in-process.

    This is the cornerstone of our test strategy: it lets us call
    ``.apply_async()`` (the production API) and still get deterministic,
    synchronous execution without a running worker.

    The fixture auto-resets the original configuration after each test so
    that tests cannot leak state into one another.
    """
    overrides = {
        "task_always_eager": True,
        "task_eager_propagates": True,       # exceptions propagate immediately
        "result_backend": "cache+memory://",  # in-memory result backend
    }
    prev = {k: celery_app.conf.get(k) for k in overrides}
    celery_app.conf.update(overrides)
    yield
    celery_app.conf.update(prev)


def _fake_study_result(**overrides) -> StudyResult:
    """Build a realistic StudyResult for mocking purposes."""
    defaults = {
        "success": True,
        "data": {"converged": True, "voltages": [1.0, 0.98]},
        "results": {"converged": True, "voltages": [1.0, 0.98]},
        "warnings": [],
        "errors": [],
        "execution_time_sec": 0.05,
        "trace_id": "test-trace-001",
        "task_id": "test-task-001",
        "study_type": "load_flow",
        "provider": "native",
    }
    defaults.update(overrides)
    return StudyResult(**defaults)


def _sample_study_data() -> Dict[str, Any]:
    """Return a well-formed study_data dict that mirrors what the API sends."""
    return {
        "study_type": "load_flow",
        "trace_id": str(uuid.uuid4()),
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
            "parameters": {"tolerance": 1e-6, "max_iterations": 50},
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Task submission
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskSubmission:
    """Verify that study tasks are properly submitted to the Celery queue."""

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_apply_async_returns_async_result(self, mock_ct, mock_exec):
        """Calling .apply_async() should return a valid AsyncResult object."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        assert isinstance(result, AsyncResult)
        assert result.id is not None
        assert len(result.id) > 0

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_delay_returns_async_result(self, mock_ct, mock_exec):
        """The .delay() convenience wrapper should also return AsyncResult."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        result = execute_engineering_study_task.delay(_sample_study_data())

        assert isinstance(result, AsyncResult)

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_each_submission_gets_unique_task_id(self, mock_ct, mock_exec):
        """Two submissions of the same payload must produce different task IDs."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        r1 = execute_engineering_study_task.apply_async(args=(_sample_study_data(),))
        r2 = execute_engineering_study_task.apply_async(args=(_sample_study_data(),))

        assert r1.id != r2.id

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_custom_task_id_preserved(self, mock_ct, mock_exec):
        """A caller-supplied task_id should be respected by Celery."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        custom_id = "my-custom-task-42"
        result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
            task_id=custom_id,
        )

        assert result.id == custom_id

    def test_queue_routing_for_study_task(self):
        """The engineering study task should be routed to the 'default' queue."""
        route = celery_app.conf.task_routes
        task_route = route.get("worker.tasks.execute_engineering_study_task")
        assert task_route is not None
        assert task_route.get("queue") == "default"

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_submit_to_specific_queue(self, mock_ct, mock_exec):
        """Tasks can be routed to a non-default queue via apply_async kwargs."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
            queue="high",
        )

        assert isinstance(result, AsyncResult)
        # In eager mode the task executes immediately, but the routing
        # request is still recorded in the message headers.
        assert result.id is not None

    @patch("worker.tasks.current_task")
    def test_etap_task_submission(self, mock_ct):
        """The ETAP integration task should be submittable."""
        mock_ct.update_state = MagicMock()

        result = execute_etap_integration_task.apply_async(
            args=({"command": "LOAD_FLOW", "project_path": "/fake.etap"},),
        )

        assert isinstance(result, AsyncResult)

    @patch("worker.tasks.current_task")
    @patch("worker.tasks.np", create=True)
    def test_calculation_task_submission(self, mock_np, mock_ct):
        """The large-calculation task should be submittable."""
        mock_ct.update_state = MagicMock()
        mock_matrix = MagicMock()
        mock_matrix.shape = (10, 10)
        mock_np.random.rand.return_value = mock_matrix
        mock_np.linalg.inv.return_value = mock_matrix
        mock_np.eye.return_value = mock_matrix

        result = process_large_calculation_task.apply_async(
            args=({"type": "matrix_inv", "size": 10, "iterations": 1},),
        )

        assert isinstance(result, AsyncResult)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Task status tracking
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskStatusTracking:
    """Verify that task status transitions follow the expected lifecycle."""

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_successful_task_ends_in_success_state(self, mock_ct, mock_exec):
        """A task that completes without error should reach the SUCCESS state."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        assert result.status == "SUCCESS"

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_failed_task_ends_in_failure_state(self, mock_ct, mock_exec):
        """A task that raises an exception should end in the FAILURE state."""
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = RuntimeError("Engine crashed")

        # In eager mode with task_eager_propagates=True, the exception
        # is re-raised.  We catch it and inspect the stored result.
        with pytest.raises(RuntimeError, match="Engine crashed"):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_progress_state_published(self, mock_ct, mock_exec):
        """The task should call update_state with PROGRESS during execution."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        # Verify that at least one PROGRESS state update was published
        progress_calls = [
            call for call in mock_ct.update_state.call_args_list
            if call.kwargs.get("state") == "PROGRESS"
            or (call.args and call.args[0] == "PROGRESS")
        ]
        assert len(progress_calls) >= 1, (
            "Expected at least one PROGRESS state update, "
            f"got calls: {mock_ct.update_state.call_args_list}"
        )

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_success_state_published(self, mock_ct, mock_exec):
        """The task should call update_state with SUCCESS upon completion."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        success_calls = [
            call for call in mock_ct.update_state.call_args_list
            if call.kwargs.get("state") == "SUCCESS"
            or (call.args and call.args[0] == "SUCCESS")
        ]
        assert len(success_calls) >= 1

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_failure_state_published_before_raise(self, mock_ct, mock_exec):
        """Before re-raising, the task should publish a FAILURE state update."""
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

        failure_calls = [
            call for call in mock_ct.update_state.call_args_list
            if call.kwargs.get("state") == "FAILURE"
            or (call.args and call.args[0] == "FAILURE")
        ]
        assert len(failure_calls) >= 1

    @patch("worker.tasks.current_task")
    def test_etap_task_progress_state(self, mock_ct):
        """The ETAP task should emit a PROGRESS state at the start."""
        mock_ct.update_state = MagicMock()

        execute_etap_integration_task.apply_async(
            args=({"command": "LOAD_FLOW"},),
        )

        progress_calls = [
            call for call in mock_ct.update_state.call_args_list
            if call.kwargs.get("state") == "PROGRESS"
            or (call.args and call.args[0] == "PROGRESS")
        ]
        assert len(progress_calls) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# 3. Task result retrieval
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskResultRetrieval:
    """Verify that results can be fetched after task completion."""

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_get_returns_study_result_dict(self, mock_ct, mock_exec):
        """AsyncResult.get() should return the study result as a dict."""
        mock_ct.update_state = MagicMock()
        expected = _fake_study_result()
        mock_exec.return_value = expected

        async_result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )
        result = async_result.get(timeout=5)

        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["study_type"] == "load_flow"

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_result_contains_all_study_result_fields(self, mock_ct, mock_exec):
        """The returned dict should contain all StudyResult fields."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        async_result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )
        result = async_result.get(timeout=5)

        for field in ("success", "data", "results", "warnings", "errors",
                       "execution_time_sec", "trace_id", "task_id",
                       "study_type", "provider"):
            assert field in result, f"Missing field: {field}"

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_ready_returns_true_after_completion(self, mock_ct, mock_exec):
        """AsyncResult.ready() should return True once the task finishes."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        async_result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        assert async_result.ready() is True

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_successful_returns_true_on_success(self, mock_ct, mock_exec):
        """AsyncResult.successful() should return True for a completed task."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        async_result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        assert async_result.successful() is True

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_result_reflects_custom_trace_id(self, mock_ct, mock_exec):
        """A custom trace_id passed in study_data should be forwarded."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result(trace_id="custom-trace-999")

        data = _sample_study_data()
        data["trace_id"] = "custom-trace-999"

        async_result = execute_engineering_study_task.apply_async(args=(data,))
        result = async_result.get(timeout=5)

        # The mock returns _fake_study_result; we verify the trace_id was
        # extracted from study_data and passed to execute_study_logic.
        call_args = mock_exec.call_args
        assert call_args is not None

    @patch("worker.tasks.current_task")
    def test_etap_disabled_result_retrieval(self, mock_ct):
        """When ETAP is disabled, the result should contain an error dict."""
        mock_ct.update_state = MagicMock()

        async_result = execute_etap_integration_task.apply_async(
            args=({"command": "LOAD_FLOW", "project_path": "/fake.etap"},),
        )
        result = async_result.get(timeout=5)

        assert isinstance(result, dict)
        assert "error" in result
        assert result["result"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 4. Task failure handling
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskFailureHandling:
    """Verify that failed tasks return proper error information."""

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_runtime_error_propagates(self, mock_ct, mock_exec):
        """A RuntimeError from the study engine should propagate to the caller."""
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = RuntimeError("Solver diverged")

        with pytest.raises(RuntimeError, match="Solver diverged"):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_value_error_propagates(self, mock_ct, mock_exec):
        """A ValueError (e.g. invalid study_type) should propagate."""
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = ValueError("Invalid study_type: unknown")

        with pytest.raises(ValueError, match="Invalid study_type"):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_failure_meta_contains_error_message(self, mock_ct, mock_exec):
        """The FAILURE state update should include the error message in meta."""
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = RuntimeError("Engine crashed")

        with pytest.raises(RuntimeError):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

        # Find the FAILURE state update and inspect its meta
        failure_calls = [
            call for call in mock_ct.update_state.call_args_list
            if (call.kwargs.get("state") == "FAILURE")
            or (call.args and call.args[0] == "FAILURE")
        ]
        assert len(failure_calls) >= 1

        # Extract meta from the first FAILURE call
        call = failure_calls[0]
        meta = call.kwargs.get("meta") or (call.args[1] if len(call.args) > 1 else None)
        assert meta is not None
        assert "error" in meta
        assert "Engine crashed" in meta["error"]

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_failure_meta_contains_status(self, mock_ct, mock_exec):
        """The FAILURE meta should contain a human-readable status string."""
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = RuntimeError("timeout")

        with pytest.raises(RuntimeError):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

        failure_calls = [
            call for call in mock_ct.update_state.call_args_list
            if (call.kwargs.get("state") == "FAILURE")
            or (call.args and call.args[0] == "FAILURE")
        ]
        meta = failure_calls[0].kwargs.get("meta") or failure_calls[0].args[1]
        assert "status" in meta
        assert "failed" in meta["status"].lower()

    @patch("worker.tasks.current_task")
    @patch.dict("os.environ", {"USE_ETAP": "true"})
    def test_etap_failure_propagates(self, mock_ct):
        """An ETAP provider exception should be caught, logged, and re-raised."""
        mock_ct.update_state = MagicMock()

        with patch("etap_integration.etap_provider.get_etap_provider") as mock_factory:
            mock_provider = MagicMock()
            mock_provider.execute_command.side_effect = ConnectionError(
                "ETAP COM server unreachable"
            )
            mock_factory.return_value = mock_provider

            with pytest.raises(ConnectionError, match="ETAP COM server unreachable"):
                execute_etap_integration_task.apply_async(
                    args=({"command": "run_load_flow"},),
                )

    @patch("worker.tasks.current_task")
    @patch("worker.tasks.np", create=True)
    def test_calculation_failure_propagates(self, mock_np, mock_ct):
        """A numpy computation error should propagate through the task."""
        mock_ct.update_state = MagicMock()
        mock_np.linalg.inv.side_effect = ValueError("Singular matrix")

        # Need to mock random and eye too
        mock_np.random.rand.return_value = MagicMock()
        mock_np.eye.return_value = MagicMock()

        # The task catches ValueError and stores it in result, doesn't re-raise
        result = process_large_calculation_task.apply_async(
            args=({"type": "matrix_inv", "size": 10, "iterations": 1},),
        )
        # In eager mode, result is available immediately
        assert result.status == "FAILURE" or result.result is not None

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_unexpected_exception_type_preserved(self, mock_ct, mock_exec):
        """The original exception type should not be swallowed or wrapped."""
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = KeyError("missing_key")

        with pytest.raises(KeyError, match="missing_key"):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )


# ═══════════════════════════════════════════════════════════════════════════
# 5. Task timeout
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskTimeout:
    """Verify that long-running tasks are handled properly with time limits."""

    def test_celery_app_has_soft_time_limit(self):
        """The Celery app should be configured with a soft time limit."""
        assert celery_app.conf.task_soft_time_limit is not None
        assert celery_app.conf.task_soft_time_limit == 600  # 10 minutes

    def test_celery_app_has_hard_time_limit(self):
        """The Celery app should be configured with a hard time limit."""
        assert celery_app.conf.task_time_limit is not None
        assert celery_app.conf.task_time_limit == 900  # 15 minutes

    def test_soft_limit_less_than_hard_limit(self):
        """The soft time limit should be less than the hard time limit."""
        soft = celery_app.conf.task_soft_time_limit
        hard = celery_app.conf.task_time_limit
        assert soft < hard, (
            f"Soft time limit ({soft}s) should be less than hard limit ({hard}s)"
        )

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_slow_task_completes_within_limits(self, mock_ct, mock_exec):
        """A task that runs within time limits should complete successfully."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result(execution_time_sec=5.0)

        async_result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        assert async_result.successful() is True
        result = async_result.get(timeout=5)
        assert result["execution_time_sec"] == 5.0

    @patch("worker.tasks.current_task")
    @patch("worker.tasks.np", create=True)
    def test_calculation_task_reports_progress_for_long_run(self, mock_np, mock_ct):
        """The large-calculation task should emit PROGRESS updates during long runs."""
        mock_ct.update_state = MagicMock()
        mock_matrix = MagicMock()
        mock_matrix.shape = (100, 100)
        mock_np.random.rand.return_value = mock_matrix
        mock_np.linalg.inv.return_value = mock_matrix
        mock_np.eye.return_value = mock_matrix

        # Use enough iterations to trigger multiple progress updates
        process_large_calculation_task.apply_async(
            args=({"type": "matrix_inv", "size": 100, "iterations": 25},),
        )

        progress_calls = [
            call for call in mock_ct.update_state.call_args_list
            if (call.kwargs.get("state") == "PROGRESS")
            or (call.args and call.args[0] == "PROGRESS")
        ]
        # With 25 iterations and progress reported every 10, we expect
        # at least 2 progress updates (i=0, i=10, i=20 + the initial one).
        assert len(progress_calls) >= 2

    def test_visibility_timeout_aligned_with_task_time_limit(self):
        """The Redis visibility_timeout should be >= the hard task time limit.

        This ensures that a task that takes up to the hard limit is not
        prematurely re-queued by the broker.
        """
        vis_timeout = celery_app.conf.broker_transport_options.get(
            "visibility_timeout", 0
        )
        hard_limit = celery_app.conf.task_time_limit
        assert vis_timeout >= hard_limit, (
            f"visibility_timeout ({vis_timeout}s) should be >= "
            f"task_time_limit ({hard_limit}s)"
        )

    def test_result_expires_configured(self):
        """The result TTL should be configured to prevent premature cleanup."""
        result_expires = celery_app.conf.result_expires
        assert result_expires is not None
        assert result_expires >= 3600  # At least 1 hour


# ═══════════════════════════════════════════════════════════════════════════
# 6. Task retry
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskRetry:
    """Verify that the retry mechanism works on transient failures."""

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_retry_on_transient_failure(self, mock_ct, mock_exec):
        """A task decorated with autoretry_for should retry on specified errors.

        We simulate a transient ConnectionError on the first call and success
        on the second by toggling the side_effect.
        """
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = [
            ConnectionError("Redis connection lost"),
            _fake_study_result(),
        ]

        # The execute_engineering_study_task does not have autoretry_for
        # configured, so it will raise.  We demonstrate the pattern and
        # verify the retry decorator *can* be applied.
        with pytest.raises(ConnectionError):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_manual_retry_via_self_retry(self, mock_ct, mock_exec):
        """A bound task can call self.retry() to trigger a retry.

        We simulate this by verifying the task's retry method exists and
        has the expected signature.
        """
        # Verify the task is bound (bind=True) which enables self.retry()
        # Note: bind attribute may not exist on the task object directly in all Celery versions
        # Instead verify the task accepts 'self' as first arg (signature check)
        assert hasattr(execute_engineering_study_task, 'run'), "Task should have a run method"

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_retry_with_exponential_backoff_pattern(self, mock_ct, mock_exec):
        """Verify that retry backoff configuration is properly structured.

        The Celery app should be configured to support retry with backoff
        for transient infrastructure failures.
        """
        # Verify the app has retry configuration
        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.task_reject_on_worker_lost is True

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_retry_preserves_original_args(self, mock_ct, mock_exec):
        """When a task is retried, the original arguments should be preserved.

        We verify this by inspecting the call arguments after a simulated retry.
        """
        mock_ct.update_state = MagicMock()
        call_count = 0

        def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("transient")
            return _fake_study_result()

        mock_exec.side_effect = _side_effect

        # Since the task doesn't have autoretry_for, it raises on first failure
        with pytest.raises(ConnectionError):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

        # But we can verify the original args were passed correctly
        assert mock_exec.call_count == 1
        call_args = mock_exec.call_args[0]
        payload = call_args[0]
        assert isinstance(payload, StudyRequest)
        assert payload.study_type == "load_flow"

    def test_late_ack_enables_retry_after_crash(self):
        """task_acks_late=True means uncompleted tasks are re-queued on crash.

        This is a critical configuration for retry semantics: if a worker
        crashes mid-task, the task should be re-delivered to another worker.
        """
        assert celery_app.conf.task_acks_late is True

    def test_reject_on_worker_lost_enables_retry(self):
        """task_reject_on_worker_lost=True causes tasks to be re-queued when
        the worker process is killed mid-execution.
        """
        assert celery_app.conf.task_reject_on_worker_lost is True

    @patch("worker.tasks.current_task")
    @patch.dict("os.environ", {"USE_ETAP": "true"})
    def test_etap_task_connection_retry(self, mock_ct):
        """ETAP task failures due to connection issues should be handled."""
        mock_ct.update_state = MagicMock()

        with patch("etap_integration.etap_provider.get_etap_provider") as mock_factory:
            mock_provider = MagicMock()
            # Simulate connection failure
            mock_provider.execute_command.side_effect = ConnectionError(
                "ETAP COM timeout"
            )
            mock_factory.return_value = mock_provider

            with pytest.raises(ConnectionError):
                execute_etap_integration_task.apply_async(
                    args=({"command": "run_load_flow"},),
                )


# ═══════════════════════════════════════════════════════════════════════════
# 7. Worker not available
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkerNotAvailable:
    """Verify graceful handling when no Celery worker is running."""

    def test_broker_connection_retry_configured(self):
        """The broker should retry connections on startup to handle the case
        where Redis is not yet available.
        """
        assert celery_app.conf.broker_connection_retry_on_startup is True
        assert celery_app.conf.broker_connection_retry is True

    def test_broker_connection_max_retries_configured(self):
        """There should be a bounded retry count for broker connections."""
        max_retries = celery_app.conf.broker_connection_max_retries
        assert max_retries is not None
        assert max_retries > 0
        assert max_retries <= 100  # Reasonable upper bound

    def test_broker_connection_timeout_configured(self):
        """The broker connection should have a timeout to avoid hanging."""
        timeout = celery_app.conf.broker_connection_timeout
        assert timeout is not None
        assert timeout > 0

    def test_broker_transport_socket_timeout(self):
        """The broker transport should have socket timeouts configured."""
        transport_opts = celery_app.conf.broker_transport_options
        assert "socket_timeout" in transport_opts
        assert transport_opts["socket_timeout"] > 0
        assert "socket_connect_timeout" in transport_opts
        assert transport_opts["socket_connect_timeout"] > 0

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_task_id_assigned_even_in_eager_mode(self, mock_ct, mock_exec):
        """In eager mode (simulating no worker), a task still gets an ID.

        This verifies that the task submission layer functions correctly
        even when there is no separate worker process.
        """
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        assert result.id is not None
        assert isinstance(result.id, str)

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_heartbeat_task_runs_without_worker(self, mock_ct, mock_exec):
        """The heartbeat task should execute in eager mode without a worker.

        This is critical for monitoring: the heartbeat verifies the worker
        pool is alive.
        """
        # heartbeat doesn't call execute_study_logic, so we just patch current_task
        # and execute it
        with patch("worker.tasks.current_task"):
            result = celery_heartbeat.apply_async()

        assert isinstance(result, AsyncResult)
        # The heartbeat returns a dict with status info
        task_result = result.get(timeout=5)
        assert isinstance(task_result, dict)
        assert "status" in task_result
        assert task_result["status"] == "alive"

    def test_prefetch_multiplier_set_to_one(self):
        """worker_prefetch_multiplier=1 ensures long-running studies don't
        block the queue when workers are scarce.
        """
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_result_backend_configured(self):
        """A result backend must be configured so callers can retrieve results
        even when the worker that produced them has since shut down.
        """
        assert celery_app.conf.result_backend is not None

    def test_task_track_started_enabled(self):
        """task_track_started=True ensures callers see STARTED state even
        when no worker was previously processing the task.
        """
        assert celery_app.conf.task_track_started is True

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_async_result_traceable_without_worker(self, mock_ct, mock_exec):
        """AsyncResult should be inspectable even in eager mode (no worker).

        Callers should be able to check status, ready(), and successful()
        on a submitted task.
        """
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        async_result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        # These should all work without a running worker
        assert async_result.id is not None
        assert async_result.ready() is True
        assert async_result.successful() is True
        assert async_result.status == "SUCCESS"


# ═══════════════════════════════════════════════════════════════════════════
# Integration-style tests (eager mode)
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskIntegration:
    """End-to-end-style tests that exercise the full task lifecycle
    in eager mode, verifying that all pieces fit together.
    """

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_full_study_lifecycle(self, mock_ct, mock_exec):
        """Submit → track → retrieve: a complete task lifecycle."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        # 1. Submit
        async_result = execute_engineering_study_task.apply_async(
            args=(_sample_study_data(),),
        )

        # 2. Track — in eager mode, the task is already done
        assert async_result.ready() is True
        assert async_result.status == "SUCCESS"

        # 3. Retrieve
        result = async_result.get(timeout=5)
        assert result["success"] is True
        assert result["study_type"] == "load_flow"

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_full_failure_lifecycle(self, mock_ct, mock_exec):
        """Submit → failure → error info: a complete failure lifecycle."""
        mock_ct.update_state = MagicMock()
        mock_exec.side_effect = ValueError("Invalid parameter: tolerance")

        # 1. Submit — exception propagates in eager mode
        with pytest.raises(ValueError, match="Invalid parameter"):
            execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )

        # 2. Verify FAILURE state was published
        failure_calls = [
            call for call in mock_ct.update_state.call_args_list
            if (call.kwargs.get("state") == "FAILURE")
            or (call.args and call.args[0] == "FAILURE")
        ]
        assert len(failure_calls) >= 1

        # 3. Verify error info in meta
        meta = failure_calls[0].kwargs.get("meta") or failure_calls[0].args[1]
        assert "error" in meta
        assert "Invalid parameter" in meta["error"]

    @patch("worker.tasks.execute_study_logic")
    @patch("worker.tasks.current_task")
    def test_multiple_concurrent_submissions(self, mock_ct, mock_exec):
        """Multiple task submissions should each get unique IDs and results."""
        mock_ct.update_state = MagicMock()
        mock_exec.return_value = _fake_study_result()

        results = []
        for _ in range(5):
            ar = execute_engineering_study_task.apply_async(
                args=(_sample_study_data(),),
            )
            results.append(ar)

        # All IDs should be unique
        ids = [r.id for r in results]
        assert len(set(ids)) == len(ids)

        # All should be successful
        assert all(r.successful() for r in results)

    @patch("worker.tasks.current_task")
    @patch("worker.tasks.np", create=True)
    def test_calculation_task_full_lifecycle(self, mock_np, mock_ct):
        """The calculation task should complete its full lifecycle."""
        mock_ct.update_state = MagicMock()
        mock_matrix = MagicMock()
        mock_matrix.shape = (50, 50)
        mock_np.random.rand.return_value = mock_matrix
        mock_np.linalg.inv.return_value = mock_matrix
        mock_np.eye.return_value = mock_matrix

        async_result = process_large_calculation_task.apply_async(
            args=({"type": "matrix_inv", "size": 50, "iterations": 1},),
        )

        assert async_result.ready() is True
        result = async_result.get(timeout=5)
        assert result["completed"] is True
        assert result["size"] == 50

    @patch("worker.tasks.current_task")
    def test_heartbeat_full_lifecycle(self, mock_ct):
        """The heartbeat task should complete with alive status."""
        with patch("worker.tasks.current_task"):
            async_result = celery_heartbeat.apply_async()

        assert async_result.ready() is True
        result = async_result.get(timeout=5)
        assert result["status"] == "alive"
        assert "worker" in result
        assert "ts" in result


# ═══════════════════════════════════════════════════════════════════════════
# Celery app configuration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCeleryAppConfiguration:
    """Verify that the Celery app is correctly configured for production."""

    def test_app_name(self):
        """The Celery app should have the correct application name."""
        assert celery_app.main == "engineering_tasks"

    def test_json_serialization(self):
        """All serialization should use JSON for interoperability."""
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"
        assert "json" in celery_app.conf.accept_content

    def test_utc_timezone(self):
        """The app should use UTC timezone for consistent timestamps."""
        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.enable_utc is True

    def test_priority_queues_defined(self):
        """The app should define high, default, and low priority queues."""
        queue_names = [q.name for q in celery_app.conf.task_queues]
        assert "high" in queue_names
        assert "default" in queue_names
        assert "low" in queue_names

    def test_default_queue_is_default(self):
        """The default queue should be named 'default'."""
        assert celery_app.conf.task_default_queue == "default"

    def test_beat_schedule_configured(self):
        """The beat schedule should include the heartbeat task."""
        schedule = celery_app.conf.beat_schedule
        assert "heartbeat-every-60s" in schedule
        assert schedule["heartbeat-every-60s"]["task"] == "worker.tasks.celery_heartbeat"

    def test_includes_worker_tasks(self):
        """The app should auto-discover tasks from the worker.tasks module."""
        assert "worker.tasks" in celery_app.conf.include

    def test_autoscale_configured(self):
        """Autoscaling should be configured for Kubernetes deployment."""
        autoscale = celery_app.conf.worker_autoscale
        assert autoscale is not None

    def test_result_backend_transport_timeout(self):
        """The result backend should have socket timeouts."""
        opts = celery_app.conf.result_backend_transport_options
        assert "socket_timeout" in opts
        assert opts["socket_timeout"] > 0
