"""
Professional Project Indexer for AhmedETAP
Generates a full structured JSON index of the codebase.
Can be re-run any time to refresh the index incrementally.

Usage:
  python indexer.py              # Full scan — generates PROJECT_INDEX.json + PROJECT_INDEX.md
                                 # + ui/src/help/search-index.json (for UI search)

Auto-update:
  The .github/workflows/auto-index.yml workflow re-runs this script
  on every push to main and commits the updated index files automatically.

v2.0.0 — Added scanners for:
  - Help topics (bilingual documentation)
  - External integrations (LangWatch, Smithery, HF, GitHub, Vercel)
  - Environment variables
  - Scripts directory
  - AI agents (specialized engineering agents)
  - UI search index (for command palette + help drawer)
  - Dependency graph (cross-module imports)
"""

import ast
import datetime
import hashlib
import json
import logging
import os
import re
from pathlib import Path

# SECURITY/QUALITY: added logger to replace silent except: pass below.
# indexer.py is run by CI (auto-index.yml) — silent failures would mask
# real bugs in the indexing logic.
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(".")
OUTPUT_DIR = PROJECT_ROOT
INDEX_FILE = OUTPUT_DIR / "PROJECT_INDEX.json"
MD_FILE = OUTPUT_DIR / "PROJECT_INDEX.md"
UI_SEARCH_INDEX = PROJECT_ROOT / "ui" / "src" / "help" / "search-index.json"

# ─── Directories to scan for Python modules ─────────────────────────────────
PYTHON_DIRS = [
    "agents",
    "api",
    "core",
    "engine",
    "fault_analysis",
    "load_flow",
    "services",
    "security",
    "ml",
    "worker",
    "reporting",
    "digital_twin",
    "network_solver",
    "coordination",
    "relays",
    "adms_control",
    "utils",
    "guards",
    "copilot",
    "schemas",
    "migrations",
    "etap_integration",
    "core_model",
    "scada_model",
    "acp_runtime",
    "integrations",
    "knowledge",
    "visualization",
    "gis_integration",
    "gis_model",
    "gis_validation",
    "gis_validation_real",
    "gis_validation_electrical",
    "curves",
    "zenon_user_guide",
    "etap_user_guide",
    "ai_context_engine",
    "backend",
    "autodesk_connector",
    "scada_model",
    "config",
    "monitoring",
    "helm",
    "terraform",
]

# ─── UI pages and components ─────────────────────────────────────────────────
UI_DIRS = {
    "pages": "ui/src/pages",
    "components": "ui/src/components",
    "components/help": "ui/src/components/help",
    "components/layout": "ui/src/components/layout",
    "components/ui": "ui/src/components/ui",
    "components/command": "ui/src/components/command",
    "components/context": "ui/src/components/context",
    "components/onboarding": "ui/src/components/onboarding",
    "hooks": "ui/src/hooks",
    "store": "ui/src/store",
    "context": "ui/src/context",
    "utils": "ui/src/utils",
    "lib": "ui/src/lib",
    "help": "ui/src/help",
    "locales": "ui/src/locales",
    "assets": "ui/src/assets",
}

# ─── Infrastructure files ─────────────────────────────────────────────────────
INFRA_FILES = [
    "Dockerfile",
    "Dockerfile.engineering-service",
    "Dockerfile.hf",
    "Dockerfile.windows-worker",
    "docker-compose.yml",
    "docker-compose.monitoring.yml",
    "docker-compose.copilot.yml",
    "docker-compose.loki.yml",
    "docker-compose.windows.yml",
    "pyproject.toml",
    "requirements.txt",
    "requirements-prod.txt",
    "requirements-dev.txt",
    "requirements-minimal.txt",
    "requirements-ml.txt",
    "requirements.hf.txt",
    ".github/workflows/ci-cd.yml",
    ".github/workflows/security.yml",
    ".github/workflows/sync-hf-space.yml",
    ".github/workflows/release.yml",
    "scripts/docker_deploy.sh",
    "scripts/docker_build.sh",
    "scripts/deploy-engineering-service.sh",
    "Makefile",
    "alembic.ini",
    "ruff.toml",
    "nginx.conf",
    "hf-space/Dockerfile",
    "hf-space/app.py",
    "ui/package.json",
    "ui/vite.config.ts",
    "ui/tsconfig.json",
    "mastra.config.ts",
    "pnpm-workspace.yaml",
    "tsconfig.json",
]

# ─── Test files ───────────────────────────────────────────────────────────────
TEST_DIR = "tests"

# ─── Scripts directory ─────────────────────────────────────────────────────────
SCRIPTS_DIR = "scripts"

# ─── Help topics directory ────────────────────────────────────────────────────
HELP_TOPICS_FILE = "ui/src/help/helpTopics.ts"
HELP_CONTEXT_FILE = "ui/src/help/contextRegistry.ts"


