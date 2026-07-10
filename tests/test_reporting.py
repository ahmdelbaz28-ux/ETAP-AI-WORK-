"""
Tests for reporting module — ReportSection, ReportMetadata, ChartGenerator, TableGenerator.
"""
from typing import Optional, Union

import os
import tempfile
from datetime import datetime, timezone

import pytest

from reporting.advanced_reports import (
    ChartGenerator,
    PDFReportGenerator,
    ReportGenerationAgent,
    ReportMetadata,
    ReportSection,
    TableGenerator,
)

UTC = timezone.utc  # noqa: UP017 — datetime.UTC requires Python 3.11+


class TestReportSection:
    def test_defaults(self):
        s = ReportSection(title="Test", content="Content", order=1)
        assert s.title == "Test"
        assert s.content == "Content"
        assert s.order == 1
        assert s.include_charts is False
        assert s.include_tables is False
        assert s.data == {}

    def test_with_charts_and_tables(self):
        s = ReportSection(
            title="Load Flow",
            content="Results",
            order=2,
            include_charts=True,
            include_tables=True,
            data={"chart_path": "/tmp/chart.png", "table_data": [["a", "b"]]},  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        )
        assert s.include_charts is True
        assert s.include_tables is True
        assert s.data["chart_path"] == "/tmp/chart.png"  # NOSONAR — S5443: /tmp use is intentional & permission-hardened

    def test_ordering(self):
        s1 = ReportSection(title="B", content="", order=2)
        s2 = ReportSection(title="A", content="", order=1)
        sections = sorted([s1, s2], key=lambda s: s.order)
        assert sections[0].title == "A"
        assert sections[1].title == "B"

    def test_empty_data(self):
        s = ReportSection(title="Empty", content="", order=3)
        assert len(s.data) == 0


class TestReportMetadata:
    def test_defaults(self):
        m = ReportMetadata(report_id="RPT_001", title="Test", prepared_by="Engineer")
        assert m.report_id == "RPT_001"
        assert m.title == "Test"
        assert m.prepared_by == "Engineer"
        assert m.company_name == "Engineering Consulting Firm"
        assert m.confidentiality == "Confidential"
        assert m.revision == "1.0"
        assert m.language == "en"

    def test_all_fields(self):
        m = ReportMetadata(
            report_id="RPT_002",
            title="Full Report",
            prepared_by="Alice",
            reviewed_by="Bob",
            approved_by="Charlie",
            company_name="TestCo",
            project_name="Project X",
            client_name="Client Y",
            report_date=datetime(2025, 1, 15, tzinfo=UTC),
            confidentiality="Public",
            revision="2.1",
            language="fr",
        )
        assert m.reviewed_by == "Bob"
        assert m.approved_by == "Charlie"
        assert m.project_name == "Project X"
        assert m.client_name == "Client Y"
        assert m.report_date.year == 2025
        assert m.revision == "2.1"

    def test_date_default_is_utc(self):
        m = ReportMetadata(report_id="ID", title="T", prepared_by="P")
        assert m.report_date.tzinfo == UTC


class TestChartGenerator:
    def setup_method(self):
        self.gen = ChartGenerator()

    def test_voltage_profile_chart_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus_data = {
                "B1": {"voltage_magnitude_pu": 1.01},
                "B2": {"voltage_magnitude_pu": 0.97},
                "B3": {"voltage_magnitude_pu": 1.03},
            }
            path = self.gen.generate_voltage_profile_chart(bus_data, tmp)
            assert os.path.exists(path)
            assert path.endswith(".png")

    def test_voltage_chart_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.gen.generate_voltage_profile_chart({}, tmp)
            # matplotlib creates an empty plot (valid PNG) with Agg backend
            assert path != ""
            assert os.path.exists(path)

    def test_fault_current_bar_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            fault_data = {
                "B1": {"three_phase": {"fault_current": complex(5000, 0)}},
                "B2": {"three_phase": {"fault_current": complex(8000, 100)}},
            }
            path = self.gen.generate_fault_current_bar_chart(fault_data, tmp)
            assert os.path.exists(path)

    def test_fault_chart_no_three_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            fault_data = {"B1": {"line_to_ground": {"fault_current": complex(3000, 0)}}}
            path = self.gen.generate_fault_current_bar_chart(fault_data, tmp)
            assert os.path.exists(path)

    def test_fault_chart_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.gen.generate_fault_current_bar_chart({}, tmp)
            # matplotlib creates an empty plot (valid PNG) with Agg backend
            assert path != ""
            assert os.path.exists(path)

    def test_harmonic_spectrum_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            harm_data = {
                3: {"magnitude": 0.05},
                5: {"magnitude": 0.08},
                7: {"magnitude": 0.03},
            }
            path = self.gen.generate_harmonic_spectrum_chart(harm_data, tmp)
            assert os.path.exists(path)

    def test_harmonic_spectrum_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.gen.generate_harmonic_spectrum_chart({}, tmp)
            # matplotlib creates an empty plot (valid PNG) with Agg backend
            assert path != ""
            assert os.path.exists(path)


