"""
Celery tasks for executing heavy engineering computations.
These tasks run asynchronously to prevent blocking the API.
"""

import logging
import os
import time
import uuid

from celery import current_task

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
        current_task.update_state(state="PROGRESS", meta={"status": "Starting study execution..."})

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

        current_task.update_state(
            state="SUCCESS",
            meta={
                "status": "Study completed successfully",
                "result": result.model_dump(),
            },
        )

        return result.model_dump()
    except Exception as exc:
        logger.error("Error executing engineering study: %s", str(exc))
        current_task.update_state(
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
        current_task.update_state(state="PROGRESS", meta={"status": "Starting ETAP integration..."})

        # Check if ETAP is enabled
        use_etap = os.environ.get("USE_ETAP", "false").lower() == "true"
        if not use_etap:
            return {"error": "ETAP integration is disabled", "result": None}

        logger.info(f"Starting ETAP integration: {etap_command.get('command', 'Unknown')}")

        # Import ETAP provider only when needed (to avoid Windows dependency issues)
        from etap_integration.etap_provider import ETAPProvider

        provider = ETAPProvider()
        result = provider.execute_command(etap_command)

        logger.info(f"Completed ETAP integration: {etap_command.get('command', 'Unknown')}")

        current_task.update_state(
            state="SUCCESS",
            meta={"status": "ETAP operation completed successfully", "result": result},
        )

        return result
    except Exception as exc:
        logger.error(f"Error executing ETAP integration: {str(exc)}")
        current_task.update_state(
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
        current_task.update_state(
            state="PROGRESS", meta={"status": "Starting large calculation..."}
        )

        logger.info(f"Starting large calculation: {calculation_data.get('type', 'Unknown')}")

        # Simulate a heavy calculation
        # In real implementation, this would contain the actual computational logic
        import numpy as np

        # Example: Heavy matrix computation
        size = calculation_data.get("size", 1000)
        iterations = calculation_data.get("iterations", 100)

        # Simulate computation progress
        for i in range(iterations):
            if i % 10 == 0:
                progress = (i / iterations) * 100
                current_task.update_state(
                    state="PROGRESS", meta={"status": f"Calculation in progress: {progress:.1f}%"}
                )

            # Perform some heavy computation
            matrix = np.random.rand(size, size)
            result_matrix = np.linalg.inv(matrix + np.eye(size))

        result = {
            "completed": True,
            "size": size,
            "iterations": iterations,
            "final_result_shape": result_matrix.shape,
            "message": "Large calculation completed successfully",
        }

        logger.info(f"Completed large calculation: {calculation_data.get('type', 'Unknown')}")

        current_task.update_state(
            state="SUCCESS", meta={"status": "Calculation completed successfully", "result": result}
        )

        return result
    except Exception as exc:
        logger.error(f"Error processing large calculation: {str(exc)}")
        current_task.update_state(
            state="FAILURE",
            meta={
                "status": "Calculation failed",
                "error": str(exc),
            },
        )
        raise exc