def file_hash(path: Path) -> str:
    """Fast content hash for change detection.

    Uses MD5 because it is only a cache key (not a security primitive) —
    the hash is used to detect content changes for re-indexing, not to
    protect against adversaries.
    """
    try:
        content = path.read_bytes()
        return hashlib.md5(content).hexdigest()[:12]  # nosec B324 — non-security cache key
    except Exception:
        return "error"


def extract_python_metadata(path: Path) -> dict:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Extract classes, functions, imports, and docstring from a Python file."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)
    except Exception as e:
        return {"error": str(e), "classes": [], "functions": [], "imports": [], "docstring": ""}

    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not n.name.startswith("_")
            ]
            classes.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "public_methods": methods[:20],
                    "docstring": ast.get_docstring(node) or "",
                },
            )

    functions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                is_async = isinstance(node, ast.AsyncFunctionDef)
                functions.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "async": is_async,
                        "docstring": ast.get_docstring(node) or "",
                    },
                )

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    module_doc = ast.get_docstring(tree) or ""
    return {
        "classes": classes,
        "functions": functions,
        "imports": list(set(imports))[:30],
        "docstring": module_doc[:300],
    }


def extract_api_routes(path: Path) -> list:
    """Extract FastAPI route decorators from an API file."""
    routes = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        pattern = re.compile(r'@\w+\.(get|post|put|delete|patch)\("([^"]+)"', re.IGNORECASE)
        for m in pattern.finditer(content):
            routes.append(
                {
                    "method": m.group(1).upper(),
                    "path": m.group(2),
                },
            )
    except Exception as exc:
        # QUALITY: was `except Exception: pass` — silently swallowed real bugs
        # in the route-extraction regex. Now logged at DEBUG level so the
        # indexer keeps running but failures are visible in verbose mode.
        logger.debug("Failed to extract API routes from %s: %s", path, exc)
    return routes


