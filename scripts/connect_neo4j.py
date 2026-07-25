#!/usr/bin/env python3
"""
Neo4j Connection & Verification Script for AhmedETAP.

Connects to Neo4j, verifies server info, benchmarks query latency,
and validates the project's integration module (Neo4jDB).

Usage:
    python scripts/connect_neo4j.py

Environment variables (from .env or shell):
    NEO4J_URI          bolt://localhost:7687 (default)
    NEO4J_USER         neo4j (default)
    NEO4J_PASSWORD     (required)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"[INFO] Loaded .env from {env_path}")

# Color codes
OK = "\033[92m"
FAIL = "\033[91m"
WARN = "\033[93m"
BOLD = "\033[1m"
END = "\033[0m"


def main() -> int:
    print(f"\n{BOLD}{'=' * 60}")
    print("  NEO4J CONNECTION & VERIFICATION")
    print(f"{'=' * 60}{END}\n")

    # ── 1. Read Configuration ────────────────────────────────────────────
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    username = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")

    print(f"  URI:      {uri}")
    print(f"  Username: {username}")
    if password:
        print(f"  Password: ***{password[-4:]}")
    else:
        print(f"  Password: (empty)")

    if not password:
        print(f"\n  {WARN}[WARN]{END} NEO4J_PASSWORD not set — connection will likely fail")
        return 1

    # ── 2. Create Driver with Connection Pooling ──────────────────────────
    print(f"\n  --- Creating Driver ---")
    from neo4j import GraphDatabase

    try:
        driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
            connection_timeout=10,
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
        )
        print(f"  {OK}[OK]{END}   Driver created — {uri} (pool_size=50)")
    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  Driver creation failed: {e}")
        return 1

    # ── 3. Verify Connection ────────────────────────────────────────────
    print(f"\n  --- Verify Connection ---")
    try:
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok").single()
            if result and result["ok"] == 1:
                print(f"  {OK}[OK]{END}   Connection SUCCESS")
            else:
                print(f"  {FAIL}[FAIL]{END}  Unexpected result: {result}")
                driver.close()
                return 1
    except Exception as e:
        err = str(e)
        print(f"  {FAIL}[FAIL]{END}  Connection failed: {err[:300]}")
        if "Connection refused" in err:
            print(f"  {WARN}TIP{END}: Start Neo4j: docker compose up neo4j -d")
        elif "Authentication" in err:
            print(f"  {WARN}TIP{END}: Check NEO4J_USER / NEO4J_PASSWORD")
        elif "DNS" in err or "Name or service not known" in err:
            print(f"  {WARN}TIP{END}: URI '{uri}' is incorrect")
        driver.close()
        return 1

    # ── 4. Server Info ───────────────────────────────────────────────────
    print(f"\n  --- Server Info ---")
    try:
        with driver.session() as session:
            comp = session.run(
                "CALL dbms.components() YIELD name, versions, edition "
                "RETURN name, versions, edition LIMIT 1"
            ).single()
            if comp:
                print(f"  {OK}[OK]{END}   Server:  {comp['name']}")
                print(f"  {OK}[OK]{END}   Version: {comp['versions']}")
                print(f"  {OK}[OK]{END}   Edition: {comp['edition']}")
    except Exception as e:
        print(f"  {WARN}[WARN]{END}  Server info: {e}")

    # ── 5. Database State ────────────────────────────────────────────────
    print(f"\n  --- Database State ---")
    try:
        with driver.session() as session:
            labels = [r["label"] for r in session.run(
                "CALL db.labels() YIELD label RETURN label ORDER BY label"
            )]
            count = session.run("MATCH (n) RETURN count(n) AS count").single()
            rels = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()

            print(f"  Labels:    {labels if labels else '(none)'}")
            print(f"  Nodes:     {count['count']}")
            print(f"  Relations: {rels['count']}")
    except Exception as e:
        print(f"  {WARN}[WARN]{END}  DB state: {e}")

    # ── 6. Benchmark ─────────────────────────────────────────────────────
    print(f"\n  --- Query Latency Benchmark (5 rounds) ---")
    latencies = []
    for i in range(5):
        t0 = time.perf_counter()
        with driver.session() as session:
            session.run("RETURN 1 AS ok").single()
        dt = (time.perf_counter() - t0) * 1000
        latencies.append(dt)
        print(f"  Round {i + 1}: {dt:.1f} ms")

    avg = sum(latencies) / len(latencies)
    status = (
        f"{OK}{avg:.1f} ms — healthy{END}"
        if avg < 100
        else f"{WARN}{avg:.1f} ms — elevated{END}"
    )
    print(f"  {OK}Average{END}: {status}")

    # ── 7. Integration Module Test ───────────────────────────────────────
    print(f"\n  --- Integration Module Test ---")
    try:
        os.environ["NEO4J_URI"] = uri
        os.environ["NEO4J_PASSWORD"] = password

        from integrations.neo4j_integration import neo4j_client, Neo4jDB

        health = neo4j_client.health_check()
        for k, v in health.items():
            tag = f"{OK}{v}{END}" if v else f"{WARN}{v}{END}"
            print(f"    {k}: {tag}")

        if health.get("enabled") and health.get("driver_initialized"):
            db = Neo4jDB(neo4j_client)
            buses = db.get_all_buses()
            lines = db.get_all_lines()
            print(f"  {OK}[OK]{END}   get_all_buses(): {len(buses)} buses")
            print(f"  {OK}[OK]{END}   get_all_lines(): {len(lines)} lines")

            # Smoke test: create → shortestPath → cleanup
            db.create_bus("_CONN_TEST_", 11.0, "PQ")
            sp = db.get_shortest_path("_CONN_TEST_", "_CONN_TEST_")
            print(f"  {OK}[OK]{END}   shortestPath (same-node guard): {sp}")

            with neo4j_client.driver.session() as session:
                session.run("MATCH (b:Bus {id: '_CONN_TEST_'}) DETACH DELETE b")
            print(f"  {OK}[OK]{END}   Test node cleaned up")

    except Exception as e:
        print(f"  {FAIL}[FAIL]{END}  Integration error: {e}")

    # ── 8. Close ─────────────────────────────────────────────────────────
    driver.close()
    print(f"\n  {OK}[OK]{END}   Driver closed cleanly")

    print(f"\n{BOLD}{'=' * 60}")
    print(f"  NEO4J CONNECTION — VERIFIED")
    print(f"{'=' * 60}{END}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
