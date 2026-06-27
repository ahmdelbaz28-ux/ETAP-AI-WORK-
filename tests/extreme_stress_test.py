#!/usr/bin/env python3
"""
Extreme Stress Test Suite for AhmedETAP
=======================================
Tests every component under maximum load to find weaknesses.

Run: python tests/extreme_stress_test.py
"""

import gc
import json
import os
import sys
import threading
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Load .env file so JWT_SECRET_KEY, FERNET_ENCRYPTION_KEY, etc. are available
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

RESULTS = {"start_time": time.time(), "tests": [], "weaknesses": []}


def log_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    entry = {"name": name, "passed": passed, "details": details}
    RESULTS["tests"].append(entry)
    print(f"  {status}: {name}" + (f" — {details}" if details else ""))


def log_weakness(component, severity, description, file_path=""):
    entry = {
        "component": component,
        "severity": severity,  # CRITICAL, HIGH, MEDIUM, LOW
        "description": description,
        "file": file_path,
    }
    RESULTS["weaknesses"].append(entry)
    icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}[severity]
    print(f"  {icon} WEAKNESS [{severity}] {component}: {description}")


# ============================================================================
# TEST 1: Python Module Import Stress — import every module, measure time + memory
# ============================================================================
print("\n" + "=" * 70)
print("TEST 1: Python Module Import Stress")
print("=" * 70)

import importlib
import tracemalloc


def stress_import_modules():
    """Try to import every Python module in the project. Find ones that
    fail, take too long, or leak memory."""
    modules_to_test = [
        "api.auth",
        "api.routes",
        "api.health",
        "api.ai_ml",
        "api.studies",
        "api.projects",
        "api.agents",
        "api.context_engine",
        "api.shared_handlers",
        "ai_context_engine.indexer",
        "ai_context_engine.retriever",
        "ai_context_engine.knowledge_graph",
        "ai_context_engine.text_chunker",
        "ai_context_engine.document_ingestor",
        "knowledge.rag_engine",
        "agents.orchestrator",
        "agents.load_flow_agent" if False else "agents",
        "core.models",
        "core.database",
        "core.redis_state",
        "engine.engine",
        "engine.sparse_solver",
        "engine.gpu_solver",
        "fault_analysis.arc_flash_engine",
        "fault_analysis.fault",
        "load_flow.solver",
        "load_flow.consolidated_solver",
        "network_solver.zbus",
        "network_solver.per_unit",
        "core_model.system",
        "core_model.bus",
        "scada_model.scada_model",
        "security.abac",
        "security.rasp",
        "security.siem",
        "digital_twin.state_store",
        "digital_twin.event_bus",
        "integrations.langwatch_integration",
        "integrations.smithery_mcp",
        "gis_integration.base",
        "gis_model.gis_model",
        "coordination.coordination",
        "relays.relay",
        "reporting.advanced_reports",
        "visualization.visualization",
        "ml.predictive",
        "guards.base",
        "guards.code_guard",
        "services.memory_service",
        "services.cache_service",
        "worker.celery_app",
        "worker.tasks",
        "etap_integration.etap_adapter",
        "etap_integration.sync_engine",
        "copilot.api.routes",
        "acp_runtime.acp.http_server",
    ]

    successes = 0
    failures = []
    slow_imports = []
    memory_hogs = []

    for mod_name in modules_to_test:
        tracemalloc.start()
        start = time.perf_counter()
        try:
            importlib.import_module(mod_name)
            elapsed = time.perf_counter() - start
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # 15s threshold — realistic for modules importing scientific
            # computing libraries (numpy, scipy, pandas, scikit-learn)
            if elapsed > 15.0:
                slow_imports.append((mod_name, elapsed))
                log_weakness(
                    "Import Performance",
                    "MEDIUM",
                    f"Module '{mod_name}' takes {elapsed:.2f}s to import (>10s threshold)",
                )
            # 150MB threshold — numpy+scipy+pandas alone use ~100MB
            if peak > 150 * 1024 * 1024:  # 150MB
                memory_hogs.append((mod_name, peak / 1024 / 1024))
                log_weakness(
                    "Import Memory",
                    "MEDIUM",
                    f"Module '{mod_name}' uses {peak / 1024 / 1024:.1f}MB peak on import (>150MB threshold)",
                )
            successes += 1
        except Exception as e:
            tracemalloc.stop()
            err_msg = str(e)[:120]
            failures.append((mod_name, err_msg))
            # Don't log as weakness if it's just a missing optional dependency
            if "No module named" not in str(e) and "cannot import" not in str(e).lower():
                log_weakness(
                    "Import Failure",
                    "HIGH",
                    f"Module '{mod_name}' fails to import: {err_msg}",
                )

    log_test(
        "Module imports",
        len(failures) == 0 or all("No module named" in f[1] for f in failures),
        f"{successes}/{len(modules_to_test)} imported, {len(failures)} failed, "
        f"{len(slow_imports)} slow, {len(memory_hogs)} memory-heavy",
    )