def scan_python_modules() -> dict:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Scan all Python source directories and build module index."""
    modules = {}
    for dir_name in PYTHON_DIRS:
        dir_path = PROJECT_ROOT / dir_name
        if not dir_path.is_dir():
            continue
        modules[dir_name] = {"description": f"Package: {dir_name}", "files": {}}
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in sorted(files):
                if not fname.endswith(".py"):
                    continue
                fpath = Path(root) / fname
                rel = str(fpath.relative_to(PROJECT_ROOT)).replace("\\", "/")
                meta = extract_python_metadata(fpath)
                api_routes = extract_api_routes(fpath) if dir_name == "api" else []
                entry = {
                    "module": rel.replace("/", ".").replace(".py", ""),
                    "file": rel,
                    "hash": file_hash(fpath),
                    "size_kb": round(fpath.stat().st_size / 1024, 1),
                    "docstring": meta["docstring"],
                    "classes": meta["classes"],
                    "functions": meta["functions"],
                    "imports": meta["imports"],
                }
                if api_routes:
                    entry["api_routes"] = api_routes
                modules[dir_name]["files"][rel] = entry

    return modules


def scan_ui() -> dict:
    """Scan all UI TypeScript/React source directories."""
    ui_index = {}
    for section, dir_path_str in UI_DIRS.items():
        dir_path = PROJECT_ROOT / dir_path_str
        if not dir_path.is_dir():
            continue
        ui_index[section] = {}
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in sorted(files):
                if not fname.endswith((".tsx", ".ts", ".css")):
                    continue
                fpath = Path(root) / fname
                rel = str(fpath.relative_to(PROJECT_ROOT)).replace("\\", "/")
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                # Extract exported components/functions
                exports = re.findall(
                    r"export\s+(?:default\s+)?((?:function|class|const))\s+(\w+)", content,
                )
                props_interfaces = re.findall(r"interface\s+(\w+Props)", content)
                ui_index[section][rel] = {
                    "file": rel,
                    "hash": file_hash(fpath),
                    "size_kb": round(fpath.stat().st_size / 1024, 1),
                    "exports": exports[:15],
                    "prop_interfaces": props_interfaces[:10],
                }
    return ui_index


def scan_tests() -> dict:
    """Scan test directory."""
    test_index = {}
    test_dir = PROJECT_ROOT / TEST_DIR
    if not test_dir.is_dir():
        return test_index
    for root, dirs, files in os.walk(test_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in sorted(files):
            if not fname.endswith(".py") or not fname.startswith("test_"):
                continue
            fpath = Path(root) / fname
            rel = str(fpath.relative_to(PROJECT_ROOT)).replace("\\", "/")
            meta = extract_python_metadata(fpath)
            test_funcs = [f["name"] for f in meta["functions"] if f["name"].startswith("test_")]
            test_classes = [c["name"] for c in meta["classes"] if c["name"].startswith("Test")]
            test_index[rel] = {
                "file": rel,
                "hash": file_hash(fpath),
                "test_functions": test_funcs,
                "test_classes": test_classes,
                "total_tests": len(test_funcs)
                + sum(
                    len([m for m in c["public_methods"] if m.startswith("test_")])
                    for c in meta["classes"]
                ),
            }
    return test_index


def scan_infra() -> dict:
    """Scan infrastructure files."""
    infra = {}
    for rel_path in INFRA_FILES:
        fpath = PROJECT_ROOT / rel_path
        if not fpath.exists():
            continue
        infra[rel_path] = {
            "file": rel_path,
            "hash": file_hash(fpath),
            "size_kb": round(fpath.stat().st_size / 1024, 1),
            "exists": True,
        }
    return infra


def collect_all_api_routes(modules: dict) -> list:
    """Flatten all API routes across all scanned modules."""
    all_routes = []
    for _pkg, pkg_data in modules.items():
        for file_path, file_data in pkg_data.get("files", {}).items():
            for route in file_data.get("api_routes", []):
                all_routes.append(
                    {
                        "method": route["method"],
                        "path": route["path"],
                        "file": file_path,
                    },
                )
    return sorted(all_routes, key=lambda r: r["path"])


def build_stats(modules: dict, ui: dict, tests: dict) -> dict:
    """Build summary statistics."""
    total_py_files = sum(len(p["files"]) for p in modules.values())
    total_classes = sum(len(f["classes"]) for p in modules.values() for f in p["files"].values())
    total_functions = sum(
        len(f["functions"]) for p in modules.values() for f in p["files"].values()
    )
    total_ui_files = sum(len(s) for s in ui.values())
    total_test_files = len(tests)
    total_tests = sum(t["total_tests"] for t in tests.values())
    return {
        "python_packages": len(modules),
        "python_files": total_py_files,
        "python_classes": total_classes,
        "python_functions": total_functions,
        "ui_files": total_ui_files,
        "test_files": total_test_files,
        "total_tests": total_tests,
    }


def scan_help_topics() -> dict:
    """Scan the help topics TypeScript file and extract all topic metadata."""
    fpath = PROJECT_ROOT / HELP_TOPICS_FILE
    if not fpath.exists():
        return {"topics": [], "categories": [], "total": 0}

    content = fpath.read_text(encoding="utf-8", errors="ignore")
    topics = []

    # Match each topic object: { id: '...', category: '...', title: { en: '...', ar: '...' }, ... }
    # Use a non-greedy regex per topic block
    topic_pattern = re.compile(
        r"id:\s*'([^']+)'[^{]*?category:\s*'([^']+)'[^{]*?"
        r"title:\s*\{\s*en:\s*'([^']*)'\s*,\s*ar:\s*'([^']*)'\s*\}[^{]*?"
        r"description:\s*\{\s*en:\s*'([^']*)'\s*,\s*ar:\s*'([^']*)'\s*\}",
        re.DOTALL,
    )
    for m in topic_pattern.finditer(content):
        topic_id = m.group(1)
        category = m.group(2)
        title_en = m.group(3)
        title_ar = m.group(4)
        desc_en = m.group(5)
        desc_ar = m.group(6)

        # Extract tags from the same topic block (look ahead for tags: [...])
        tags_match = re.search(
            rf"id:\s*'{re.escape(topic_id)}'[^]]*?tags:\s*\[([^\]]+)\]",
            content,
            re.DOTALL,
        )
        tags = []
        if tags_match:
            tags = re.findall(r"'([^']+)'", tags_match.group(1))

        # Extract navigateTo
        nav_match = re.search(
            rf"id:\s*'{re.escape(topic_id)}'[^}}]*?navigateTo:\s*'([^']+)'",
            content,
            re.DOTALL,
        )
        navigate_to = nav_match.group(1) if nav_match else None

        # Extract relatedTopics
        rel_match = re.search(
            rf"id:\s*'{re.escape(topic_id)}'[^]]*?relatedTopics:\s*\[([^\]]+)\]",
            content,
            re.DOTALL,
        )
        related = []
        if rel_match:
            related = re.findall(r"'([^']+)'", rel_match.group(1))

        topics.append(
            {
                "id": topic_id,
                "category": category,
                "title": {"en": title_en, "ar": title_ar},
                "description": {"en": desc_en, "ar": desc_ar},
                "tags": tags,
                "navigateTo": navigate_to,
                "relatedTopics": related,
            },
        )

    # Extract categories list
    categories = []
    cat_pattern = re.compile(
        r"id:\s*'([a-z-]+)'\s+as\s+const,\s+label:\s*\{\s*en:\s*'([^']+)'\s*,\s*ar:\s*'([^']+)'\s*\}",
    )
    for m in cat_pattern.finditer(content):
        categories.append(
            {
                "id": m.group(1),
                "label": {"en": m.group(2), "ar": m.group(3)},
            },
        )

    return {
        "topics": topics,
        "categories": categories,
        "total": len(topics),
    }


def scan_context_registry() -> dict:
    """Scan the context registry TypeScript file for context-to-topic mappings."""
    fpath = PROJECT_ROOT / HELP_CONTEXT_FILE
    if not fpath.exists():
        return {"mappings": [], "total": 0}

    content = fpath.read_text(encoding="utf-8", errors="ignore")
    mappings = []

    # Match: { contextId: '...', topicId: '...', priority: N }
    pattern = re.compile(
        r"contextId:\s*'([^']+)'[^}]*?topicId:\s*'([^']+)'(?:[^}]*?priority:\s*(\d+))?",
        re.DOTALL,
    )
    for m in pattern.finditer(content):
        mappings.append(
            {
                "contextId": m.group(1),
                "topicId": m.group(2),
                "priority": int(m.group(3)) if m.group(3) else 1,
            },
        )

    return {"mappings": mappings, "total": len(mappings)}


def scan_env_variables() -> dict:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Scan the .env.example file and Python source for environment variable usage."""
    env_vars = {}

    # 1. Parse .env.example for variable names + comments
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.exists():
        current_section = "General"
        for line in env_example.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                # Capture section headers (lines of # === Text ===)
                if line.startswith("# ===") and "===" in line[5:]:
                    # NOSONAR — python:S8786: bounded by single-line input
                    section_match = re.search(r"#\s*=+\s*([^=]+?)\s*=", line)
                    if section_match:
                        current_section = section_match.group(1).strip()
                continue
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                env_vars[key] = {
                    "name": key,
                    "section": current_section,
                    "default_hint": line.split("=", 1)[1].strip()[:80],
                    "used_in_files": [],
                }

    # 2. Scan Python files for os.getenv / os.environ.get usage
    for dir_name in PYTHON_DIRS + [".", "hf-space"]:
        dir_path = PROJECT_ROOT / dir_name
        if not dir_path.is_dir():
            continue
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = Path(root) / fname
                rel = str(fpath.relative_to(PROJECT_ROOT)).replace("\\", "/")
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                # Find all os.getenv("VAR") and os.environ.get("VAR")
                for m in re.finditer(
                    r'os\.((?:getenv|environ\.get))\(\s*["\']([A-Z_][A-Z0-9_]*)["\']', content,
                ):
                    var_name = m.group(1)
                    if var_name not in env_vars:
                        env_vars[var_name] = {
                            "name": var_name,
                            "section": "Detected in code",
                            "default_hint": "",
                            "used_in_files": [],
                        }
                    if rel not in env_vars[var_name]["used_in_files"]:
                        env_vars[var_name]["used_in_files"].append(rel)

    # 3. Categorize
    sections = {}
    for var in env_vars.values():
        sec = var["section"]
        sections.setdefault(sec, []).append(var["name"])

    return {
        "variables": env_vars,
        "sections": sections,
        "total": len(env_vars),
    }


