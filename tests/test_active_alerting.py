"""
tests/test_active_alerting.py — Unit tests for FIX-26 Active Alerting Service.

Verifies:
1. trigger_alert dispatches on critical infrastructure events.
2. Debounce suppresses rapid-fire alerts of the same type (anti-fatigue).
3. Alerts are re-enabled after cooldown period expires.
4. /healthz integration dispatches an alert when database is unhealthy.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.alerting_service import AlertingService, AlertSeverity


@pytest.mark.asyncio
async def test_alerting_service_dispatch_and_debounce():
    """Verify alerting service dispatches and applies debounce cooldown."""
    service = AlertingService(webhook_url=None, debounce_seconds=10.0)

    # 1. First alert should be dispatched
    t0 = 1000.0
    with patch("time.time", return_value=t0):
        dispatched1 = await service.trigger_alert(
            alert_type="db_down",
            message="PostgreSQL connection refused",
            severity=AlertSeverity.CRITICAL,
        )
        assert dispatched1 is True

    # 2. Second alert immediately after should be suppressed by debouncing
    with patch("time.time", return_value=t0 + 2.0):
        dispatched2 = await service.trigger_alert(
            alert_type="db_down",
            message="PostgreSQL connection refused again",
            severity=AlertSeverity.CRITICAL,
        )
        assert dispatched2 is False

    # 3. Different alert type should NOT be blocked by db_down cooldown
    with patch("time.time", return_value=t0 + 3.0):
        dispatched_other = await service.trigger_alert(
            alert_type="redis_timeout",
            message="Redis ping timed out",
            severity=AlertSeverity.WARNING,
        )
        assert dispatched_other is True

    # 4. After debounce period (10 seconds), db_down should dispatch again
    with patch("time.time", return_value=t0 + 11.0):
        dispatched3 = await service.trigger_alert(
            alert_type="db_down",
            message="PostgreSQL connection still down",
            severity=AlertSeverity.CRITICAL,
        )
        assert dispatched3 is True


@pytest.mark.asyncio
async def test_healthz_triggers_alert_on_unhealthy_db(monkeypatch):
    """Verify /healthz endpoint triggers an alert when check_db_health returns unhealthy."""
    import importlib.util
    from pathlib import Path

    app_path = Path(__file__).resolve().parent.parent / "hf-space" / "app.py"
    spec = importlib.util.spec_from_file_location("hf_space_app", str(app_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app = mod.app

    from services.alerting_service import get_alerting_service

    # Mock db_health to return unhealthy
    async def mock_check_db_health():
        return {"status": "unhealthy", "backend": "postgresql"}

    monkeypatch.setattr("api.database.check_db_health", mock_check_db_health)

    alert_service = get_alerting_service()
    mock_trigger = AsyncMock(return_value=True)
    monkeypatch.setattr(alert_service, "trigger_alert", mock_trigger)

    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert mock_trigger.await_count >= 1
    call_args = mock_trigger.await_args
    assert call_args.kwargs.get("alert_type") == "database_unhealthy"
    assert call_args.kwargs.get("severity") == "CRITICAL"
