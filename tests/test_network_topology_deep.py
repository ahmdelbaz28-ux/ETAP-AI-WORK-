"""
Comprehensive Unit & Integration Test Suite for deep NetworkTopology module.
"""

import pytest

from core.network_topology import (
    BranchEdge,
    BusNode,
    FeederTree,
    IsolationZone,
    NetworkTopology,
)


@pytest.fixture
def topology():
    """Create a fresh isolated NetworkTopology instance for each test."""
    top = NetworkTopology()
    top.clear()
    return top


class TestNetworkTopologyBasics:
    """Test fundamental node and edge graph operations."""

    def test_add_bus_object_and_dict(self, topology):
        bus1 = topology.add_bus(BusNode(id="BUS_1", voltage_kv=33.0, bus_type="slack"))
        bus2 = topology.add_bus({"id": "BUS_2", "voltage_kv": 11.0, "bus_type": "load"})

        assert bus1.id == "BUS_1"
        assert bus1.voltage_kv == 33.0
        assert bus2.id == "BUS_2"
        assert bus2.voltage_kv == 11.0

        all_buses = topology.get_all_buses()
        assert len(all_buses) == 2
        assert topology.get_bus("BUS_1") is not None
        assert topology.get_bus("NON_EXISTENT") is None

    def test_add_branch_object_and_dict(self, topology):
        topology.add_bus(BusNode(id="BUS_A", voltage_kv=132.0))
        topology.add_bus(BusNode(id="BUS_B", voltage_kv=132.0))

        branch1 = topology.add_branch(
            BranchEdge(
                id="LINE_AB", from_bus="BUS_A", to_bus="BUS_B", impedance=0.02, rating_mva=150.0
            )
        )
        assert branch1.id == "LINE_AB"
        assert len(topology.get_all_branches()) == 1

        adjacent_a = topology.get_adjacent_buses("BUS_A")
        assert "BUS_B" in adjacent_a
        adjacent_b = topology.get_adjacent_buses("BUS_B")
        assert "BUS_A" in adjacent_b


class TestNetworkTopologyAlgorithms:
    """Test pathfinding, isolation zone, and feeder tree algorithms."""

    def test_shortest_path_simple(self, topology):
        topology.add_branch(BranchEdge(id="L1", from_bus="B1", to_bus="B2", impedance=1.0))
        topology.add_branch(BranchEdge(id="L2", from_bus="B2", to_bus="B3", impedance=1.0))
        topology.add_branch(BranchEdge(id="L3", from_bus="B1", to_bus="B3", impedance=5.0))

        # Path should choose B1 -> B2 -> B3 (total weight 2.0 vs direct 5.0)
        path = topology.find_shortest_path("B1", "B3")
        assert path == ["B1", "B2", "B3"]

    def test_shortest_path_same_node(self, topology):
        topology.add_bus(BusNode(id="B1", voltage_kv=11.0))
        assert topology.find_shortest_path("B1", "B1") == ["B1"]

    def test_shortest_path_disconnected(self, topology):
        topology.add_bus(BusNode(id="ISOLATED_1"))
        topology.add_bus(BusNode(id="ISOLATED_2"))
        assert topology.find_shortest_path("ISOLATED_1", "ISOLATED_2") is None

    def test_find_isolation_zone(self, topology):
        topology.add_branch(
            BranchEdge(id="BR_1", from_bus="BUS_FAULT", to_bus="BUS_NORTH", rating_mva=50.0)
        )
        topology.add_branch(
            BranchEdge(id="BR_2", from_bus="BUS_FAULT", to_bus="BUS_SOUTH", rating_mva=50.0)
        )

        zone = topology.find_isolation_zone("BUS_FAULT")
        assert isinstance(zone, IsolationZone)
        assert zone.target_bus == "BUS_FAULT"
        assert "BR_1" in zone.boundary_branches
        assert "BR_2" in zone.boundary_branches
        assert zone.isolated_capacity_mva == 100.0
        assert zone.is_fully_isolated is True

    def test_trace_feeders(self, topology):
        # Radial topology: SUB -> B1 -> B2
        topology.add_branch(BranchEdge(id="CB1", from_bus="SUB_1", to_bus="B1"))
        topology.add_branch(BranchEdge(id="CB2", from_bus="B1", to_bus="B2"))
        topology.add_branch(BranchEdge(id="CB3", from_bus="SUB_1", to_bus="B3"))

        tree = topology.trace_feeders("SUB_1")
        assert isinstance(tree, FeederTree)
        assert tree.root_substation == "SUB_1"
        assert set(tree.buses) == {"SUB_1", "B1", "B2", "B3"}
        assert "B2" in tree.leaf_buses
        assert "B3" in tree.leaf_buses
        assert tree.max_depth == 2