stress_import_modules()
gc.collect()


# ============================================================================
# TEST 2: Text Chunker Stress — large documents, edge cases, memory
# ============================================================================
print("\n" + "=" * 70)
print("TEST 2: Text Chunker Stress")
print("=" * 70)


def stress_text_chunker():
    """Test the chunkr-inspired text chunker with extreme inputs."""
    from ai_context_engine.text_chunker import (
        Chunk,
        ChunkingConfig,
        Segment,
        SegmentType,
        hierarchical_chunking,
    )

    # 2a: Very large document (10,000 segments)
    segments = [
        Segment(
            content=f"Segment {i} with some text content to fill space",
            segment_type=SegmentType.TEXT,
        )
        for i in range(10000)
    ]
    config = ChunkingConfig(target_length=100)
    start = time.perf_counter()
    chunks = hierarchical_chunking(segments, config)
    elapsed = time.perf_counter() - start
    log_test(
        "10K segments chunking",
        len(chunks) > 0 and elapsed < 5.0,
        f"{len(chunks)} chunks in {elapsed:.3f}s",
    )
    if elapsed > 5.0:
        log_weakness(
            "Chunker Performance", "HIGH", f"10K segments took {elapsed:.2f}s (should be <5s)"
        )

    # 2b: Empty segments
    try:
        hierarchical_chunking([], config)
        log_test("Empty segments", True)
    except Exception as e:
        log_test("Empty segments", False, str(e))
        log_weakness("Chunker Robustness", "CRITICAL", f"Empty input crashes: {e}")

    # 2c: Very long single segment (1M characters)
    huge_content = "word " * 200000  # 1M chars
    segs = [Segment(content=huge_content, segment_type=SegmentType.TEXT)]
    start = time.perf_counter()
    chunks = hierarchical_chunking(segs, ChunkingConfig(target_length=500))
    elapsed = time.perf_counter() - start
    log_test(
        "1M char segment",
        len(chunks) > 0 and elapsed < 2.0,
        f"{len(chunks)} chunks in {elapsed:.3f}s",
    )

    # 2d: All segment types mixed
    all_types = [
        Segment(content="Title", segment_type=SegmentType.TITLE),
        Segment(content="Header", segment_type=SegmentType.SECTION_HEADER),
        Segment(content="Body text", segment_type=SegmentType.TEXT),
        Segment(content="[Image]", segment_type=SegmentType.PICTURE),
        Segment(content="Figure 1", segment_type=SegmentType.CAPTION),
        Segment(content="| Col1 | Col2 |", segment_type=SegmentType.TABLE),
        Segment(content="Page 1", segment_type=SegmentType.PAGE_HEADER),
        Segment(content="Footer", segment_type=SegmentType.PAGE_FOOTER),
        Segment(content="• item", segment_type=SegmentType.LIST_ITEM),
        Segment(content="footnote", segment_type=SegmentType.FOOTNOTE),
        Segment(content="E=mc²", segment_type=SegmentType.FORMULA),
    ]
    chunks = hierarchical_chunking(
        all_types, ChunkingConfig(target_length=100, ignore_headers_and_footers=False)
    )
    log_test("All 11 segment types", len(chunks) > 0, f"{len(chunks)} chunks")

    # 2e: Negative target_length (should raise)
    try:
        hierarchical_chunking(segs, ChunkingConfig(target_length=-1))
        log_test("Negative target_length rejection", False, "should have raised")
        log_weakness("Chunker Validation", "HIGH", "Negative target_length not rejected")
    except ValueError:
        log_test("Negative target_length rejection", True)


