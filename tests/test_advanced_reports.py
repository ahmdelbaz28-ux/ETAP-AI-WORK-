import pytest

from reporting.advanced_reports import ReportGenerationAgent, _validate_output_path


@pytest.mark.asyncio
async def test_generate_complete_report_path_traversal_blocked():
    agent = ReportGenerationAgent()
    with pytest.raises(ValueError, match="escapes reports directory"):
        await agent.generate_complete_report(
            analysis_results={},
            output_path="../../../tmp/evil",
        )


@pytest.mark.asyncio
async def test_generate_complete_report_valid_path():
    agent = ReportGenerationAgent()
    results = await agent.generate_complete_report(
        analysis_results={},
        formats=[],
        output_path="reports/output/normal",
    )
    assert isinstance(results, dict)


def test_validate_output_path_direct():
    with pytest.raises(ValueError, match="escapes reports directory"):
        _validate_output_path("../../../tmp/evil")

    safe_path = _validate_output_path("reports/output/normal")
    assert "normal" in safe_path