class TestTableGenerator:
    def setup_method(self):
        self.gen = TableGenerator()

    def test_load_flow_table(self):
        bus_data = {
            "B1": {
                "voltage_magnitude_pu": 1.01,
                "voltage_angle_deg": -2.0,
                "active_power_mw": 50,
                "reactive_power_mvar": 10,
            },
            "B2": {
                "voltage_magnitude_pu": 0.94,
                "voltage_angle_deg": -3.5,
                "active_power_mw": 30,
                "reactive_power_mvar": 15,
            },
        }
        table = self.gen.generate_load_flow_table(bus_data)
        assert "LOAD FLOW RESULTS" in table
        assert "B1" in table
        assert "B2" in table
        assert "OK" in table
        assert "UNDER" in table

    def test_load_flow_table_over_voltage(self):
        bus_data = {
            "B1": {
                "voltage_magnitude_pu": 1.06,
                "voltage_angle_deg": 0.0,
                "active_power_mw": 0,
                "reactive_power_mvar": 0,
            },
        }
        table = self.gen.generate_load_flow_table(bus_data)
        assert "OVER" in table

    def test_load_flow_table_empty(self):
        table = self.gen.generate_load_flow_table({})
        assert "LOAD FLOW RESULTS" in table

    def test_fault_current_table(self):
        fault_data = {
            "B1": {
                "three_phase": {"fault_current": complex(5000, 0)},
                "line_to_ground": {"fault_current": complex(4000, 0)},
                "line_to_line": {"fault_current_b": complex(3000, 0)},
                "double_line_to_ground": {"fault_current_b": complex(3500, 0)},
            }
        }
        table = self.gen.generate_fault_current_table(fault_data)
        assert "SHORT CIRCUIT" in table
        assert "B1" in table
        assert "5000.00" in table

    def test_fault_table_empty(self):
        table = self.gen.generate_fault_current_table({})
        assert "SHORT CIRCUIT" in table

    def test_compliance_table_pass(self):
        results = [
            {
                "standard": "IEEE 519",
                "parameter": "THD",
                "value": 2.5,
                "limit": 5.0,
                "compliant": True,
            },
        ]
        table = self.gen.generate_compliance_table(results)
        assert "COMPLIANCE" in table
        assert "PASS" in table

    def test_compliance_table_fail(self):
        results = [
            {
                "standard": "IEEE 519",
                "parameter": "THD",
                "value": 8.0,
                "limit": 5.0,
                "compliant": False,
            },
        ]
        table = self.gen.generate_compliance_table(results)
        assert "FAIL" in table

    def test_compliance_table_empty(self):
        table = self.gen.generate_compliance_table([])
        assert "COMPLIANCE" in table


class TestPDFReportGenerator:
    def test_fallback_pdf(self):
        try:
            gen = PDFReportGenerator()
            meta = ReportMetadata(report_id="TEST_001", title="Test", prepared_by="Engineer")
            sections = [
                ReportSection(title="Section 1", content="Content 1", order=1),
            ]
            with tempfile.TemporaryDirectory() as tmp:
                path = gen.generate_report(meta, sections, tmp)
                # Should produce a .txt file as fallback (reportlab may or may not be installed)
                assert os.path.exists(path)
        except TypeError as e:
            if "usedforsecurity" in str(e):
                pytest.skip(f"Python 3.8 OpenSSL compatibility issue: {e}")
            raise


class TestReportGenerationAgent:
    def test_generate_executive_summary_no_data(self):
        agent = ReportGenerationAgent()
        summary = agent._generate_executive_summary({})
        assert "Key Findings" in summary
        assert "Load Flow" not in summary

    def test_generate_executive_summary_with_lf(self):
        agent = ReportGenerationAgent()
        results = {"load_flow": {"converged": True}}
        summary = agent._generate_executive_summary(results)
        assert "Converged successfully" in summary

    def test_generate_executive_summary_lf_not_converged(self):
        agent = ReportGenerationAgent()
        results = {"load_flow": {"converged": False}}
        summary = agent._generate_executive_summary(results)
        assert "Did not converge" in summary

    def test_generate_executive_summary_with_sc(self):
        agent = ReportGenerationAgent()
        results = {"short_circuit": {}}
        summary = agent._generate_executive_summary(results)
        assert "IEC 60909" in summary

    def test_generate_executive_summary_with_harmonic(self):
        agent = ReportGenerationAgent()
        results = {"harmonic": {"violations": [1, 2, 3]}}
        summary = agent._generate_executive_summary(results)
        assert "3" in summary

    def test_generate_executive_summary_with_opf(self):
        agent = ReportGenerationAgent()
        results = {"opf": {"success": True, "objective_value": 1250.50}}
        summary = agent._generate_executive_summary(results)
        assert "$1,250.50" in summary

    def test_convert_to_table_data(self):
        agent = ReportGenerationAgent()
        text = '" | A, B, C, |\n, 1 | 2, 3 |"'
        rows = agent._convert_to_table_data(text)
        assert len(rows) >= 1
        assert "A" in rows[0]

    def test_empty_sections_when_no_match(self):
        agent = ReportGenerationAgent()
        sections = agent._compile_sections({}, "/tmp")  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        assert len(sections) >= 2  # executive summary + system description