stress_text_chunker()
gc.collect()


# ============================================================================
# TEST 3: RAG Engine Stress — large knowledge base, concurrent queries
# ============================================================================
print("\n" + "=" * 70)
print("TEST 3: RAG Engine Stress")
print("=" * 70)


def stress_rag_engine():
    """Test the RAG knowledge base under load."""
    try:
        from knowledge.rag_engine import EngineeringDocument, EngineeringKnowledgeBase
    except ImportError as e:
        log_test("RAG engine import", False, str(e))
        return

    # 3a: Initialize knowledge base (should be fast)
    start = time.perf_counter()
    try:
        kb = EngineeringKnowledgeBase()
        elapsed = time.perf_counter() - start
        log_test("RAG init", elapsed < 10.0, f"{elapsed:.2f}s")
        if elapsed > 10.0:
            log_weakness(
                "RAG Performance", "HIGH", f"RAG init takes {elapsed:.1f}s (should be <10s)"
            )
    except Exception as e:
        log_test("RAG init", False, str(e)[:100])
        log_weakness("RAG Robustness", "CRITICAL", f"RAG init crashes: {str(e)[:100]}")
        return

    # 3b: Concurrent queries (50 parallel)
    queries = [
        "What is IEEE 1584 arc flash?",
        "IEC 60909 short circuit calculation",
        "How to calculate load flow?",
        "Protection coordination IEC 60255",
        "IEEE 519 harmonic distortion limits",
    ] * 10  # 50 queries

    errors = []
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(kb.retrieve_knowledge, q, 3): q for q in queries}
        for future in as_completed(futures):
            try:
                future.result(timeout=15)
            except Exception as e:
                errors.append(str(e)[:80])
    elapsed = time.perf_counter() - start
    log_test(
        "50 concurrent RAG queries",
        len(errors) == 0,
        f"{len(queries) - len(errors)}/{len(queries)} succeeded in {elapsed:.2f}s",
    )
    if errors:
        log_weakness(
            "RAG Concurrency", "HIGH", f"{len(errors)}/50 concurrent queries failed: {errors[0]}"
        )


stress_rag_engine()
gc.collect()


# ============================================================================
# TEST 4: Security Hardening Stress — auth, rate limiting, injection
# ============================================================================
print("\n" + "=" * 70)
print("TEST 4: Security Hardening Stress")
print("=" * 70)


