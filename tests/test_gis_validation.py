"""
Tests for GIS validation modules — TopologyValidator, CRSValidator, ADMSGraphModel.

Note: gis_integration has Python 3.8 type hint compatibility issues in some
providers. Tests are skipped if the required imports are not available.
"""
import pytest

# Attempt import — gis_integration may fail on Python 3.8 due to X | None syntax
try:
    from gis_integration.models import ADMSAsset, ADMSAssetType
    from gis_validation.crs_validator import (
        CRSIssue,
        validate_crs_consistency,
        validate_normalization_applied,
    )
    from gis_validation.topology_validator import (
        ADMSGraphModel,
        TopologyIssue,
        validate_adms_topology,
    )

    HAS_GIS_DEPS = True
except (ImportError, TypeError):
    HAS_GIS_DEPS = False


def _make_asset(
    asset_id: str,
    asset_type=None,
    geometry=None,
    metadata=None,
):
    """Helper to create test assets."""
    if asset_type is None:
        asset_type = ADMSAssetType.SUBSTATION
    if geometry is None:
        geometry = {"type": "Point", "coordinates": [31.0, 30.0]}
    if metadata is None:
        metadata = {}
    return ADMSAsset(
        asset_id=asset_id,
        asset_type=asset_type,
        geometry=geometry,
        metadata=metadata,
    )


pytestmark = pytest.mark.skipif(
    not HAS_GIS_DEPS,
    reason="gis_integration requires Python 3.9+ or psycopg2",
)


# ===========================================================================
# ADMSGraphModel
# ===========================================================================

class TestADMSGraphModel:
    def test_empty_assets(self):
        model = ADMSGraphModel([])
        assert len(model.nodes) == 0
        assert len(model.edges) == 0

    def test_single_substation(self):
        assets = [_make_asset("S1")]
        model = ADMSGraphModel(assets)
        assert "S1" in model.nodes
        assert len(model.edges["S1"]) == 0

    def test_substation_and_line_connected(self):
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1", ADMSAssetType.LINE,
                geometry={
                    "type": "LineString",
                    "coordinates": [[31.0, 30.0], [31.1, 30.1]],
                },
            ),
        ]
        model = ADMSGraphModel(assets)
        assert "S1" in model.edges["L1"]
        assert "L1" in model.edges["S1"]

    def test_line_no_connection(self):
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1", ADMSAssetType.LINE,
                geometry={
                    "type": "LineString",
                    "coordinates": [[32.0, 31.0], [33.0, 32.0]],
                },
            ),
        ]
        model = ADMSGraphModel(assets)
        assert len(model.edges["L1"]) == 0
        assert len(model.edges["S1"]) == 0

    def test_multiple_lines_one_substation(self):
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1", ADMSAssetType.LINE,
                geometry={
                    "type": "LineString",
                    "coordinates": [[31.0, 30.0], [31.1, 30.1]],
                },
            ),
            _make_asset(
                "L2", ADMSAssetType.LINE,
                geometry={
                    "type": "LineString",
                    "coordinates": [[31.0, 30.0], [31.2, 29.9]],
                },
            ),
        ]
        model = ADMSGraphModel(assets)
        assert len(model.edges["S1"]) == 2

    def test_find_disconnected_single_component(self):
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1", ADMSAssetType.LINE,
                geometry={
                    "type": "LineString",
                    "coordinates": [[31.0, 30.0], [31.1, 30.1]],
                },
            ),
        ]
        model = ADMSGraphModel(assets)
        comps = model.find_disconnected_components()
        assert len(comps) == 1

    def test_find_disconnected_two_components(self):
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1", ADMSAssetType.LINE,
                geometry={
                    "type": "LineString",
                    "coordinates": [[31.0, 30.0], [31.1, 30.1]],
                },
            ),
            _make_asset("S2", geometry={"type": "Point", "coordinates": [35.0, 35.0]}),
        ]
        model = ADMSGraphModel(assets)
        comps = model.find_disconnected_components()
        assert len(comps) == 2

    def test_extract_endpoints_linestring(self):
        geometry = {"type": "LineString", "coordinates": [[1.0, 2.0], [3.0, 4.0]]}
        result = ADMSGraphModel._extract_endpoints(geometry)
        assert result is not None
        a, b = result
        assert a == (1.0, 2.0)
        assert b == (3.0, 4.0)

    def test_extract_endpoints_point(self):
        geometry = {"type": "Point", "coordinates": [1.0, 2.0]}
        result = ADMSGraphModel._extract_endpoints(geometry)
        assert result is None

    def test_extract_endpoints_empty_coords(self):
        geometry = {"type": "LineString", "coordinates": []}
        result = ADMSGraphModel._extract_endpoints(geometry)
        assert result is None

    def test_extract_endpoints_single_coord(self):
        geometry = {"type": "LineString", "coordinates": [[1.0, 2.0]]}
        result = ADMSGraphModel._extract_endpoints(geometry)
        assert result is None

    def test_feeder_connects_like_line(self):
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "F1", ADMSAssetType.FEEDER,
                geometry={
                    "type": "LineString",
                    "coordinates": [[31.0, 30.0], [31.1, 30.1]],
                },
            ),
        ]
        model = ADMSGraphModel(assets)
        assert "F1" in model.edges["S1"]


