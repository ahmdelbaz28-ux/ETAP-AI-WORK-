"""
Professional Project Indexer for AhmedETAP
Generates a full structured JSON index of the codebase.
Can be re-run any time to refresh the index incrementally.

Usage:
  python indexer.py              # Full scan — generates PROJECT_INDEX.json + PROJECT_INDEX.md

Auto-update:
  The .github/workflows/auto-index.yml workflow re-runs this script
  on every push to main and commits the updated index files automatically.
"""
import os
import re
import ast
import json
import hashlib
import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(".")
OUTPUT_DIR = PROJECT_ROOT
INDEX_FILE = OUTPUT_DIR / "PROJECT_INDEX.json"
MD_FILE = OUTPUT_DIR / "PROJECT_INDEX.md"

# ─── Directories to scan for Python modules ─────────────────────────────────
PYTHON_DIRS = [
    "agents", "api", "core", "engine", "fault_analysis", "load_flow",
    "services", "security", "ml", "worker", "reporting", "digital_twin",
    "network_solver", "coordination", "relays", "adms_control", "utils",
    "guards", "copilot", "schemas", "migrations", "etap_integration",
    "core_model", "scada_model", "acp_runtime"
]

# ─── UI pages and components ─────────────────────────────────────────────────
UI_DIRS = {
    "pages": "ui/src/pages",
    "components": "ui/src/components",
    "hooks": "ui/src/hooks",
    "store": "ui/src/store",
    "context": "ui/src/context",
    "utils": "ui/src/utils",
}

# ─── Infrastructure files ─────────────────────────────────────────────────────
INFRA_FILES = [
    "Dockerfile", "Dockerfile.engineering-service", "Dockerfile.hf",
    "docker-compose.yml", "docker-compose.monitoring.yml",
    "docker-compose.copilot.yml", "pyproject.toml", "requirements.txt",
    "requirements-prod.txt", "requirements-dev.txt", ".github/workflows/ci-cd.yml",
    ".github/workflows/security.yml", ".github/workflows/sync-hf-space.yml",
    ".github/workflows/release.yml", "scripts/docker_deploy.sh",
    "scripts/docker_build.sh", "scripts/deploy-engineering-service.sh",
    "Makefile", "alembic.ini", "ruff.toml",
]

# ─── Test files ───────────────────────────────────────────────────────────────
TEST_DIR = "tests"


def file_hash(path: Path) -> str:
    """Fast content hash for change detection."""
    try:
        content = path.read_bytes()
        return hashlib.md5(content).hexdigest()[:12]
    except Exception:
        return "error"


def extract_python_metadata(path: Path) -> dict:
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
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not n.name.startswith("_")
            ]
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "public_methods": methods[:20],
                "docstring": ast.get_docstring(node) or ""
            })

    functions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                is_async = isinstance(node, ast.AsyncFunctionDef)
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "async": is_async,
                    "docstring": ast.get_docstring(node) or ""
                })

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
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
        pattern = re.compile(
            r'@\w+\.(get|post|put|delete|patch)\("([^"]+)"', re.IGNORECASE
        )
        for m in pattern.finditer(content):
            routes.append({
                "method": m.group(1).upper(),
                "path": m.group(2),
            })
    except Exception:
        pass
    return routes


