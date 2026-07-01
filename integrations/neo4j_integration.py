"""
Neo4j Integration for AhmedETAP
Provides graph database access for network topology, power system modeling,
and knowledge graph operations.

Usage:
    from integrations.neo4j_integration import neo4j_client, get_neo4j_db

    # Direct client usage
    with neo4j_client.driver.session() as session:
        result = session.run("MATCH (n) RETURN n LIMIT 10")

    # Or via database helper
    db = get_neo4j_db()
    buses = db.get_all_buses()
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Neo4j SDK (optional dependency) ─────────────────────────────────────
try:
    from neo4j import GraphDatabase, Driver, Session

    NEO4J_AVAILABLE = True
    logger.debug("Neo4j SDK loaded successfully")
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("Neo4j SDK not installed. Run: pip install neo4j")


class Neo4jClient:
    """
    Central Neo4j client wrapper for AhmedETAP.
    Provides graph database access for network topology and knowledge graphs.
    """

    def __init__(self):
        self.uri = os.environ.get("NEO4J_URI", "")
        self.username = os.environ.get("NEO4J_USER", "neo4j")
        self.password = os.environ.get("NEO4J_PASSWORD", "")
        self.enabled = bool(self.uri and self.password and NEO4J_AVAILABLE)

        if self.enabled:
            try:
                self.driver: Driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.username, self.password),
                )
                # Test connection
                with self.driver.session() as session:
                    session.run("RETURN 1")
                logger.info(f"✅ Neo4j initialized — URI: {self.uri}")
            except Exception as e:
                logger.error(f"Neo4j connection failed: {e}")
                self.driver = None
                self.enabled = False
        else:
            self.driver = None
            if not self.uri:
                logger.info("Neo4j disabled: NEO4J_URI not set")
            elif not self.password:
                logger.info("Neo4j disabled: NEO4J_PASSWORD not set")
            elif not NEO4J_AVAILABLE:
                logger.info("Neo4j disabled: SDK not installed")

    def close(self):
        """Close the driver connection."""
        if self.driver:
            self.driver.close()

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a Cypher query."""
        if not self.enabled or not self.driver:
            return {"error": "Neo4j is not enabled", "data": []}
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                data = [record.data() for record in result]
                return {"success": True, "data": data, "error": None}
        except Exception as e:
            logger.error(f"Neo4j query error: {e}")
            return {"success": False, "data": [], "error": str(e)}

    def health_check(self) -> Dict[str, Any]:
        """Return Neo4j integration status."""
        return {
            "enabled": self.enabled,
            "uri": self.uri,
            "sdk_available": NEO4J_AVAILABLE,
            "driver_initialized": self.driver is not None,
        }


# ─── Module-level singleton ───────────────────────────────────────────────────
neo4j_client = Neo4jClient()


def get_neo4j_db() -> Neo4jClient:
    """Get the Neo4j client instance."""
    return neo4j_client


# ─── Graph database helpers for common operations ────────────────────────────

class Neo4jDB:
    """High-level graph database operations for AhmedETAP."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    def get_all_buses(self) -> List[Dict[str, Any]]:
        """Get all buses from the power system graph."""
        result = self.client.execute_query("MATCH (b:Bus) RETURN b")
        return result.get("data", [])

    def get_all_lines(self) -> List[Dict[str, Any]]:
        """Get all transmission lines from the graph."""
        result = self.client.execute_query("MATCH (l:Line) RETURN l")
        return result.get("data", [])

    def get_topology(self) -> Dict[str, Any]:
        """Get the complete network topology."""
        buses = self.get_all_buses()
        lines = self.get_all_lines()
        return {"buses": buses, "lines": lines}

    def create_bus(self, bus_id: str, voltage_kv: float, bus_type: str = "bus") -> Dict[str, Any]:
        """Create a new bus node."""
        query = """
        CREATE (b:Bus {id: $bus_id, voltage_kv: $voltage_kv, type: $bus_type})
        RETURN b
        """
        return self.client.execute_query(query, {
            "bus_id": bus_id,
            "voltage_kv": voltage_kv,
            "bus_type": bus_type,
        })

    def create_line(self, line_id: str, from_bus: str, to_bus: str, impedance: float) -> Dict[str, Any]:
        """Create a new transmission line."""
        query = """
        MATCH (from:Bus {id: $from_bus})
        MATCH (to:Bus {id: $to_bus})
        CREATE (from)-[r:LINE {id: $line_id, impedance: $impedance}]->(to)
        RETURN r
        """
        return self.client.execute_query(query, {
            "line_id": line_id,
            "from_bus": from_bus,
            "to_bus": to_bus,
            "impedance": impedance,
        })

    def get_shortest_path(self, from_bus: str, to_bus: str) -> Optional[List[Dict[str, Any]]]:
        """Find the shortest path between two buses."""
        query = """
        MATCH (from:Bus {id: $from_bus}), (to:Bus {id: $to_bus})
        MATCH path = shortestPath((from)-[*]-(to))
        RETURN [node IN nodes(path) | node.id] AS path
        """
        result = self.client.execute_query(query, {
            "from_bus": from_bus,
            "to_bus": to_bus,
        })
        data = result.get("data", [])
        return data[0]["path"] if data else None


def get_neo4j_db_helper() -> Neo4jDB:
    """Get a Neo4jDB helper instance."""
    return Neo4jDB(neo4j_client)