# ===========================================================================
# validate_adms_topology
# ===========================================================================

class TestValidateADMSTopology:
    def test_empty_assets(self):
        ok, issues = validate_adms_topology([])
        assert ok is False
        assert len(issues) == 1
        assert issues[0].issue_type == "empty_graph"

    def test_isolated_substation_detected(self):
        assets = [_make_asset("S1")]
        ok, issues = validate_adms_topology(assets)
        assert ok is False
        assert issues[0].issue_type == "isolated_substations"

    def test_valid_line_connected_to_substation(self):
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset(
                "L1", ADMSAssetType.LINE,
                geometry={
                    "type": "LineString",
                    "coordinates": [[31.0, 30.0], [31.1, 30.1]],
                },
            ),
        ]
        ok, issues = validate_adms_topology(assets)
        assert ok is True

    def test_disconnected_components_detected(self):
        assets = [
            _make_asset("S1", geometry={"type": "Point", "coordinates": [31.0, 30.0]}),
            _make_asset("S2", geometry={"type": "Point", "coordinates": [35.0, 35.0]}),
        ]
        ok, issues = validate_adms_topology(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "disconnected_components" in types

    def test_dangling_line_detected(self):
        assets = [
            _make_asset(
                "L1", ADMSAssetType.LINE,
                geometry={
                    "type": "LineString",
                    "coordinates": [[32.0, 31.0], [33.0, 32.0]],
                },
            ),
        ]
        ok, issues = validate_adms_topology(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "dangling_lines" in types


# ===========================================================================
# CRS Validator
# ===========================================================================

class TestCRSValidator:
    def test_empty_assets(self):
        ok, issues = validate_crs_consistency([])
        assert ok is False
        assert issues[0].issue_type == "empty_assets"

    def test_single_asset_with_crs(self):
        assets = [_make_asset("S1", metadata={"source_crs": "EPSG:4326"})]
        ok, issues = validate_crs_consistency(assets)
        assert ok is True

    def test_missing_crs(self):
        assets = [_make_asset("S1", metadata={})]
        ok, issues = validate_crs_consistency(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "missing_crs_metadata" in types

    def test_mixed_crs(self):
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={"source_crs": "EPSG:3857"}),
        ]
        ok, issues = validate_crs_consistency(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "mixed_crs_contamination" in types

    def test_same_crs_is_valid(self):
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={"source_crs": "EPSG:4326"}),
        ]
        ok, issues = validate_crs_consistency(assets)
        assert ok is True

    def test_crs_case_insensitive(self):
        assets = [
            _make_asset("S1", metadata={"source_crs": "epsg:4326"}),
        ]
        ok, issues = validate_crs_consistency(assets)
        assert ok is True

    def test_missing_and_present_crs(self):
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={}),
        ]
        ok, issues = validate_crs_consistency(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "missing_crs_metadata" in types


class TestNormalizationApplied:
    def test_all_normalized(self):
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={"source_crs": "EPSG:3857"}),
        ]
        ok, issues = validate_normalization_applied(assets)
        assert ok is True

    def test_some_not_normalized(self):
        assets = [
            _make_asset("S1", metadata={"source_crs": "EPSG:4326"}),
            _make_asset("S2", metadata={}),
        ]
        ok, issues = validate_normalization_applied(assets)
        assert ok is False
        types = [i.issue_type for i in issues]
        assert "normalization_not_applied" in types

    def test_empty_assets(self):
        ok, issues = validate_normalization_applied([])
        assert ok is False
        assert issues[0].issue_type == "empty_assets"

    def test_no_crs_field(self):
        assets = [
            _make_asset("S1", metadata={"other_field": "value"}),
        ]
        ok, issues = validate_normalization_applied(assets)
        assert ok is False


# ===========================================================================
# Dataclass tests (no import guard needed)
# ===========================================================================

class TestTopologyIssueDataclass:
    def test_create(self):
        issue = TopologyIssue(
            issue_type="test",
            affected_assets=["A1", "A2"],
            details={"key": "value"},
        )
        assert issue.issue_type == "test"
        assert "A1" in issue.affected_assets
        assert issue.details["key"] == "value"


class TestCRSIssueDataclass:
    def test_create(self):
        issue = CRSIssue(
            issue_type="test",
            affected_assets=["A1"],
            details={"reason": "test reason"},
        )
        assert issue.issue_type == "test"
        assert issue.details["reason"] == "test reason"