def scan_python_modules() -> dict:
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
                exports = re.findall(r'export\s+(?:default\s+)?(?:function|class|const)\s+(\w+)', content)
                props_interfaces = re.findall(r'interface\s+(\w+Props)', content)
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
            test_funcs = [
                f["name"] for f in meta["functions"]
                if f["name"].startswith("test_")
            ]
            test_classes = [c["name"] for c in meta["classes"] if c["name"].startswith("Test")]
            test_index[rel] = {
                "file": rel,
                "hash": file_hash(fpath),
                "test_functions": test_funcs,
                "test_classes": test_classes,
                "total_tests": len(test_funcs) + sum(
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
    for pkg, pkg_data in modules.items():
        for file_path, file_data in pkg_data.get("files", {}).items():
            for route in file_data.get("api_routes", []):
                all_routes.append({
                    "method": route["method"],
                    "path": route["path"],
                    "file": file_path,
                })
    return sorted(all_routes, key=lambda r: r["path"])


def build_stats(modules: dict, ui: dict, tests: dict) -> dict:
    """Build summary statistics."""
    total_py_files = sum(len(p["files"]) for p in modules.values())
    total_classes = sum(
        len(f["classes"])
        for p in modules.values()
        for f in p["files"].values()
    )
    total_functions = sum(
        len(f["functions"])
        for p in modules.values()
        for f in p["files"].values()
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


def generate_markdown(index: dict) -> str:
    """Generate a rich human-readable Markdown index."""
    now = index["meta"]["generated_at"]
    stats = index["stats"]
    lines = [
        "# 📘 AhmedETAP — Complete Project Index",
        "",
        f"> Auto-generated on **{now}**. Re-run `python indexer.py` to refresh.",
        "",
        "---",
        "",
        "## 📊 Project Statistics",
        "",
        f"| Metric | Count |",
        f"|:---|---:|",
        f"| Python Packages | {stats['python_packages']} |",
        f"| Python Files | {stats['python_files']} |",
        f"| Python Classes | {stats['python_classes']} |",
        f"| Python Functions | {stats['python_functions']} |",
        f"| UI Files (TSX/TS) | {stats['ui_files']} |",
        f"| Test Files | {stats['test_files']} |",
        f"| Total Tests | {stats['total_tests']} |",
        "",
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
        badge = {"GET": "🟢", "POST": "🔵", "PUT": "🟡", "DELETE": "🔴", "PATCH": "🟠"}.get(method, "⚪")
        lines.append(f"| {badge} `{method}` | `{route['path']}` | `{route['file']}` |")

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
        "## 🧪 Test Suite",
        "",
        "| Test File | Test Functions | Test Classes | Total |",
        "|:---|---:|---:|---:|",
    ]
    for path, t in index["tests"].items():
        fname = path.split("/")[-1]
        lines.append(f"| `{fname}` | {len(t['test_functions'])} | {len(t['test_classes'])} | **{t['total_tests']}** |")

    lines += [
        "",
        "---",
        "",
        "## 🏗️ Infrastructure Files",
        "",
        "| File | Size | Hash |",
        "|:---|---:|:---|",
    ]
    for rel_path, idata in index["infrastructure"].items():
        lines.append(f"| `{rel_path}` | {idata['size_kb']} KB | `{idata['hash']}` |")

    lines += [
        "",
        "---",
        "",
        "> **How to update this index:** Run `python indexer.py` from the project root.",
        "> The index captures content hashes for each file — only changed files need re-inspection.",
    ]

    return "\n".join(lines)


def main():
    print("[INFO] Starting AhmedETAP Project Indexer...")
    print("[INFO] Scanning Python modules...")
    modules = scan_python_modules()

    print("[INFO] Scanning UI components...")
    ui = scan_ui()

    print("[INFO] Scanning test suite...")
    tests = scan_tests()

    print("[INFO] Scanning infrastructure files...")
    infra = scan_infra()

    all_routes = collect_all_api_routes(modules)
    stats = build_stats(modules, ui, tests)

    index = {
        "meta": {
            "project": "AhmedETAP — Power Systems Engineering AI Platform",
            "version": open("VERSION", encoding="utf-8").read().strip() if Path("VERSION").exists() else "unknown",
            "generated_at": datetime.datetime.now(timezone.utc).isoformat(),

            "indexer_version": "1.0.0",
            "total_api_routes": len(all_routes),
        },
        "stats": stats,
        "python_modules": modules,
        "api_routes": all_routes,
        "ui_modules": ui,
        "tests": tests,
        "infrastructure": infra,
    }

    # Write JSON index
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"[OK] JSON index written to: {INDEX_FILE} ({INDEX_FILE.stat().st_size // 1024} KB)")

    # Write Markdown index
    md_content = generate_markdown(index)
    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[OK] Markdown index written to: {MD_FILE} ({MD_FILE.stat().st_size // 1024} KB)")

    print()
    print("=" * 60)
    print("  AhmedETAP Project Index — Summary")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k:<30}: {v}")
    print(f"  {'api_routes':<30}: {len(all_routes)}")
    print("=" * 60)
    print("[SUCCESS] Indexing complete.")


if __name__ == "__main__":
    main()
