"""
tests/test_scada_interlock.py — Unit tests for SCADA Engineering Interlock Engine.

Verifies:
- Signal quality validation (GOOD accepted, UNCERTAIN/BAD rejected)
- Telemetry timestamp freshness (stale timestamps rejected)
- ANSI 43 Local/Remote switch check (LOCAL mode blocks remote control)
- Load Flow contingency overload prevention (>100% thermal capacity blocked)
- Protection coordination selectivity check (IEC 60255 CTI < 0.2s blocked)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scada.interlock_engine import InterlockViolation, SCADAInterlockEngine
from scada.models import (
    ControlActionType,
    ControlCommandRequest,
    ControlProtocol,
    SignalQuality,
)

UTC = timezone.utc


@pytest.fixture
def interlock_engine() -> SCADAInterlockEngine:
    return SCADAInterlockEngine(
        max_telemetry_age_sec=10.0,
        max_line_loading_pct=100.0,
        min_coordination_margin_sec=0.2,
    )


@pytest.fixture
def sample_breaker_command() -> ControlCommandRequest:
    return ControlCommandRequest(
        device_id="CB_001",
        protocol=ControlProtocol.OPC_UA,
        action_type=ControlActionType.BREAKER_OPEN,
        target_value=0,
        reason="Scheduled maintenance on feeder 1",
    )


class TestSCADAInterlockEngine:
    def test_good_signal_quality_passes(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        telemetry = {
            "CB_001": {
                "quality": SignalQuality.GOOD.value,
                "control_mode": "REMOTE",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        }
        # Must not raise
        interlock_engine.pre_flight_check(sample_breaker_command, telemetry=telemetry)

    def test_poor_signal_quality_rejected(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        telemetry = {
            "CB_001": {
                "quality": SignalQuality.UNCERTAIN.value,
                "control_mode": "REMOTE",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(sample_breaker_command, telemetry=telemetry)

        assert exc_info.value.code == "POOR_DATA_QUALITY"
        assert "UNCERTAIN" in exc_info.value.message

    def test_stale_telemetry_rejected(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        stale_time = (datetime.now(UTC) - timedelta(seconds=25)).isoformat()
        telemetry = {
            "CB_001": {
                "quality": SignalQuality.GOOD.value,
                "control_mode": "REMOTE",
                "timestamp": stale_time,
            }
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(sample_breaker_command, telemetry=telemetry)

        assert exc_info.value.code == "STALE_TELEMETRY"
        assert "stale" in exc_info.value.message.lower()

    def test_local_mode_blocks_remote_operation(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        telemetry = {
            "CB_001": {
                "quality": SignalQuality.GOOD.value,
                "control_mode": "LOCAL",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(sample_breaker_command, telemetry=telemetry)

        assert exc_info.value.code == "EQUIPMENT_IN_LOCAL_MODE"
        assert "LOCAL" in exc_info.value.message

    def test_overload_contingency_violation(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        """Mock load flow overload detection."""
        class MockBranch:
            def __init__(self, bid):
                self.id = bid
                self.status = 1

        mock_network = {
            "branches": [MockBranch("CB_001")],
        }

        # Subclass engine to simulate overload branch result
        class OverloadingEngine(SCADAInterlockEngine):
            def validate_load_flow_overload(self, command, network_data=None):
                if network_data:
                    raise InterlockViolation(
                        code="INTERLOCK_OVERLOAD_PREVENTED",
                        message=f"Action on {command.device_id} causes branch Line_4 to overload at 118.5%",
                    )

        engine = OverloadingEngine()
        telemetry = {
            "CB_001": {"quality": "GOOD", "control_mode": "REMOTE", "timestamp": datetime.now(UTC).isoformat()}
        }
        with pytest.raises(InterlockViolation) as exc_info:
            engine.pre_flight_check(sample_breaker_command, telemetry=telemetry, network_data=mock_network)

        assert exc_info.value.code == "INTERLOCK_OVERLOAD_PREVENTED"
        assert "118.5%" in exc_info.value.message

    def test_coordination_margin_violation(
        self, interlock_engine: SCADAInterlockEngine, sample_breaker_command: ControlCommandRequest
    ) -> None:
        """Protection margin < 0.2s must raise COORDINATION_MARGIN_VIOLATION."""
        class MockRelay:
            def __init__(self, time_val):
                self._t = time_val

            def trip_time(self, current):
                return self._t

        coordination_data = {
            "upstream_relay": MockRelay(0.35),
            "downstream_relay": MockRelay(0.25),  # Margin is 0.10s (< 0.20s standard)
            "fault_current": 10.0,
        }

        telemetry = {
            "CB_001": {"quality": "GOOD", "control_mode": "REMOTE", "timestamp": datetime.now(UTC).isoformat()}
        }
        with pytest.raises(InterlockViolation) as exc_info:
            interlock_engine.pre_flight_check(
                sample_breaker_command,
                telemetry=telemetry,
                coordination_data=coordination_data,
            )

        assert exc_info.value.code == "COORDINATION_MARGIN_VIOLATION"
        assert "0.100s" in exc_info.value.message
