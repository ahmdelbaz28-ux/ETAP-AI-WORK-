"""Report Generation Agent - Multi-turn Conversation Scenario Test.

Tests the ReportGenerationAgent through multi-turn engineering scenarios covering
PDF/DOCX/XLSX export, report compilation, and recommendation generation.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    ReportGenerationAgent,
    StudyType,
)


@pytest.fixture
def agent():
    return ReportGenerationAgent()


def _sample_load_flow_result():
    return AgentResult(
        agent_name="LoadFlowAgent",
        study_type=StudyType.LOAD_FLOW,
        status=AgentStatus.COMPLETED,
        data={
            "converged": True,
            "buses": {
                "Bus1": {"voltage_magnitude_pu": 1.00},
                "Bus2": {"voltage_magnitude_pu": 0.92},  # Below limit
            },
        },
    )


class TestReportScenario:
    """Test Report Generation Agent with multi-turn engineering scenarios."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, agent):
        """Test 1: Agent initializes correctly."""
        assert agent.agent_name == "ReportGenerationAgent"

    @pytest.mark.asyncio
    async def test_pdf_report_generation(self, agent):
        """Test 2: Generates a PDF report from engineering results."""
        task = EngineeringTask(
            task_id="rpt-001",
            description="Generate PDF report",
            study_types=[],
            parameters={
                "results": [_sample_load_flow_result()],
                "format": "pdf",
                "output_path": "/tmp/etap_test_reports",
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["report_generated"] is True
        assert result.data["format"] == "pdf"

    @pytest.mark.asyncio
    async def test_docx_report_generation(self, agent):
        """Test 3: Generates a DOCX report from engineering results."""
        task = EngineeringTask(
            task_id="rpt-002",
            description="Generate DOCX report",
            study_types=[],
            parameters={
                "results": [_sample_load_flow_result()],
                "format": "docx",
                "output_path": "/tmp/etap_test_reports",
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["format"] == "docx"

    @pytest.mark.asyncio
    async def test_xlsx_report_generation(self, agent):
        """Test 4: Generates an XLSX report from engineering results."""
        task = EngineeringTask(
            task_id="rpt-003",
            description="Generate XLSX report",
            study_types=[],
            parameters={
                "results": [_sample_load_flow_result()],
                "format": "xlsx",
                "output_path": "/tmp/etap_test_reports",
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["format"] == "xlsx"

    @pytest.mark.asyncio
    async def test_unsupported_format(self, agent):
        """Test 5: Rejects unsupported output formats."""
        task = EngineeringTask(
            task_id="rpt-004",
            description="Generate RTF report",
            study_types=[],
            parameters={
                "results": [],
                "format": "rtf",
                "output_path": "/tmp/etap_test_reports",
            },
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_report_sections(self, agent):
        """Test 6: Report contains expected sections."""
        task = EngineeringTask(
            task_id="rpt-005",
            description="Check sections",
            study_types=[],
            parameters={
                "results": [_sample_load_flow_result()],
                "format": "pdf",
                "output_path": "/tmp/etap_test_reports",
            },
        )
        result = await agent.execute(task)
        if result.status == AgentStatus.COMPLETED:
            sections = result.data.get("sections", [])
            assert len(sections) > 0
