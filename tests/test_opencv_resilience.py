"""
tests/test_opencv_resilience.py — Tests for OpenCV vision + Resilience layer.

Covers:
  1. integrations/opencv_vision.py — OpenCVVisionClient
  2. integrations/resilience.py — retry_with_backoff, CheckpointStore,
     HybridVisionRouter, ResumeManager

Design: tests run on CI/HF Space (headless, no OpenCV) without crashing.
When deps are missing, we assert graceful fallback — never skip.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1. OpenCV Vision — module imports cleanly on any environment
# ---------------------------------------------------------------------------


def test_opencv_vision_module_imports_cleanly():
    """integrations.opencv_vision must be importable on any environment."""
    from integrations import opencv_vision

    assert hasattr(opencv_vision, "OpenCVVisionClient")
    assert hasattr(opencv_vision, "opencv_vision")


def test_opencv_vision_health_check_returns_dict():
    """health_check() must return a dict, never crash."""
    from integrations.opencv_vision import opencv_vision

    health = opencv_vision.health_check()
    assert isinstance(health, dict)
    assert "enabled" in health
    assert "cv2_available" in health
    assert "pil_available" in health
    assert "ocr_enabled" in health
    assert "tesseract_status" in health


def test_opencv_vision_analyze_screenshot_returns_none_when_disabled():
    """When OpenCV is disabled, analyze_screenshot must return None — not raise."""
    from integrations.opencv_vision import OpenCVVisionClient

    # Create a fresh client and check behavior
    client = OpenCVVisionClient()
    if not client.enabled:
        result = client.analyze_screenshot(image=b"fake", objective="test")
        assert result is None
    else:
        # If enabled, we expect either a result or an error dict
        result = client.analyze_screenshot(image=b"fake-bytes", objective="test")
        assert isinstance(result, (dict, type(None)))


def test_opencv_vision_find_element_by_text_returns_none_when_disabled():
    """find_element_by_text must return None when OCR is disabled."""
    from integrations.opencv_vision import OpenCVVisionClient

    client = OpenCVVisionClient()
    if not client.ocr_enabled:
        result = client.find_element_by_text(image=b"fake", target_text="Run")
        assert result is None
    else:
        # If OCR enabled, expect a dict (found or not-found)
        result = client.find_element_by_text(image=b"fake", target_text="Run")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 2. Resilience — retry_with_backoff decorator
# ---------------------------------------------------------------------------


def test_retry_with_backoff_succeeds_first_try():
    """If the function succeeds on first attempt, no retry happens."""
    from integrations.resilience import retry_with_backoff

    call_count = [0]

    @retry_with_backoff(max_retries=3, base_delay=0.01)
    def succeed():
        call_count[0] += 1
        return "ok"

    result = succeed()
    assert result == "ok"
    assert call_count[0] == 1


def test_retry_with_backoff_retries_on_failure():
    """If the function fails, it must retry up to max_retries times."""
    from integrations.resilience import retry_with_backoff

    call_count = [0]

    @retry_with_backoff(max_retries=2, base_delay=0.01)
    def fail_twice_then_succeed():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError("transient")
        return "recovered"

    result = fail_twice_then_succeed()
    assert result == "recovered"
    assert call_count[0] == 3


def test_retry_with_backoff_raises_after_max_retries():
    """If all retries fail, the last exception must be raised."""
    from integrations.resilience import retry_with_backoff

    call_count = [0]

    @retry_with_backoff(max_retries=2, base_delay=0.01)
    def always_fail():
        call_count[0] += 1
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError, match="permanent"):
        always_fail()
    assert call_count[0] == 3  # 1 initial + 2 retries


# ---------------------------------------------------------------------------
# 3. Resilience — CheckpointStore
# ---------------------------------------------------------------------------


def test_checkpoint_store_save_and_load():
    """CheckpointStore must save and load checkpoints atomically."""
    from integrations.resilience import CheckpointStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore(directory=tmpdir)

        # Save a checkpoint
        filepath = store.save(
            execution_id="test-exec-123",
            step_num=5,
            objective="Open ETAP",
            completed_steps=[{"step": 1}, {"step": 2}],
            context="Step 5 done",
        )
        assert filepath.exists()

        # Load it back
        loaded = store.load_latest("test-exec-123")
        assert loaded is not None
        assert loaded["execution_id"] == "test-exec-123"
        assert loaded["step_num"] == 5
        assert loaded["objective"] == "Open ETAP"
        assert len(loaded["completed_steps"]) == 2
        assert loaded["context"] == "Step 5 done"
        assert "timestamp" in loaded


def test_checkpoint_store_load_latest_picks_most_recent():
    """load_latest must return the checkpoint with the highest step number."""
    from integrations.resilience import CheckpointStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore(directory=tmpdir)

        store.save(execution_id="exec-A", step_num=1, objective="obj", completed_steps=[])
        store.save(execution_id="exec-A", step_num=5, objective="obj", completed_steps=[])
        store.save(execution_id="exec-A", step_num=3, objective="obj", completed_steps=[])

        latest = store.load_latest("exec-A")
        assert latest is not None
        assert latest["step_num"] == 5


def test_checkpoint_store_load_latest_returns_none_if_empty():
    """load_latest must return None if no checkpoints exist."""
    from integrations.resilience import CheckpointStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore(directory=tmpdir)
        result = store.load_latest("nonexistent-exec")
        assert result is None


def test_checkpoint_store_cleanup_keeps_last_n():
    """cleanup() must delete old checkpoints, keeping only the last N."""
    from integrations.resilience import CheckpointStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore(directory=tmpdir)

        for step in range(1, 6):  # 5 checkpoints
            store.save(execution_id="exec-B", step_num=step, objective="obj", completed_steps=[])

        deleted = store.cleanup("exec-B", keep_last=2)
        assert deleted == 3  # deleted 3, kept 2

        remaining = store.list_checkpoints("exec-B")
        assert len(remaining) == 2


def test_checkpoint_store_clear_all():
    """clear_all must delete all checkpoints for an execution_id."""
    from integrations.resilience import CheckpointStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore(directory=tmpdir)
        for step in range(1, 4):
            store.save(execution_id="exec-C", step_num=step, objective="obj", completed_steps=[])

        deleted = store.clear_all("exec-C")
        assert deleted == 3
        assert store.list_checkpoints("exec-C") == []


# ---------------------------------------------------------------------------
# 4. Resilience — HybridVisionRouter
# ---------------------------------------------------------------------------


def test_hybrid_vision_router_initializes():
    """HybridVisionRouter must initialize without crashing."""
    from integrations.resilience import hybrid_vision

    assert hybrid_vision is not None
    health = hybrid_vision.health_check()
    assert isinstance(health, dict)
    assert "primary" in health
    assert "fallback" in health
    assert "gemini" in health
    assert "opencv" in health


def test_hybrid_vision_router_analyze_returns_dict_or_none():
    """analyze_screenshot must return a dict, None, or error dict — never raise."""
    from integrations.resilience import hybrid_vision

    result = hybrid_vision.analyze_screenshot(
        image=b"fake-bytes",
        objective="test",
    )
    # Either None (both disabled), or a dict (result or error)
    assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# 5. Resilience — ResumeManager
# ---------------------------------------------------------------------------


def test_resume_manager_start_execution_returns_unique_id():
    """start_execution must return a unique execution_id."""
    from integrations.resilience import ResumeManager

    with tempfile.TemporaryDirectory() as tmpdir:
        rm = ResumeManager(checkpoint_dir=tmpdir)
        id1 = rm.start_execution("objective A")
        id2 = rm.start_execution("objective A")
        assert id1 != id2
        # Both should start with the same hash prefix (same objective)
        assert id1.split("_")[0] == id2.split("_")[0]


def test_resume_manager_resume_returns_prior_steps():
    """If a checkpoint exists for the objective, resume_or_start must return
    the prior steps and the resume point."""
    from integrations.resilience import CheckpointStore, ResumeManager

    with tempfile.TemporaryDirectory() as tmpdir:
        store = CheckpointStore(directory=tmpdir)
        rm = ResumeManager(checkpoint_dir=tmpdir)

        # First: start a fresh execution and save a checkpoint
        exec_id = rm.start_execution("Test objective XYZ")
        store.save(
            execution_id=exec_id,
            step_num=7,
            objective="Test objective XYZ",
            completed_steps=[{"step": 1}, {"step": 2}, {"step": 3}],
            context="at step 7",
        )

        # Now: resume should find the checkpoint
        rm2 = ResumeManager(checkpoint_dir=tmpdir)
        resumed_id, resume_from, prior_steps, context = rm2.resume_or_start("Test objective XYZ")
        assert resume_from == 7
        assert len(prior_steps) == 3
        assert context == "at step 7"
        # The resumed_id should match the original
        assert resumed_id == exec_id


def test_resume_manager_resume_returns_zero_if_no_checkpoint():
    """If no checkpoint exists, resume_or_start must return step=0 and empty steps."""
    from integrations.resilience import ResumeManager

    with tempfile.TemporaryDirectory() as tmpdir:
        rm = ResumeManager(checkpoint_dir=tmpdir)
        exec_id, resume_from, prior_steps, context = rm.resume_or_start("Brand new objective")
        assert resume_from == 0
        assert prior_steps == []
        assert context == ""


# ---------------------------------------------------------------------------
# 6. CUAExecutor — uses Hybrid Vision + Checkpointing
# ---------------------------------------------------------------------------


def test_cua_execution_result_has_resilience_fields():
    """CUAExecutionResult.to_dict() must include execution_id, resumed_from_step,
    and vision_source fields."""
    from agents.cua_executor import CUAAction, CUAExecutionResult, CUAStepResult

    result = CUAExecutionResult(
        success=True,
        steps=[
            CUAStepResult(
                step_number=1,
                action=CUAAction(type="click", x=100, y=200),
                success=True,
                duration_ms=100,
            ),
        ],
        final_summary="Done",
        objective_complete=True,
        total_duration_ms=500,
        execution_id="test-exec-456",
        resumed_from_step=3,
        vision_source="gemini",
    )

    d = result.to_dict()
    assert d["execution_id"] == "test-exec-456"
    assert d["resumed_from_step"] == 3
    assert d["vision_source"] == "gemini"
    # Must still be JSON-serializable
    json_str = json.dumps(d, default=str)
    parsed = json.loads(json_str)
    assert parsed["execution_id"] == "test-exec-456"


def test_cua_executor_uses_hybrid_vision():
    """CUAExecutor.execute_loop must use HybridVisionRouter (not direct gemini_vision)."""
    # Read the source and verify the import
    p = Path(__file__).resolve().parent.parent / "agents" / "cua_executor.py"
    content = p.read_text(encoding="utf-8")
    assert "from integrations.resilience import" in content
    assert "hybrid_vision" in content
    assert "CheckpointStore" in content
    assert "resume_manager" in content


def test_browser_cua_executor_uses_hybrid_vision():
    """BrowserCUAExecutor.execute_loop must use HybridVisionRouter."""
    p = Path(__file__).resolve().parent.parent / "agents" / "browser_cua_executor.py"
    content = p.read_text(encoding="utf-8")
    assert "from integrations.resilience import" in content
    assert "hybrid_vision" in content
    assert "CheckpointStore" in content


# ---------------------------------------------------------------------------
# 7. Integration: health endpoint exposes resilience status
# ---------------------------------------------------------------------------


def test_health_endpoint_exposes_resilience_info():
    """The /etap-gui/health endpoint should expose resilience/vision status."""
    p = Path(__file__).resolve().parent.parent / "api" / "agents.py"
    content = p.read_text(encoding="utf-8")
    # The health endpoint must mention gemini_vision
    assert "gemini_vision" in content


def test_hf_space_app_health_endpoint():
    """hf-space/app.py must also expose the health endpoint."""
    p = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    content = p.read_text(encoding="utf-8")
    assert "/etap-gui/health" in content


# ---------------------------------------------------------------------------
# 8. Documentation
# ---------------------------------------------------------------------------


def test_opencv_vision_module_has_docstring():
    """integrations/opencv_vision.py must have a module-level docstring."""
    from integrations import opencv_vision

    assert opencv_vision.__doc__ is not None
    assert len(opencv_vision.__doc__) > 100


def test_resilience_module_has_docstring():
    """integrations/resilience.py must have a module-level docstring."""
    from integrations import resilience

    assert resilience.__doc__ is not None
    assert len(resilience.__doc__) > 100


# ---------------------------------------------------------------------------
# 9. Smoke test: full chain still works
# ---------------------------------------------------------------------------


def test_full_chain_imports_cleanly():
    """All CUA-related modules must import without crashing."""
    # These imports must never fail, even on headless servers
    from integrations.gemini_vision import gemini_vision
    from integrations.opencv_vision import opencv_vision
    from integrations.resilience import hybrid_vision, resume_manager

    assert gemini_vision is not None
    assert opencv_vision is not None
    assert hybrid_vision is not None
    assert resume_manager is not None

    # The hybrid router must have checked both backends
    health = hybrid_vision.health_check()
    assert "primary" in health
    assert health["primary"] in ("gemini", "opencv", "none")
