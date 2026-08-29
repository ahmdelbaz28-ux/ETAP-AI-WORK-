"""
Network Topology Module for AhmedETAP
======================================
Provides a deep, domain-centric electrical graph seam for the AhmedETAP platform.

Architecture & Design:
----------------------
This module encapsulates all power system graph representation, path-finding,
isolation zone analysis, and feeder tracing behind a cohesive domain interface.

Under the seam:
- Transparently connects to **Neo4j Aura Enterprise Cloud** when configured and available.
- Maintains an in-memory **NetworkX** graph model for ultra-fast local computations,
  instant unit tests, and offline resilience.
- Ensures zero leakage of Cypher queries or database driver internals to callers.

Usage:
------
    from core.network_topology import network_topology, BusNode, BranchEdge

    # Add components
    network_topology.add_bus(BusNode(id="BUS_1", voltage_kv=13.8, bus_type="generator"))
    network_topology.add_bus(BusNode(id="BUS_2", voltage_kv=13.8, bus_type="load"))
    network_topology.add_branch(BranchEdge(id="LINE_1_2", from_bus="BUS_1", to_bus="BUS_2", impedance=0.05))

    # Perform domain operations
    path = network_topology.find_shortest_path("BUS_1", "BUS_2")
    zone = network_topology.find_isolation_zone("BUS_2")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import networkx as nx

    NETWORKX_AVAILABLE = True
except ImportError:
    nx = None  # type: ignore
    NETWORKX_AVAILABLE = False

from integrations.neo4j_integration import Neo4jClient, neo4j_client

logger = logging.getLogger(__name__)


# ─── Domain Data Structures ──────────────────────────────────────────────────


@dataclass
class BusNode:
    """Represents an electrical bus in the power system topology."""

    id: str
    voltage_kv: float = 13.8
    bus_type: str = "bus"  # "slack", "generator", "load", "substation", "bus"
    active_power_mw: float = 0.0
    reactive_power_mvar: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "voltage_kv": self.voltage_kv,
            "bus_type": self.bus_type,
            "active_power_mw": self.active_power_mw,
            "reactive_power_mvar": self.reactive_power_mvar,
            **self.metadata,
        }


@dataclass
class BranchEdge:
    """Represents a transmission line, cable, or transformer branch."""

    id: str
    from_bus: str
    to_bus: str
    impedance: float = 0.01  # p.u. or ohms
    resistance: float = 0.005
    reactance: float = 0.05
    rating_mva: float = 100.0
    status: str = "closed"  # "closed", "open", "tripped"
    branch_type: str = "line"  # "line", "transformer", "cable", "breaker"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_bus": self.from_bus,
            "to_bus": self.to_bus,
            "impedance": self.impedance,
            "resistance": self.resistance,
            "reactance": self.reactance,
            "rating_mva": self.rating_mva,
            "status": self.status,
            "branch_type": self.branch_type,
            **self.metadata,
        }


@dataclass
class IsolationZone:
    """Represents the protective boundary and isolated components around a fault."""

    target_bus: str
    isolated_buses: list[str]
    boundary_branches: list[str]
    isolated_capacity_mva: float = 0.0
    is_fully_isolated: bool = True


@dataclass
class FeederTree:
    """Represents a radial or meshed feeder tree traced from a substation."""

    root_substation: str
    buses: list[str]
    branches: list[str]
    leaf_buses: list[str]
    max_depth: int = 0


# ─── Deep Domain Module: NetworkTopology ──────────────────────────────────────


class NetworkTopology:
    """
    Deep domain module managing electrical grid graph topology.
    Encapsulates graph persistence, pathfinding, and zone isolation.
    """

    def __init__(self, neo4j: Optional[Neo4jClient] = None):
        self._neo4j = neo4j or neo4j_client
        self._buses: dict[str, BusNode] = {}
        self._branches: dict[str, BranchEdge] = {}

        # In-memory graph representation
        if NETWORKX_AVAILABLE:
            self._graph = nx.Graph()
        else:
            self._graph = None
            logger.warning(
                "networkx is not installed. Graph topology analysis will use simplified fallbacks."
            )

    @property
    def is_cloud_connected(self) -> bool:
        """Return True if Neo4j cloud graph is active and reachable."""
        return bool(
            self._neo4j
            and getattr(self._neo4j, "enabled", False)
            and getattr(self._neo4j, "driver", None)
        )

    def clear(self) -> None:
        """Clear all in-memory topology nodes and branches."""
        self._buses.clear()
        self._branches.clear()
        if self._graph is not None:
            self._graph.clear()

    def add_bus(self, bus: BusNode | dict[str, Any]) -> BusNode:
        """Add or update an electrical bus in the topology."""
        if isinstance(bus, dict):
            bus_obj = BusNode(
                id=str(bus.get("id", "")),
                voltage_kv=float(bus.get("voltage_kv", 13.8)),
                bus_type=str(bus.get("bus_type", bus.get("type", "bus"))),
                active_power_mw=float(bus.get("active_power_mw", 0.0)),
                reactive_power_mvar=float(bus.get("reactive_power_mvar", 0.0)),
            )
        else:
            bus_obj = bus

        self._buses[bus_obj.id] = bus_obj

        if self._graph is not None:
            self._graph.add_node(bus_obj.id, **bus_obj.to_dict())

        # Sync to Neo4j if connected
        if self.is_cloud_connected:
            try:
                query = """
                MERGE (b:Bus {id: $bus_id})
                SET b.voltage_kv = $voltage_kv, b.type = $bus_type,
                    b.active_power_mw = $mw, b.reactive_power_mvar = $mvar
                RETURN b
                """
                self._neo4j.execute_query(
                    query,
                    {
                        "bus_id": bus_obj.id,
                        "voltage_kv": bus_obj.voltage_kv,
                        "bus_type": bus_obj.bus_type,
                        "mw": bus_obj.active_power_mw,
                        "mvar": bus_obj.reactive_power_mvar,
                    },
                )
            except Exception as e:
                logger.debug("Neo4j bus sync error: %s", e)

        return bus_obj

    def add_branch(self, branch: BranchEdge | dict[str, Any]) -> BranchEdge:
        """Add or update a branch (transmission line, transformer, cable)."""
        if isinstance(branch, dict):
            branch_obj = BranchEdge(
                id=str(branch.get("id", "")),
                from_bus=str(branch.get("from_bus", "")),
                to_bus=str(branch.get("to_bus", "")),
                impedance=float(branch.get("impedance", 0.01)),
                rating_mva=float(branch.get("rating_mva", 100.0)),
                status=str(branch.get("status", "closed")),
                branch_type=str(branch.get("branch_type", "line")),
            )
        else:
            branch_obj = branch

        self._branches[branch_obj.id] = branch_obj

        # Ensure endpoints exist
        if branch_obj.from_bus not in self._buses:
            self.add_bus(BusNode(id=branch_obj.from_bus))
        if branch_obj.to_bus not in self._buses:
            self.add_bus(BusNode(id=branch_obj.to_bus))

        if self._graph is not None:
            self._graph.add_edge(
                branch_obj.from_bus,
                branch_obj.to_bus,
                weight=branch_obj.impedance,
                **branch_obj.to_dict(),
            )

        # Sync to Neo4j if connected
        if self.is_cloud_connected:
            try:
                query = """
                MATCH (from:Bus {id: $from_bus}), (to:Bus {id: $to_bus})
                MERGE (from)-[r:LINE {id: $branch_id}]->(to)
                SET r.impedance = $impedance, r.rating_mva = $rating, r.status = $status
                RETURN r
                """
                self._neo4j.execute_query(
                    query,
                    {
                        "branch_id": branch_obj.id,
                        "from_bus": branch_obj.from_bus,
                        "to_bus": branch_obj.to_bus,
                        "impedance": branch_obj.impedance,
                        "rating": branch_obj.rating_mva,
                        "status": branch_obj.status,
                    },
                )
            except Exception as e:
                logger.debug("Neo4j branch sync error: %s", e)

        return branch_obj

    def get_bus(self, bus_id: str) -> Optional[BusNode]:
        """Retrieve a bus by ID."""
        return self._buses.get(bus_id)

    def get_all_buses(self) -> list[BusNode]:
        """Return all registered buses."""
        return list(self._buses.values())

    def get_all_branches(self) -> list[BranchEdge]:
        """Return all registered branches."""
        return list(self._branches.values())

    def get_adjacent_buses(self, bus_id: str) -> list[str]:
        """Get all directly connected bus IDs."""
        if self._graph is not None and bus_id in self._graph:
            return list(self._graph.neighbors(bus_id))

        # Fallback manual scan
        neighbors = set()
        for b in self._branches.values():
            if b.status == "closed":
                if b.from_bus == bus_id:
                    neighbors.add(b.to_bus)
                elif b.to_bus == bus_id:
                    neighbors.add(b.from_bus)
        return list(neighbors)

    def _dijkstra_shortest_path(self, from_bus: str, to_bus: str) -> list[str] | None:
        """Pure-Python Dijkstra shortest path weighted by branch impedance."""
        import heapq

        adj: dict[str, list[tuple[str, float]]] = {}
        for b in self._branches.values():
            if b.status == "closed":
                u, v, w = b.from_bus, b.to_bus, max(float(b.impedance), 1e-9)
                adj.setdefault(u, []).append((v, w))
                adj.setdefault(v, []).append((u, w))

        if from_bus not in adj and from_bus not in self._buses:
            return None
        if to_bus not in adj and to_bus not in self._buses:
            return None

        dist: dict[str, float] = {from_bus: 0.0}
        prev: dict[str, Optional[str]] = {from_bus: None}
        pq = [(0.0, from_bus)]
        visited: set[str] = set()

        while pq:
            d, u = heapq.heappop(pq)
            if u in visited:
                continue
            visited.add(u)

            if u == to_bus:
                path: list[str] = []
                curr: Optional[str] = to_bus
                while curr is not None:
                    path.append(curr)
                    curr = prev[curr]
                return path[::-1]

            for v, w in adj.get(u, []):
                if d + w < dist.get(v, float("inf")):
                    dist[v] = d + w
                    prev[v] = u
                    heapq.heappush(pq, (dist[v], v))

        return None

    def find_shortest_path(self, from_bus: str, to_bus: str) -> list[str] | None:
        """
        Find the shortest electrical path between two buses.
        Handles same-node edge case natively ([bus_id]).
        """
        if from_bus == to_bus:
            return (
                [from_bus]
                if from_bus in self._buses or (self._graph and from_bus in self._graph)
                else None
            )

        # Try fast in-memory graph
        if self._graph is not None and from_bus in self._graph and to_bus in self._graph:
            try:
                # Calculate shortest path weighted by impedance
                return list(
                    nx.shortest_path(self._graph, source=from_bus, target=to_bus, weight="weight")
                )
            except nx.NetworkXNoPath:
                return None
            except Exception as e:
                logger.debug("NetworkX shortest path calculation error: %s", e)

        # Try pure-Python Dijkstra fallback
        dijkstra_path = self._dijkstra_shortest_path(from_bus, to_bus)
        if dijkstra_path is not None:
            return dijkstra_path

        # Try Neo4j if available
        if self.is_cloud_connected:
            try:
                query = """
                MATCH (from:Bus {id: $from_bus}), (to:Bus {id: $to_bus})
                MATCH path = shortestPath((from)-[*..20]-(to))
                RETURN [node IN nodes(path) | node.id] AS path
                """
                res = self._neo4j.execute_query(query, {"from_bus": from_bus, "to_bus": to_bus})
                data = res.get("data", [])
                if data and "path" in data[0]:
                    return data[0]["path"]
            except Exception as e:
                logger.debug("Neo4j shortest path error: %s", e)

        return None

    def find_isolation_zone(self, fault_bus: str) -> IsolationZone:
        """
        Determine the protection boundary and isolated buses surrounding a fault.
        """
        if fault_bus not in self._buses and (self._graph is None or fault_bus not in self._graph):
            return IsolationZone(
                target_bus=fault_bus,
                isolated_buses=[],
                boundary_branches=[],
                is_fully_isolated=False,
            )

        boundary_branches = []
        isolated_buses = [fault_bus]
        total_capacity = 0.0

        for branch in self._branches.values():
            if branch.from_bus == fault_bus or branch.to_bus == fault_bus:
                boundary_branches.append(branch.id)
                total_capacity += branch.rating_mva

        return IsolationZone(
            target_bus=fault_bus,
            isolated_buses=isolated_buses,
            boundary_branches=boundary_branches,
            isolated_capacity_mva=total_capacity,
            is_fully_isolated=len(boundary_branches) > 0,
        )

    def _get_branch_between(self, bus_a: str, bus_b: str) -> Optional[BranchEdge]:
        """Find the branch connecting two buses."""
        if self._graph is not None and bus_a in self._graph and bus_b in self._graph:
            edge_data = self._graph.get_edge_data(bus_a, bus_b)
            if edge_data and "id" in edge_data:
                return self._branches.get(edge_data["id"])

        for b in self._branches.values():
            if b.status == "closed":
                if (b.from_bus == bus_a and b.to_bus == bus_b) or (b.from_bus == bus_b and b.to_bus == bus_a):
                    return b
        return None

    def trace_feeders(self, root_substation: str) -> FeederTree:
        """
        Trace all downstream feeder branches and leaf buses starting from a substation.
        """
        if root_substation not in self._buses and (self._graph is None or root_substation not in self._graph):
            return FeederTree(
                root_substation=root_substation,
                buses=[root_substation],
                branches=[],
                leaf_buses=[root_substation],
            )

        visited_buses: set[str] = set()
        visited_branches: set[str] = set()
        leaf_buses: list[str] = []
        max_depth = 0

        # BFS traversal
        queue: list[tuple[str, int]] = [(root_substation, 0)]
        visited_buses.add(root_substation)

        while queue:
            current_bus, depth = queue.pop(0)
            max_depth = max(max_depth, depth)
            neighbors = self.get_adjacent_buses(current_bus)

            is_leaf = True
            for neighbor in neighbors:
                if neighbor not in visited_buses:
                    is_leaf = False
                    visited_buses.add(neighbor)
                    branch = self._get_branch_between(current_bus, neighbor)
                    if branch is not None:
                        visited_branches.add(branch.id)
                    queue.append((neighbor, depth + 1))

            if is_leaf and current_bus != root_substation:
                leaf_buses.append(current_bus)

        return FeederTree(
            root_substation=root_substation,
            buses=list(visited_buses),
            branches=list(visited_branches),
            leaf_buses=leaf_buses if leaf_buses else [root_substation],
            max_depth=max_depth,
        )


# Global singleton instance
network_topology = NetworkTopology()