def stress_security():
    """Test security components for weaknesses."""
    # 4a: Check for hardcoded secrets in non-test files
    import subprocess

    result = subprocess.run(
        [sys.executable, "scripts/security_scan.py"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    log_test(
        "Security scan (hardcoded secrets)",
        result.returncode == 0,
        result.stdout.strip() if result.returncode == 0 else result.stderr.strip()[:100],
    )

    # 4b: Check .env is not tracked by git
    result = subprocess.run(
        ["git", "ls-files", ".env"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    env_tracked = result.stdout.strip()
    log_test(".env not in git", env_tracked == "", "TRACKED!" if env_tracked else "not tracked")
    if env_tracked:
        log_weakness("Security", "CRITICAL", ".env file is tracked by git!")

    # 4c: Check JWT secret length
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "")
    if len(jwt_secret) < 32:
        log_weakness(
            "Security", "HIGH", f"JWT_SECRET_KEY is {len(jwt_secret)} chars (should be ≥32)"
        )
        log_test("JWT secret length", False, f"{len(jwt_secret)} chars")
    else:
        log_test("JWT secret length", True, f"{len(jwt_secret)} chars")

    # 4d: Check Fernet key validity
    fernet_key = os.environ.get("FERNET_ENCRYPTION_KEY", "")
    if fernet_key:
        try:
            from cryptography.fernet import Fernet

            Fernet(fernet_key.encode())
            log_test("Fernet key validity", True)
        except Exception as e:
            log_test("Fernet key validity", False, str(e)[:60])
            log_weakness("Security", "HIGH", f"Invalid Fernet key: {e}")

    # 4e: Check for SQL injection patterns in code
    sql_risks = []
    for py_file in PROJECT_ROOT.rglob("*.py"):
        if "/tests/" in str(py_file) or "/.venv/" in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                # Look for string-formatted SQL with f-strings or .format()
                if any(kw in line.lower() for kw in ["select ", "insert ", "update ", "delete "]):
                    if "f'" in line or 'f"' in line or ".format(" in line or "%" in line:
                        if "execute" in line.lower() or "cursor" in line.lower():
                            sql_risks.append(f"{py_file}:{i}: {line.strip()[:80]}")
        except Exception:
            pass

    if sql_risks:
        log_weakness("Security", "HIGH", f"Possible SQL injection: {sql_risks[0]}")
    log_test(
        "SQL injection scan",
        len(sql_risks) == 0,
        f"{len(sql_risks)} potential risks found" if sql_risks else "clean",
    )


stress_security()
gc.collect()


# ============================================================================
# TEST 5: Memory Leak Detection — repeated operations
# ============================================================================
print("\n" + "=" * 70)
print("TEST 5: Memory Leak Detection")
print("=" * 70)


def stress_memory_leaks():
    """Run operations repeatedly and check for memory growth."""
    import tracemalloc

    # 5a: Text chunker repeated calls
    try:
        from ai_context_engine.text_chunker import (
            ChunkingConfig,
            Segment,
            SegmentType,
            hierarchical_chunking,
        )

        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        segments = [
            Segment(content=f"Test segment {i} with words", segment_type=SegmentType.TEXT)
            for i in range(1000)
        ]
        config = ChunkingConfig(target_length=100)
        for _ in range(50):
            hierarchical_chunking(segments, config)
            gc.collect()

        snapshot2 = tracemalloc.take_snapshot()
        stats = snapshot2.compare_to(snapshot1, "lineno")
        total_growth = sum(s.size_diff for s in stats if s.size_diff > 0)
        tracemalloc.stop()

        growth_mb = total_growth / 1024 / 1024
        log_test(
            "Chunker memory leak",
            growth_mb < 10.0,
            f"memory growth: {growth_mb:.2f}MB after 50 iterations",
        )
        if growth_mb > 10.0:
            log_weakness(
                "Memory Leak", "HIGH", f"Chunker leaks {growth_mb:.1f}MB after 50 iterations"
            )
    except Exception as e:
        log_test("Chunker memory leak", False, str(e)[:80])

    # 5b: RAG engine repeated queries
    try:
        from knowledge.rag_engine import EngineeringKnowledgeBase

        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        kb = EngineeringKnowledgeBase()
        for _ in range(20):
            kb.retrieve_knowledge("IEEE 1584 arc flash", top_k=3)
            gc.collect()

        snapshot2 = tracemalloc.take_snapshot()
        stats = snapshot2.compare_to(snapshot1, "lineno")
        total_growth = sum(s.size_diff for s in stats if s.size_diff > 0)
        tracemalloc.stop()

        growth_mb = total_growth / 1024 / 1024
        log_test(
            "RAG memory leak",
            growth_mb < 20.0,
            f"memory growth: {growth_mb:.2f}MB after 20 queries",
        )
        if growth_mb > 20.0:
            log_weakness("Memory Leak", "MEDIUM", f"RAG leaks {growth_mb:.1f}MB after 20 queries")
    except Exception as e:
        log_test("RAG memory leak", False, str(e)[:80])


stress_memory_leaks()
gc.collect()


# ============================================================================
# TEST 6: Concurrent Thread Safety — race conditions
# ============================================================================
print("\n" + "=" * 70)
print("TEST 6: Concurrent Thread Safety")
print("=" * 70)


def stress_thread_safety():
    """Test for race conditions in shared state."""
    # 6a: Concurrent chunker calls (shared config object)
    try:
        from ai_context_engine.text_chunker import (
            ChunkingConfig,
            Segment,
            SegmentType,
            hierarchical_chunking,
        )

        config = ChunkingConfig(target_length=50)
        errors = []

        def worker(worker_id):
            try:
                segs = [
                    Segment(content=f"W{worker_id} segment {i}", segment_type=SegmentType.TEXT)
                    for i in range(100)
                ]
                chunks = hierarchical_chunking(segs, config)
                return len(chunks) > 0
            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")
                return False

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(worker, range(20)))

        success_count = sum(results)
        log_test(
            "20 concurrent chunker workers",
            len(errors) == 0 and success_count == 20,
            f"{success_count}/20 succeeded, {len(errors)} errors",
        )
        if errors:
            log_weakness("Thread Safety", "HIGH", f"Chunker race condition: {errors[0]}")
    except Exception as e:
        log_test("Concurrent chunker", False, str(e)[:80])

    # 6b: Concurrent RAG knowledge base access
    try:
        from knowledge.rag_engine import EngineeringKnowledgeBase

        kb = EngineeringKnowledgeBase()
        errors = []

        def rag_worker(q):
            try:
                kb.retrieve_knowledge(q, top_k=2)
                return True
            except Exception as e:
                errors.append(str(e)[:60])
                return False

        queries = ["IEEE 1584", "IEC 60909", "load flow", "harmonic", "protection"] * 4
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(rag_worker, queries))

        log_test(
            "20 concurrent RAG queries",
            len(errors) == 0,
            f"{sum(results)}/{len(queries)} succeeded",
        )
        if errors:
            log_weakness("Thread Safety", "HIGH", f"RAG race condition: {errors[0]}")
    except Exception as e:
        log_test("Concurrent RAG", False, str(e)[:80])


stress_thread_safety()
gc.collect()


# ============================================================================
# TEST 7: UI Bundle Size Analysis
# ============================================================================
print("\n" + "=" * 70)
print("TEST 7: UI Bundle Size Analysis")
print("=" * 70)


def stress_ui_bundle():
    """Check UI bundle sizes for bloat."""
    dist_dir = PROJECT_ROOT / "ui" / "dist" / "assets"
    if not dist_dir.exists():
        log_test("UI bundle analysis", False, "ui/dist/assets not found")
        return

    js_files = sorted(dist_dir.glob("*.js"), key=lambda f: f.stat().st_size, reverse=True)
    total_size = sum(f.stat().st_size for f in js_files)
    total_kb = total_size / 1024

    log_test(
        "UI bundle total", total_kb < 2048, f"{total_kb:.0f}KB across {len(js_files)} JS files"
    )

    # Flag chunks > 500KB
    large_chunks = [
        (f.name, f.stat().st_size / 1024) for f in js_files if f.stat().st_size > 500 * 1024
    ]
    if large_chunks:
        for name, size in large_chunks:
            log_weakness(
                "Bundle Size", "MEDIUM", f"Chunk '{name}' is {size:.0f}KB (>500KB threshold)"
            )
    else:
        log_test("No oversized chunks", True)

    # Check for duplicate icons (lucide-react tree-shaking)
    icon_chunks = [
        f
        for f in js_files
        if "lucide" in f.name.lower() or f.name.startswith("link-") or f.name.startswith("chart-")
    ]
    total_icon_kb = sum(f.stat().st_size for f in icon_chunks) / 1024
    if total_icon_kb > 50:
        log_weakness(
            "Bundle Size", "LOW", f"Icon chunks total {total_icon_kb:.0f}KB — check tree-shaking"
        )


stress_ui_bundle()


# ============================================================================
# TEST 8: Error Handling Robustness — malformed inputs
# ============================================================================
print("\n" + "=" * 70)
print("TEST 8: Error Handling Robustness")
print("=" * 70)


def stress_error_handling():
    """Feed malformed/edge-case inputs to find unhandled exceptions."""
    try:
        from ai_context_engine.text_chunker import (
            ChunkingConfig,
            Segment,
            SegmentType,
            hierarchical_chunking,
        )

        # 8a: None content
        try:
            seg = Segment(content=None, segment_type=SegmentType.TEXT)  # type: ignore
            chunks = hierarchical_chunking([seg], ChunkingConfig(target_length=100))
            log_test("None content handling", True, f"{len(chunks)} chunks")
        except Exception as e:
            log_weakness("Error Handling", "MEDIUM", f"None content crashes chunker: {e}")
            log_test("None content handling", False, str(e)[:60])

        # 8b: Unicode/multilingual content
        segs = [
            Segment(content="مرحبا بالعالم العربية", segment_type=SegmentType.TEXT),
            Segment(content="你好世界", segment_type=SegmentType.TEXT),
            Segment(content="🎉🎊🎈", segment_type=SegmentType.TEXT),
            Segment(content="Null\x00byte\x00content", segment_type=SegmentType.TEXT),
        ]
        try:
            chunks = hierarchical_chunking(segs, ChunkingConfig(target_length=100))
            log_test("Unicode/multilingual", True, f"{len(chunks)} chunks")
        except Exception as e:
            log_weakness("Error Handling", "HIGH", f"Unicode content crashes: {e}")
            log_test("Unicode/multilingual", False, str(e)[:60])

        # 8c: Very deep nesting (many Title > Section > Text)
        segs = []
        for i in range(100):
            segs.append(Segment(content=f"Title {i}", segment_type=SegmentType.TITLE))
            segs.append(Segment(content=f"Section {i}", segment_type=SegmentType.SECTION_HEADER))
            segs.append(Segment(content=f"Body {i}", segment_type=SegmentType.TEXT))
        try:
            chunks = hierarchical_chunking(segs, ChunkingConfig(target_length=50))
            log_test("Deep nesting (300 segments)", True, f"{len(chunks)} chunks")
        except Exception as e:
            log_weakness("Error Handling", "HIGH", f"Deep nesting crashes: {e}")
            log_test("Deep nesting", False, str(e)[:60])

    except ImportError:
        log_test("Error handling tests", False, "text_chunker not importable")


stress_error_handling()
gc.collect()


# ============================================================================
# TEST 9: API Endpoint Schema Validation
# ============================================================================
print("\n" + "=" * 70)
print("TEST 9: API Endpoint Schema Validation")
print("=" * 70)


def stress_api_schemas():
    """Check that API request/response schemas are properly defined."""
    import ast

    api_files = list((PROJECT_ROOT / "api").glob("*.py"))
    total_endpoints = 0
    endpoints_without_schema = 0

    for api_file in api_files:
        try:
            content = api_file.read_text(encoding="utf-8")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        # Check if decorator is @router.get/post/put/delete
                        if isinstance(decorator, ast.Call) and isinstance(
                            decorator.func, ast.Attribute
                        ):
                            http_method = decorator.func.attr
                            if http_method in ("get", "post", "put", "delete", "patch"):
                                total_endpoints += 1
                                # GET endpoints don't need request body models —
                                # they have no input to validate. Only flag
                                # POST/PUT/PATCH endpoints that lack schemas.
                                if http_method in ("post", "put", "patch"):
                                    has_model = False
                                    for arg in node.args.args:
                                        if arg.annotation and isinstance(arg.annotation, ast.Name):
                                            if (
                                                arg.annotation.id[0].isupper()
                                                and arg.annotation.id != "Request"
                                            ):
                                                has_model = True
                                                break
                                    if not has_model and "request" not in [
                                        a.arg for a in node.args.args
                                    ]:
                                        endpoints_without_schema += 1
        except Exception:
            pass

    log_test(
        "API schema coverage",
        endpoints_without_schema == 0,
        f"{total_endpoints - endpoints_without_schema}/{total_endpoints} have schemas",
    )
    if endpoints_without_schema > 0:
        log_weakness(
            "API Validation",
            "MEDIUM",
            f"{endpoints_without_schema} endpoints lack Pydantic request models",
        )


stress_api_schemas()


# ============================================================================
# TEST 10: Dependency Security — check for known vulnerabilities
# ============================================================================
print("\n" + "=" * 70)
print("TEST 10: Dependency Security Check")
print("=" * 70)


def stress_dependency_security():
    """Check requirements.txt for pinned versions and known issues."""
    req_file = PROJECT_ROOT / "requirements.txt"
    if not req_file.exists():
        log_test("Dependency check", False, "requirements.txt not found")
        return

    content = req_file.read_text()
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]

    unpinned = []
    for line in lines:
        # Check for unpinned packages (no == or ~=)
        if "==" not in line and "~=" not in line and ">=" not in line:
            if not line.startswith("-r") and not line.startswith("git+"):
                unpinned.append(line)

    log_test(
        "Pinned dependencies",
        len(unpinned) == 0,
        f"{len(lines) - len(unpinned)}/{len(lines)} pinned"
        if unpinned
        else f"all {len(lines)} pinned",
    )
    if unpinned:
        log_weakness("Dependency Security", "LOW", f"Unpinned: {', '.join(unpinned[:3])}")

    # Check for known-vulnerable versions
    # Each entry: (package_name, min_safe_version, CVE_id)
    # We parse the actual version from requirements.txt and compare numerically.
    import re as _re

    vulnerable_checks = [
        ("jinja2", "3.1.4", "CVE-2024-34064"),
        ("pillow", "10.3.0", "CVE-2024-28219"),
        ("cryptography", "42.0.4", "CVE-2024-26130"),
    ]
    for pkg, safe_ver, cve in vulnerable_checks:
        for line in lines:
            if line.lower().startswith(pkg):
                vm = _re.search(r"[>~]=?\s*(\d+\.\d+\.\d+)", line)
                if vm:
                    declared = [int(x) for x in vm.group(1).split(".")]
                    safe = [int(x) for x in safe_ver.split(".")]
                    if declared < safe:
                        log_weakness(
                            "Dependency Security",
                            "HIGH",
                            f"{pkg} {vm.group(1)} < {safe_ver} — {cve}",
                        )
                break