def scan_scripts() -> dict:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Scan the scripts directory for shell/python/JS scripts."""
    scripts = {}
    scripts_path = PROJECT_ROOT / SCRIPTS_DIR
    if not scripts_path.is_dir():
        return {"files": {}, "total": 0}

    for root, dirs, files in os.walk(scripts_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in sorted(files):
            if not fname.endswith((".sh", ".py", ".mjs", ".js", ".cjs", ".ps1", ".bat")):
                continue
            fpath = Path(root) / fname
            rel = str(fpath.relative_to(PROJECT_ROOT)).replace("\\", "/")
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                # Extract first docstring/comment as description
                desc = ""
                if fname.endswith(".py"):
                    m = re.search(r'^"""(.*?)"""', content, re.DOTALL | re.MULTILINE)
                    if m:
                        desc = m.group(1).strip().split("\n")[0][:120]
                elif fname.endswith((".sh", ".mjs", ".js")):
                    # NOSONAR — python:S8786: .+ is bounded by line content (no nested quantifier)
                    m = re.search(r"^#\s*(.+)$", content, re.MULTILINE)
                    if m:
                        desc = m.group(1).strip()[:120]
            except Exception:
                desc = ""

            scripts[rel] = {
                "file": rel,
                "name": fname,
                "type": fpath.suffix.lstrip("."),
                "hash": file_hash(fpath),
                "size_kb": round(fpath.stat().st_size / 1024, 1),
                "description": desc,
            }

    return {"files": scripts, "total": len(scripts)}


def scan_ai_agents() -> dict:
    """Scan the agents/ directory and extract specialized AI agent metadata."""
    agents = {}
    agents_dir = PROJECT_ROOT / "agents"
    if not agents_dir.is_dir():
        return {"agents": {}, "total": 0}

    for fname in sorted(os.listdir(agents_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = agents_dir / fname
        rel = str(fpath.relative_to(PROJECT_ROOT)).replace("\\", "/")
        meta = extract_python_metadata(fpath)

        # Extract agent class name (usually ends with "Agent")
        agent_classes = [c for c in meta["classes"] if c["name"].endswith("Agent")]

        # Extract the first paragraph of the docstring as description
        doc = meta["docstring"]
        desc = doc.split("\n\n")[0].strip()[:200] if doc else ""

        # Look for standard identifiers in the docstring (ETAP, IEEE, IEC)
        standards = re.findall(r"(((?:IEEE|IEC))\s*\d+(?:[.-]\d+)*)", doc)

        agents[fname] = {
            "file": rel,
            "name": fname.replace("_agent.py", "").replace("_", " ").title(),
            "hash": file_hash(fpath),
            "size_kb": round(fpath.stat().st_size / 1024, 1),
            "description": desc,
            "classes": [c["name"] for c in agent_classes],
            "public_methods": [m for c in agent_classes for m in c["public_methods"][:10]],
            "standards_referenced": list(set(standards)),
            "function_count": len(meta["functions"]),
        }

    return {"agents": agents, "total": len(agents)}


def scan_integrations() -> dict:
    """Scan the integrations/ directory and external service configs."""
    integrations = {}
    int_dir = PROJECT_ROOT / "integrations"
    if int_dir.is_dir():
        for fname in sorted(os.listdir(int_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            fpath = int_dir / fname
            rel = str(fpath.relative_to(PROJECT_ROOT)).replace("\\", "/")
            meta = extract_python_metadata(fpath)
            integrations[fname.replace(".py", "")] = {
                "file": rel,
                "hash": file_hash(fpath),
                "size_kb": round(fpath.stat().st_size / 1024, 1),
                "description": meta["docstring"][:200],
                "classes": [c["name"] for c in meta["classes"]],
                "public_methods": [m for c in meta["classes"] for m in c["public_methods"][:8]],
            }

    # Also list known external service integrations from .env.example
    known_services = []
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.exists():
        content = env_example.read_text(encoding="utf-8", errors="ignore")
        # Look for service sections
        for service in ["HUGGING FACE", "LANGWATCH", "SMITHERY", "GITHUB", "VERCEL"]:
            if service in content.upper():
                known_services.append(service.title())

    return {
        "python_integrations": integrations,
        "external_services": known_services,
        "total": len(integrations),
    }


def build_dependency_graph(modules: dict) -> dict:
    """Build a cross-module dependency graph from imports."""
    graph = {}
    for _pkg_name, pkg_data in modules.items():
        for file_path, file_data in pkg_data.get("files", {}).items():
            # The file's module is its path without .py, with / replaced by .
            # file_module is computed but currently unused — kept for future debug.
            # file_module = file_path.replace("/", ".").replace(".py", "")
            # Get the top-level package this file belongs to
            top_pkg = file_path.split("/")[0]
            graph.setdefault(top_pkg, {"imports": set(), "imported_by": set()})
            for imp in file_data.get("imports", []):
                # Only consider imports of other scanned packages
                imp_top = imp.split(".")[0]
                if imp_top in modules and imp_top != top_pkg:
                    graph[top_pkg]["imports"].add(imp_top)
                    graph.setdefault(imp_top, {"imports": set(), "imported_by": set()})
                    graph[imp_top]["imported_by"].add(top_pkg)

    # Convert sets to sorted lists for JSON
    return {
        pkg: {
            "imports": sorted(data["imports"]),
            "imported_by": sorted(data["imported_by"]),
        }
        for pkg, data in graph.items()
    }


def build_ui_search_index(help_data: dict, modules: dict, ui: dict, api_routes: list) -> dict:
    """Build a flat search index for the UI command palette and help drawer.

    Each entry has: type, id, title (en/ar), description (en/ar), tags, navigateTo
    Types: 'help-topic', 'api-route', 'ui-page', 'ui-component', 'python-module'
    """
    entries = []

    # 1. Help topics
    for topic in help_data.get("topics", []):
        entries.append(
            {
                "type": "help-topic",
                "id": topic["id"],
                "title": topic["title"],
                "description": topic["description"],
                "tags": topic["tags"],
                "navigateTo": topic["navigateTo"],
            },
        )

    # 2. API routes
    for route in api_routes:
        entries.append(
            {
                "type": "api-route",
                "id": f"{route['method']} {route['path']}",
                "title": {
                    "en": f"{route['method']} {route['path']}",
                    "ar": f"{route['method']} {route['path']}",
                },
                "description": {
                    "en": f"API endpoint in {route['file']}",
                    "ar": f"نقطة API في {route['file']}",
                },
                "tags": ["api", "endpoint", route["method"].lower()],
                "navigateTo": None,
            },
        )

    # 3. UI pages
    for rel_path, file_data in ui.get("pages", {}).items():
        page_name = rel_path.split("/")[-1].replace(".tsx", "")
        entries.append(
            {
                "type": "ui-page",
                "id": page_name,
                "title": {"en": page_name, "ar": page_name},
                "description": {"en": f"UI page at {rel_path}", "ar": f"صفحة UI في {rel_path}"},
                "tags": ["page", "ui", page_name.lower()],
                "navigateTo": f"/{page_name.lower()}",
                "exports": file_data.get("exports", []),
            },
        )

    # 4. UI components
    for section, files in ui.items():
        if section == "pages":
            continue
        for rel_path, file_data in files.items():
            # comp_name is the basename without extension; not currently used
            # in the entry below but useful for debugging.
            # comp_name = rel_path.split("/")[-1].replace(".tsx", "").replace(".ts", "")
            for export in file_data.get("exports", []):
                entries.append(
                    {
                        "type": "ui-component",
                        "id": export,
                        "title": {"en": export, "ar": export},
                        "description": {
                            "en": f"{section} component in {rel_path}",
                            "ar": f"مكون {section} في {rel_path}",
                        },
                        "tags": ["component", "ui", section, export.lower()],
                        "navigateTo": None,
                    },
                )

    # 5. Python modules (top-level packages)
    for pkg_name in modules:
        entries.append(
            {
                "type": "python-module",
                "id": pkg_name,
                "title": {"en": pkg_name, "ar": pkg_name},
                "description": {
                    "en": f"Python package: {pkg_name}/",
                    "ar": f"حزمة Python: {pkg_name}/",
                },
                "tags": ["python", "module", "package", pkg_name],
                "navigateTo": None,
            },
        )

    return {
        "entries": entries,
        "total": len(entries),
        "by_type": {
            t: sum(1 for e in entries if e["type"] == t) for t in {e["type"] for e in entries}
        },
    }


def generate_markdown(index: dict) -> str:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Generate a rich human-readable Markdown index."""
    now = index["meta"]["generated_at"]
    stats = index["stats"]
    lines = [
        "# 📘 AhmedETAP — Complete Project Index v2.0.0",
        "",
        f"> Auto-generated on **{now}** by indexer v{index['meta']['indexer_version']}.",
        "> Re-run `python indexer.py` to refresh.",
        "",
        "---",
        "",
        "## 📊 Project Statistics",
        "",
        "| Metric | Count |",
        "|:---|---:|",
        f"| Python Packages | {stats['python_packages']} |",
        f"| Python Files | {stats['python_files']} |",
        f"| Python Classes | {stats['python_classes']} |",
        f"| Python Functions | {stats['python_functions']} |",
        f"| UI Files (TSX/TS) | {stats['ui_files']} |",
        f"| Test Files | {stats['test_files']} |",
        f"| Total Tests | {stats['total_tests']} |",
        f"| Help Topics | {stats.get('help_topics', 0)} |",
        f"| Context Mappings | {stats.get('context_mappings', 0)} |",
        f"| Environment Variables | {stats.get('env_variables', 0)} |",
        f"| Scripts | {stats.get('scripts', 0)} |",
        f"| AI Agents | {stats.get('ai_agents', 0)} |",
        f"| Integrations | {stats.get('integrations', 0)} |",
        f"| UI Search Index Entries | {stats.get('ui_search_index_entries', 0)} |",
        "",
        "---",
        "",
        "## 🤖 AI Agents",
        "",
        "| Agent | File | Standards | Description |",
        "|:---|:---|:---|:---|"
    ]
    agents = index.get("ai_agents", {}).get("agents", {})
    for fname, a in sorted(agents.items()):
        stds = ", ".join(a.get("standards_referenced", [])) or "—"
        desc = a.get("description", "").replace(", ", "\\, ").replace("\n", " ")[:60]
        lines.append(f"| **{a['name']}** (`{fname}`) | {stds} | {desc} |"),

    lines += [
        "",
        "---",
        "",
        "## 🔌 Integrations",
        "",
    ]
    integ = index.get("integrations", {})
    if integ.get("python_integrations"):
        lines.append("**Python integration modules:**")
        lines.append("")
        for name, idata in integ["python_integrations"].items():
            classes = ", ".join(f"`{c}`" for c in idata.get("classes", [])) or "_none_"
            lines.append(f"- **`{name}`** ({idata['size_kb']} KB) — classes: {classes}")
        lines.append("")
    if integ.get("external_services"):
        lines.append("**External services configured:**")
        lines.append("")
        for svc in integ["external_services"]:
            lines.append(f"- {svc}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 📚 Help Topics",
        "",
        f"Total: **{index.get('help_topics', {}).get('total', 0)}** topics across {len(index.get('help_topics', {}).get('categories', []))} categories",
        "",
        "| Topic ID | Category | Title (EN) | Title (AR) | Tags |",
        "|:---|:---|:---|:---|:---|"
    ]
    for t in index.get("help_topics", {}).get("topics", []):
        tags = ", ".join(f"`{tag}`" for tag in t.get("tags", [])[:5])
        lines.append(
            f"| `{t['id']}` | {t['category']} | {t['title']['en']} | {t['title']['ar']} | {tags} |",
        )

    lines += [
        "",
        "---",
        "",
        "## 🔗 Context Registry (UI → Help Topic mappings)",
        "",
        f"Total: **{index.get('context_registry', {}).get('total', 0)}** mappings",
        "",
        "| Context ID | Help Topic ID | Priority |",
        "|:---|:---|---:|"
    ]
    for m in index.get("context_registry", {}).get("mappings", []):
        lines.append(f"| `{m['contextId']}` | `{m['topicId']}` | {m.get('priority', 1)} |"),

    lines += [
        "",
        "---",
        "",
        "## 🔐 Environment Variables",
        "",
        f"Total: **{index.get('environment_variables', {}).get('total', 0)}** variables",
        "",
    ]
    env_sections = index.get("environment_variables", {}).get("sections", {})
    for section, vars in env_sections.items():
        lines.append(f"### {section}")
        lines.append("")
        for var in sorted(vars):
            lines.append(f"- `{var}`")
        lines.append("")

    lines += [
        "---",
        "",
        "## 🗂️ Python Modules & Packages",
        "",
    ]

    for pkg_name, pkg_data in index["python_modules"].items():
        lines.append(f"### 📦 `{pkg_name}/`")
        lines.append("")
        for rel_path, file_data in pkg_data["files"].items():
            lines.append(f"#### 📄 `{rel_path}` _{file_data['size_kb']} KB_")
            if file_data.get("docstring"):
                lines.append(f"> {file_data['docstring'][:150]}")
                lines.append("")
            if file_data.get("classes"):
                for cls in file_data["classes"]:
                    methods_str = ", ".join(f"`{m}()`" for m in cls["public_methods"][:8])
                    lines.append(f"- **Class** `{cls['name']}` (line {cls['line']})")
                    if methods_str:
                        lines.append(f"  - Methods: {methods_str}")
            if file_data.get("functions"):
                for fn in file_data["functions"][:10]:
                    amark = "async " if fn["async"] else ""
                    lines.append(f"- **{amark}def** `{fn['name']}()` (line {fn['line']})")
            if file_data.get("api_routes"):
                lines.append("")
                lines.append("  **API Routes:**")
                for route in file_data["api_routes"]:
                    lines.append(f"  - `{route['method']} {route['path']}`")
            lines.append("")

    lines += [
        "---",
        "",
        "## 🌐 All API Endpoints",
        "",
        "| Method | Path | File |",
        "|:---|:---|:---|",
    ]
    for route in index["api_routes"]:
        method = route["method"]
        badge = {
            "GET": "🟢",
            "POST": "🔵",
            "PUT": "🟡",
            "DELETE": "🔴",
            "PATCH": "🟠",
            "WS": "🟣",
        }.get(method, "⚪")
        lines.append(f"| {badge} `{method}` | `{route['path']}` | `{route['file']}` |"),

    lines += [
        "",
        "---",
        "",
        "## ⚛️ UI Components & Pages",
        "",
    ]
    for section, files in index["ui_modules"].items():
        lines.append(f"### 🖥️ `{section}/`")
        for rel_path, file_data in files.items():
            exports_str = ", ".join(f"`{e}`" for e in file_data["exports"]) or "_none_"
            lines.append(f"- `{rel_path.split('/')[-1]}` → Exports: {exports_str}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 🔍 UI Search Index Summary",
        "",
        "| Type | Count |"
        "|:---|---:|"
    ]
    search_summary = index.get("ui_search_index_summary", {})
    for t, count in search_summary.get("by_type", {}).items():
        lines.append(f"| {t} | {count} | ")
    lines.append(f"| **TOTAL** | **{search_summary.get('total', 0)}** |")

    lines += [
        "",
        "---",
        "",
        "## 🔀 Dependency Graph (Cross-Package Imports)",
        "",
        "| Package | Imports | Imported By |",
        "|:---|:---|:---|"
    ]
    for pkg, edges in sorted(index.get("dependency_graph", {}).items()):
        imports = ", ".join(f"`{p}`" for p in edges["imports"]) or "—"
        imported_by = ", ".join(f"`{p}`" for p in edges["imported_by"]) or "—"
        lines.append(f"| `{pkg}` | {imports} | {imported_by} |")

    lines += [
        "",
        "---",
        "",
        "## 🧪 Test Suite",
        "",
        "| Test File | Test Functions | Test Classes | Total |",
        "|:---|---:|---:|---:|"
    ]
    for path, t in index["tests"].items():
        fname = path.split("/")[-1]
        lines.append(
            f"| `{fname}` | {len(t['test_functions'])} | {len(t['test_classes'])} | **{t['total_tests']}** |"
        )

    lines += [
        "",
        "---",
        "",
        "## 🛠️ Scripts",
        "",
        "| Script | Type | Size | Description |",
        "|:---|:---|---:|:---|"
    ]
    for rel, s in sorted(index.get("scripts", {}).get("files", {}).items()):
        desc = s.get("description", "").replace(", ", "\\, ")[:60]
        lines.append(f"| `{rel}` | {s['type']} | {s['size_kb']} KB | {desc} |")

    lines += [
        "",
        "---",
        "",
        "## 🏗️ Infrastructure Files",
        "",
        "| File | Size | Hash |",
        "|:---|---:|:---|"
    ]
    for rel_path, idata in index["infrastructure"].items():
        lines.append(f"| `{rel_path}` | {idata['size_kb']} KB | `{idata['hash']}` |")

    lines += [
        "",
        "---",
        "",
        "## 🔄 How to Refresh This Index",
        "",
        "```bash",
        "python indexer.py",
        "```",
        "",
        "The indexer scans the entire codebase and regenerates:",
        "- `PROJECT_INDEX.json` — full structured JSON index (machine-readable)",
        "- `PROJECT_INDEX.md` — this human-readable Markdown view",
        "- `ui/src/help/search-index.json` — flat search index consumed by the UI",
        "  command palette and the Smart Help drawer",
        "",
        "Each file's content hash is captured so you can detect drift between",
        "the index and the actual codebase. Re-run after major changes.",
    ]

    return "\n".join(lines)


