"""Unit regression test ensuring buffered SSE responses cannot pass Staging acceptance.

Verifies Gate E remediation:
- A buffered SSE stream (is_incremental=False) triggers an explicit AssertionError.
- Mandatory user login failure raises AssertionError when require_login=True.
"""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest

from scripts.test_staging_e2e_capabilities import run_full_capability_suite


@patch("scripts.test_staging_e2e_capabilities.probe_authenticated_sse", return_value=(False, [0.0, 0.005], "event: token\ndata: test\n\nevent: done\n\n"))
@patch("scripts.test_staging_e2e_capabilities.probe_engineering_study", return_value={"incident_energy_cal_per_cm2": 0.297, "arc_flash_boundary_mm": 226.4, "arc_current_ka": 25.0})
@patch("scripts.test_staging_e2e_capabilities.probe_unauthenticated_chat", return_value=401)
@patch("scripts.test_staging_e2e_capabilities.probe_public_version", return_value="ee64fba9d342e2f0bd22cab82f0146727309cee9")
@patch("scripts.test_staging_e2e_capabilities.probe_public_ready", return_value={"status": "ready"})
@patch("scripts.test_staging_e2e_capabilities.probe_public_health", return_value={"status": "ok"})
def test_buffered_sse_response_raises_assertion_error(m_live, m_ready, m_ver, m_unauth, m_study, m_sse):
    """Verify that a buffered (non-incremental) stream causes run_full_capability_suite to fail."""
    args = argparse.Namespace(
        url="https://fake-staging-worker.workers.dev",
        sha="ee64fba9d342e2f0bd22cab82f0146727309cee9",
        api_key="etap_staging_sec_test",
        email="",
        password="",
        token="",
        llm_key="",
        llm_provider="openai",
        require_login=False,
    )

    with pytest.raises(AssertionError, match="SSE acceptance test defect detected: stream was BUFFERED"):
        run_full_capability_suite(args)


@patch("scripts.test_staging_e2e_capabilities.probe_authenticated_sse", return_value=(True, [0.0, 0.15, 0.35, 0.52], "event: token\ndata: test\n\nevent: done\n\n"))
@patch("scripts.test_staging_e2e_capabilities.probe_engineering_study", return_value={"incident_energy_cal_per_cm2": 0.297, "arc_flash_boundary_mm": 226.4, "arc_current_ka": 25.0})
@patch("scripts.test_staging_e2e_capabilities.probe_unauthenticated_chat", return_value=401)
@patch("scripts.test_staging_e2e_capabilities.probe_public_version", return_value="ee64fba9d342e2f0bd22cab82f0146727309cee9")
@patch("scripts.test_staging_e2e_capabilities.probe_public_ready", return_value={"status": "ready"})
@patch("scripts.test_staging_e2e_capabilities.probe_public_health", return_value={"status": "ok"})
def test_incremental_sse_response_passes(m_live, m_ready, m_ver, m_unauth, m_study, m_sse):
    """Verify that an incremental stream succeeds and returns complete capability metrics."""
    args = argparse.Namespace(
        url="https://fake-staging-worker.workers.dev",
        sha="ee64fba9d342e2f0bd22cab82f0146727309cee9",
        api_key="etap_staging_sec_test",
        email="",
        password="",
        token="",
        llm_key="",
        llm_provider="openai",
        require_login=False,
    )

    result = run_full_capability_suite(args)
    assert result["sse_incremental"] is True
    assert result["sse_chunks"] == 4
    assert result["study_success"] is True


@patch("scripts.test_staging_e2e_capabilities.probe_engineering_study", return_value={"incident_energy_cal_per_cm2": 0.297, "arc_flash_boundary_mm": 226.4, "arc_current_ka": 25.0})
@patch("scripts.test_staging_e2e_capabilities.probe_unauthenticated_chat", return_value=401)
@patch("scripts.test_staging_e2e_capabilities.probe_public_version", return_value="ee64fba9d342e2f0bd22cab82f0146727309cee9")
@patch("scripts.test_staging_e2e_capabilities.probe_public_ready", return_value={"status": "ready"})
@patch("scripts.test_staging_e2e_capabilities.probe_public_health", return_value={"status": "ok"})
def test_require_login_fails_when_unauthenticated(m_live, m_ready, m_ver, m_unauth, m_study):
    """Verify that require_login=True raises AssertionError when no credentials are provided."""
    args = argparse.Namespace(
        url="https://fake-staging-worker.workers.dev",
        sha="ee64fba9d342e2f0bd22cab82f0146727309cee9",
        api_key="etap_staging_sec_test",
        email="",
        password="",
        token="",
        llm_key="",
        llm_provider="openai",
        require_login=True,
    )

    with pytest.raises(AssertionError, match="User login verification is mandatory"):
        run_full_capability_suite(args)
