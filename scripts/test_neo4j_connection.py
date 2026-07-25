#!/usr/bin/env python3
"""
Neo4j Connection Test Script for AhmedETAP
Tests Neo4j connectivity with provided credentials.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"[INFO] Loaded .env from {env_path}")
else:
    print(f"[WARN] .env not found at {env_path}")

# Color codes
OK = "\033[92m"
FAIL = "\033[91m"
WARN = "\033[93m"
BOLD = "\033[1m"
END = "\033[0m"


def print_header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"{BOLD}{title}{END}")
    print(f"{'='*60}")


def test_neo4j():
    print_header("NEO4J CONNECTION TEST")

    # Read config
    uri = os.environ.get("NEO4J_URI", "")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")

    print(f"  URI:     {uri or '(not set)'}")
    print(f"  User:    {user}")
    print(f"  Password: {'***' + password[-4:] if password and len(password) > 4 else '(not set)' if not password else '***'}")

    if not uri:
        print(f"\n  {FAIL}[FAIL]{END} NEO4J_URI not set in .env")
        return False

    if not password:
        print(f"\n  {FAIL}[FAIL]{END} NEO4J_PASSWORD not set in .env")
        return False

    # Test import
    try:
        import neo4j as _neo4j_mod
        from neo4j import GraphDatabase
        print(f"  {OK}[OK]{END}   neo4j SDK imported successfully (v{_neo4j_mod.__version__})")
    except ImportError as e:
        print(f"  {FAIL}[FAIL]{END} neo4j SDK not installed: {e}")
        return False
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END} Import error: {e}")
        return False

    # Test connection
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=10)
        print(f"  {OK}[OK]{END}   Driver created for {uri}")

        with driver.session() as session:
            result = session.run("RETURN 1 AS ok").single()
            if result and result["ok"] == 1:
                print(f"  {OK}[OK]{END}   Connection SUCCESS — query 'RETURN 1 AS ok' returned 1")
            else:
                print(f"  {FAIL}[FAIL]{END}  Query returned unexpected result: {result}")
                driver.close()
                return False

            # Check Neo4j version
            version_result = session.run("CALL dbms.components() YIELD name, versions RETURN name, versions LIMIT 1").single()
            if version_result:
                print(f"  {OK}[OK]{END}   Server: {version_result['name']}, Versions: {version_result['versions']}")

            # Check existing constraints and labels
            labels_result = [r for r in session.run("CALL db.labels() YIELD label RETURN label ORDER BY label")]
            if labels_result:
                labels = [r['label'] for r in labels_result]
                print(f"  {OK}[OK]{END}   Existing labels: {labels}")

            # Check node count
            count_result = session.run("MATCH (n) RETURN count(n) AS count").single()
            if count_result:
                print(f"  {OK}[OK]{END}   Total nodes in database: {count_result['count']}")

            # Check relationship count
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()
            if rel_result:
                print(f"  {OK}[OK]{END}   Total relationships: {rel_result['count']}")

        driver.close()
        print(f"\n  {OK}[OK]{END}   Neo4j connection test PASSED")
        return True

    except ImportError as e:
        print(f"  {FAIL}[FAIL]{END}  Import error: {e}")
        return False
    except Exception as e:
        err = str(e)
        if "DNS" in err or "Name or service not known" in err or "TransientError" in err:
            print(f"\n  {FAIL}[FAIL]{END}  DNS resolution failed — URI '{uri}' may be incorrect")
            print(f"  {WARN}[WARN]{END}  Common formats:")
            print(f"    - bolt://localhost:7687 (local Docker)")
            print(f"    - neo4j+s://<id>.databases.neo4j.io (Aura)")
            print(f"    - neo4j://<host>:7687 (remote)")
        elif "Authentication" in err or "auth" in err.lower():
            print(f"\n  {FAIL}[FAIL]{END}  Authentication failed — check NEO4J_USER and NEO4J_PASSWORD")
        elif "Connection" in err or "connect" in err.lower():
            print(f"\n  {FAIL}[FAIL]{END}  Connection refused — Neo4j server may not be running at {uri}")
        else:
            print(f"\n  {FAIL}[FAIL]{END}  Connection error: {err[:300]}")
        return False


def test_integration_module():
    """Test the project's own Neo4j integration module."""
    print_header("NEO4J INTEGRATION MODULE TEST")

    try:
        from integrations.neo4j_integration import neo4j_client, get_neo4j_db, Neo4jDB
        print(f"  {OK}[OK]{END}   Integration module imported")

        # Health check
        health = neo4j_client.health_check()
        print(f"  Health check:")
        for k, v in health.items():
            status = f"{OK}{v}{END}" if v else f"{WARN}{v}{END}"
            print(f"    {k}: {status}")

        if health.get("enabled") and health.get("driver_initialized"):
            db = get_neo4j_db()
            topo = db.get_topology()
            print(f"  {OK}[OK]{END}   get_neo4j_db() works — buses: {len(topo.get('buses', []))}, lines: {len(topo.get('lines', []))}")
        else:
            print(f"  {WARN}[WARN]{END}  Neo4j client is not enabled (expected in local dev without Neo4j running)")

    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  Integration module error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    success = test_neo4j()
    test_integration_module()
    print_header("NEO4J TEST COMPLETE")
    sys.exit(0 if success else 1)
