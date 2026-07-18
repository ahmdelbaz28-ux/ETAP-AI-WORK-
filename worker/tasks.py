"""
Celery tasks for executing heavy engineering computations.
These tasks run asynchronously to prevent blocking the API.
"""

import logging
import os
import time
import uuid

from celery import (
    current_task,  # noqa: F401 — re-exported for tests that patch worker.tasks.current_task
)

# Import the study execution logic from the services
from services.study_service import StudyRequest, execute_study_logic
from worker.celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True)
def execute_engineering_study_task(self, study_data: dict):
    """
    Execute an engineering study asynchronously.

    Args:
        study_data (dict): The study parameters and configuration

    Returns:
        dict: The study results
    """
    try:
        # Update task progress
        self.update_state(state="PROGRESS", meta={"status": "Starting study execution..."})

        study_type = study_data.get("study_type", "Unknown")
        logger.info("Starting engineering study: %s", study_type)

        # Build a proper StudyRequest from the dict
        trace_id = study_data.get("trace_id", str(uuid.uuid4()))
        start_time = time.perf_counter()

        # If 'data' key exists (from async endpoint), use it; otherwise use study_data directly
        payload_dict = study_data.get("data", study_data)
        payload = StudyRequest(**payload_dict) if isinstance(payload_dict, dict) else payload_dict

        result = execute_study_logic(payload, trace_id=trace_id, start_time=start_time)

        logger.info("Completed engineering study: %s", study_type)

        self.update_state(
            state="SUCCESS",
            meta={
                "status": "Study completed successfully",
                "result": result.model_dump(),
            },
        )

        return result.model_dump()
    except Exception as exc:
        logger.exception("Error executing engineering study: %s", str(exc))
        self.update_state(
            state="FAILURE",
            meta={
                "status": "Study failed",
                "error": str(exc),
            },
        )
        raise exc


@app.task(bind=True)
def execute_etap_integration_task(self, etap_command: dict):
    """
    Execute ETAP COM integration task asynchronously.

    Args:
        etap_command (dict): The ETAP command parameters

    Returns:
        dict: The ETAP operation results
    """
    try:
        # Update task progress
        self.update_state(state="PROGRESS", meta={"status": "Starting ETAP integration..."})

        # Check if ETAP is enabled
        use_etap = os.environ.get("USE_ETAP", "false").lower() == "true"
        if not use_etap:
            return {"error": "ETAP integration is disabled", "result": None}

        logger.info("Starting ETAP integration: %s", etap_command.get('command', 'Unknown'))

        from etap_integration.etap_provider import get_etap_provider

        provider = get_etap_provider()
        if hasattr(provider, "execute_command"):
            result = provider.execute_command(etap_command)  # type: ignore[reportAttributeAccessIssue]
        else:
            project_path = etap_command.get("project_path", "")
            from etap_integration.etap_provider import ETAPStudyType

            study_type_str = etap_command.get("command", "LOAD_FLOW").upper()
            try:
                study_type = ETAPStudyType(study_type_str)
            except ValueError:
                study_type = ETAPStudyType.LOAD_FLOW
            res = provider.execute_study(project_path, study_type)
            result = {
                "success": res.success,
                "data": res.data,
                "warnings": res.warnings,
                "errors": res.errors,
            }

        logger.info("Completed ETAP integration: %s", etap_command.get('command', 'Unknown'))

        self.update_state(
            state="SUCCESS",
            meta={"status": "ETAP operation completed successfully", "result": result},
        )

        return result
    except Exception as exc:
        logger.exception("Error executing ETAP integration: %s", str(exc))
        self.update_state(
            state="FAILURE",
            meta={
                "status": "ETAP operation failed",
                "error": str(exc),
            },
        )
        raise exc


@app.task(bind=True)
def process_large_calculation_task(self, calculation_data: dict):
    """
    Process large calculations asynchronously.

    Args:
        calculation_data (dict): The calculation parameters

    Returns:
        dict: The calculation results
    """
    try:
        # Update task progress
        self.update_state(state="PROGRESS", meta={"status": "Starting large calculation..."})

        logger.info("Starting large calculation: %s", calculation_data.get('type', 'Unknown'))

        # Simulate a heavy calculation
        # In real implementation, this would contain the actual computational logic
        import numpy as np

        # SECURITY (OPS-4): Validate size and iterations to prevent DoS.
        # Without these limits, an attacker could send size=100000 (80GB
        # matrix → OOM kill) or iterations=1000000 (days of CPU time).
        # Limits are generous for legitimate engineering work:
        #   size=5000 → 200MB matrix (largest realistic power-system study)
        #   iterations=1000 → ~10 minutes max
        size = min(int(calculation_data.get("size", 1000)), 5000)
        iterations = min(int(calculation_data.get("iterations", 100)), 1000)
        if size < 1 or iterations < 1:
            result = {
                "success": False,
                "error": "size and iterations must be positive integers",
            }
            return result

        # Simulate computation progress
        for i in range(iterations):
            if i % 10 == 0:
                progress = (i / iterations) * 100
                self.update_state(
                    state="PROGRESS", meta={"status": f"Calculation in progress: {progress:.1f}%"},
                )

            # Perform some heavy computation
            matrix = np.random.rand(size, size)  # NOSONAR — S6711: numpy.random.Generator migration; API change required
            result_matrix = np.linalg.inv(matrix + np.eye(size))

        result = {
            "completed": True,
            "size": size,
            "iterations": iterations,
            "final_result_shape": result_matrix.shape,
            "message": "Large calculation completed successfully",
        }

        logger.info("Completed large calculation: %s", calculation_data.get('type', 'Unknown'))

        self.update_state(
            state="SUCCESS", meta={"status": "Calculation completed successfully", "result": result},
        )

        return result
    except Exception as exc:
        logger.exception("Error processing large calculation: %s", str(exc))
        self.update_state(
            state="FAILURE",
            meta={
                "status": "Calculation failed",
                "error": str(exc),
            },
        )
        raise exc


@app.task(bind=False, name="worker.tasks.celery_heartbeat", ignore_result=True)
def celery_heartbeat():
    """Periodic heartbeat task — emits a log line every 60s for monitoring.

    This task is scheduled by Celery Beat and is used to confirm the worker
    pool is alive and processing tasks.  Prometheus / Grafana can alert when
    this metric stops appearing.
    """
    import socket

    hostname = socket.gethostname()
    logger.info(
        "celery_heartbeat worker=%s timestamp=%s",
        hostname,
        time.time(),
    )
    # Optionally push heartbeat to Redis for external monitoring
    try:
        import redis as _redis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = _redis.from_url(redis_url, socket_timeout=5)
        r.set(f"etap:worker:heartbeat:{hostname}", "alive", ex=120)
    except Exception:
        pass  # heartbeat is best-effort

    return {"status": "alive", "worker": hostname, "ts": time.time()}