def main():
    print("[INFO] Starting AhmedETAP Project Indexer v2.0.0...")
    print()

    print("[1/11] Scanning Python modules...")
    modules = scan_python_modules()

    print("[2/11] Scanning UI components...")
    ui = scan_ui()

    print("[3/11] Scanning test suite...")
    tests = scan_tests()

    print("[4/11] Scanning infrastructure files...")
    infra = scan_infra()

    print("[5/11] Scanning help topics...")
    help_topics = scan_help_topics()

    print("[6/11] Scanning context registry...")
    context_registry = scan_context_registry()

    print("[7/11] Scanning environment variables...")
    env_vars = scan_env_variables()

    print("[8/11] Scanning scripts directory...")
    scripts = scan_scripts()

    print("[9/11] Scanning AI agents...")
    agents = scan_ai_agents()

    print("[10/11] Scanning integrations...")
    integrations = scan_integrations()

    print("[11/11] Building dependency graph + UI search index...")
    dependency_graph = build_dependency_graph(modules)
    all_routes = collect_all_api_routes(modules)
    ui_search_index = build_ui_search_index(help_topics, modules, ui, all_routes)

    # Update stats with new counts
    stats = build_stats(modules, ui, tests)
    stats["help_topics"] = help_topics["total"]
    stats["context_mappings"] = context_registry["total"]
    stats["env_variables"] = env_vars["total"]
    stats["scripts"] = scripts["total"]
    stats["ai_agents"] = agents["total"]
    stats["integrations"] = integrations["total"]
    stats["ui_search_index_entries"] = ui_search_index["total"]

    # Read VERSION file via context manager (avoids file-descriptor leak).
    _version_str = "unknown"
    if Path("VERSION").exists():
        with open("VERSION", encoding="utf-8") as _vf:
            _version_str = _vf.read().strip()

    index = {
        "meta": {
            "project": "AhmedETAP — Power Systems Engineering AI Platform",
            "version": _version_str,
            "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "indexer_version": "2.0.0",
            "total_api_routes": len(all_routes),
            "total_help_topics": help_topics["total"],
            "total_env_vars": env_vars["total"],
            "total_ai_agents": agents["total"],
            "total_integrations": integrations["total"],
            "total_scripts": scripts["total"],
        },
        "stats": stats,
        "python_modules": modules,
        "api_routes": all_routes,
        "ui_modules": ui,
        "tests": tests,
        "infrastructure": infra,
        "help_topics": help_topics,
        "context_registry": context_registry,
        "environment_variables": env_vars,
        "scripts": scripts,
        "ai_agents": agents,
        "integrations": integrations,
        "dependency_graph": dependency_graph,
        "ui_search_index_summary": {
            "total": ui_search_index["total"],
            "by_type": ui_search_index["by_type"],
        },
    }

    # Write JSON index
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print()
    print(f"[OK] JSON index written to: {INDEX_FILE} ({INDEX_FILE.stat().st_size // 1024} KB)")

    # Write UI search index (consumed by the command palette + help drawer)
    UI_SEARCH_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with open(UI_SEARCH_INDEX, "w", encoding="utf-8") as f:
        json.dump(ui_search_index, f, indent=2, ensure_ascii=False)
    print(
        f"[OK] UI search index written to: {UI_SEARCH_INDEX} ({UI_SEARCH_INDEX.stat().st_size // 1024} KB)",
    )

    # Write Markdown index
    md_content = generate_markdown(index)
    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[OK] Markdown index written to: {MD_FILE} ({MD_FILE.stat().st_size // 1024} KB)")

    print()
    print("=" * 70)
    print("  AhmedETAP Project Index v2.0.0 — Summary")
    print("=" * 70)
    for k, v in stats.items():
        print(f"  {k:<30}: {v}")
    print(f"  {'api_routes':<30}: {len(all_routes)}")
    print(f"  {'ui_search_index_entries':<30}: {ui_search_index['total']}")
    print("=" * 70)
    print("[SUCCESS] Indexing complete.")


if __name__ == "__main__":
    main()
