"""tests/test_orchestrator_b1_b2.py — Unit tests for B1 (report failure status) and B2 (bus index lookup)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agents.orchestrator import (
    AgentStatus,
    EngineeringTask,
    ReportGenerationAgent,
    ShortCircuitAgent,
    StudyType,
)


@pytest.mark.asyncio
async def test_report_agent_fails_when_export_returns_none():
    agent = ReportGenerationAgent()
    task = EngineeringTask(
        task_id="test-rep-1",
        description="Generate report",
        study_types=[],
        parameters={"format": "pdf", "results": []},
    )

    with patch.object(agent, "_export_pdf", return_value=None):
        result = await agent.execute(task)
        assert result.status == AgentStatus.FAILED
        assert result.data.get("report_generated") is False
        assert result.data.get("file_path") is None
        assert any("Failed to generate PDF report" in err for err in result.validation_errors)


@pytest.mark.asyncio
async def test_report_agent_succeeds_when_export_returns_path(tmp_path):
    agent = ReportGenerationAgent()
    fake_path = str(tmp_path / "report.pdf")
    task = EngineeringTask(
        task_id="test-rep-2",
        description="Generate report",
        study_types=[],
        parameters={"format": "pdf", "results": []},
    )

    with patch.object(agent, "_export_pdf", return_value=fake_path):
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data.get("report_generated") is True
        assert result.data.get("file_path") == fake_path