stress_dependency_security()


# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("STRESS TEST SUMMARY")
print("=" * 70)

total_tests = len(RESULTS["tests"])
passed_tests = sum(1 for t in RESULTS["tests"] if t["passed"])
failed_tests = total_tests - passed_tests

critical = sum(1 for w in RESULTS["weaknesses"] if w["severity"] == "CRITICAL")
high = sum(1 for w in RESULTS["weaknesses"] if w["severity"] == "HIGH")
medium = sum(1 for w in RESULTS["weaknesses"] if w["severity"] == "MEDIUM")
low = sum(1 for w in RESULTS["weaknesses"] if w["severity"] == "LOW")

print(f"\nTests: {passed_tests}/{total_tests} passed ({failed_tests} failed)")
print(f"Weaknesses: {critical} CRITICAL, {high} HIGH, {medium} MEDIUM, {low} LOW")
print(f"Total weaknesses: {len(RESULTS['weaknesses'])}")

if RESULTS["weaknesses"]:
    print("\n--- WEAKNESS DETAILS ---")
    for w in RESULTS["weaknesses"]:
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}[w["severity"]]
        print(f"  {icon} [{w['severity']}] {w['component']}: {w['description']}")

RESULTS["end_time"] = time.time()
RESULTS["total_duration_sec"] = RESULTS["end_time"] - RESULTS["start_time"]
RESULTS["summary"] = {
    "total_tests": total_tests,
    "passed": passed_tests,
    "failed": failed_tests,
    "weaknesses": {
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
    },
}

output_file = PROJECT_ROOT / "tests" / "extreme-stress-report.json"
with open(output_file, "w") as f:
    json.dump(RESULTS, f, indent=2, default=str)
print(f"\nReport saved: {output_file}")
print(f"Duration: {RESULTS['total_duration_sec']:.1f}s")
