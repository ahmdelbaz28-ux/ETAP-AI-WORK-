"""
AI Context Engine - Knowledge Graph
Implements Phase 3: Explicit code relationships and dependency mapping (Code Property Graph).
"""

import ast
import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_context_engine_kg")


class KnowledgeGraph:
    """In-memory Code Property Graph for impact analysis and dependency mapping."""

    def __init__(self):
        self.nodes = {}  # node_id -> {label, properties}
        self.edges = []  # list of {source, relationship, target, properties}
        self.adj = {}  # adjacency list: source -> list of (target, relationship)

    def add_node(self, node_id: str, label: str, properties: dict = None) -> None:
        """Add a component node to the graph."""
        self.nodes[node_id] = {"label": label, "properties": properties or {}}
        if node_id not in self.adj:
            self.adj[node_id] = []

    def add_relationship(
        self, source: str, relationship: str, target: str, properties: dict = None,
    ) -> None:
        """Add a directed relationship between two components."""
        # Ensure nodes exist
        if source not in self.nodes:
            self.add_node(source, "unknown")
        if target not in self.nodes:
            self.add_node(target, "unknown")

        edge = {
            "source": source,
            "relationship": relationship,
            "target": target,
            "properties": properties or {},
        }
        self.edges.append(edge)
        self.adj[source].append((target, relationship))

    def get_neighbors(self, node_id: str) -> list[tuple[str, str]]:
        """Returns adjacent nodes and their relationship types."""
        return self.adj.get(node_id, [])

    def find_path(self, start: str, end: str, max_depth: int = 5) -> list[list[tuple[str, str]]]:
        """Find paths between two nodes up to max_depth."""
        if start not in self.nodes or end not in self.nodes:
            return []

        paths = []
        queue = [[(start, "start")]]

        while queue:
            current_path = queue.pop(0)
            current_node, _ = current_path[-1]

            if current_node == end:
                paths.append(current_path)
                continue

            if len(current_path) > max_depth:
                continue

            for neighbor, rel in self.get_neighbors(current_node):
                # Avoid cycles
                visited_nodes = {node for node, _ in current_path}
                if neighbor not in visited_nodes:
                    new_path = list(current_path)
                    new_path.append((neighbor, rel))
                    queue.append(new_path)

        return paths

    def generate_impact_subgraph(self, start_node: str, max_depth: int = 2) -> dict:
        """
        Traverses downstream dependencies to find all components impacted
        by a change in start_node (DFS/BFS limit traversal).
        """
        visited = {}
        queue = [(start_node, 0)]

        impacted_nodes = {}
        impacted_edges = []

        while queue:
            node, depth = queue.pop(0)
            if node in visited and visited[node] <= depth:
                continue

            visited[node] = depth
            impacted_nodes[node] = self.nodes.get(node, {"label": "unknown", "properties": {}})

            if depth < max_depth:
                for neighbor, rel in self.get_neighbors(node):
                    impacted_edges.append({"source": node, "relationship": rel, "target": neighbor})
                    queue.append((neighbor, depth + 1))

        return {"nodes": impacted_nodes, "edges": impacted_edges}

    def scan_file_for_relations(self, filepath: Path, repo_root: Path) -> None:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Parse file imports and class structure using AST to populate the graph."""
        try:
            with open(filepath, encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(filepath))
            rel_path = filepath.relative_to(repo_root).as_posix()
            file_node_id = f"file:{rel_path}"

            self.add_node(file_node_id, "file", {"path": rel_path})

            for node in ast.walk(tree):
                # Detect Imports
                if isinstance(node, ast.Import):
                    for name in node.names:
                        target = f"module:{name.name}"
                        self.add_node(target, "module")
                        self.add_relationship(file_node_id, "imports", target)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        target = f"module:{node.module}"
                        self.add_node(target, "module")
                        self.add_relationship(file_node_id, "imports", target)

                # Detect Class Declarations and Inheritances
                elif isinstance(node, ast.ClassDef):
                    class_node_id = f"{rel_path}::{node.name}"
                    self.add_node(class_node_id, "class", {"name": node.name, "filepath": rel_path})
                    self.add_relationship(file_node_id, "defines", class_node_id)

                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            # Simple base class name reference
                            parent_id = f"class_ref:{base.id}"
                            self.add_node(parent_id, "class_reference")
                            self.add_relationship(class_node_id, "inherits_from", parent_id)

                # Detect Functions
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_node_id = f"{rel_path}::{node.name}"
                    self.add_node(
                        func_node_id, "function", {"name": node.name, "filepath": rel_path},
                    )
                    self.add_relationship(file_node_id, "defines", func_node_id)

        except Exception as e:
            logger.exception("Failed to scan %s for KG: %s", filepath, e)

    def resolve_references(self) -> None:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Resolve module imports and class references to their actual file and class nodes."""
        # 1. Map class name to class node ID
        class_name_to_id = {}
        for node_id, node_data in self.nodes.items():
            if node_data.get("label") == "class":
                class_name = node_data.get("properties", {}).get("name")
                if class_name:
                    class_name_to_id[class_name] = node_id

        # 2. Map module name to file path/node ID
        module_to_file_id = {}
        for node_id, node_data in self.nodes.items():
            if node_data.get("label") == "file":
                filepath_str = node_data.get("properties", {}).get("path", "")
                if filepath_str.endswith(".py"):
                    # Convert "api/shared_handlers.py" -> "api.shared_handlers"
                    mod_path = filepath_str[:-3].replace("/", ".")
                    module_to_file_id[mod_path] = node_id
                    # Also support simple name mapping for root/relative modules
                    simple_name = Path(filepath_str).stem
                    module_to_file_id[simple_name] = node_id

        # 3. Resolve class_reference nodes
        for node_id, node_data in self.nodes.items():
            if node_data.get("label") == "class_reference":
                # ID is "class_ref:ClassName"
                class_name = node_id.split(":", 1)[1] if ":" in node_id else node_id
                if class_name in class_name_to_id:
                    target_id = class_name_to_id[class_name]
                    self.add_relationship(node_id, "resolves_to", target_id)

        # 4. Resolve module nodes
        for node_id, node_data in self.nodes.items():
            if node_data.get("label") == "module":
                # ID is "module:mod_name"
                mod_name = node_id.split(":", 1)[1] if ":" in node_id else node_id
                # Check direct match
                if mod_name in module_to_file_id:
                    target_id = module_to_file_id[mod_name]
                    self.add_relationship(node_id, "resolves_to", target_id)
                else:
                    # Check if it's a sub-module or parent module match
                    for m_name, file_id in module_to_file_id.items():
                        if mod_name.startswith(m_name + ".") or m_name.startswith(mod_name + "."):
                            self.add_relationship(node_id, "resolves_to", file_id)
                            break

    def scan_repo(self, repo_path: str) -> None:
        """Scan entire repository to build a Code Property Graph."""
        repo_dir = Path(repo_path)
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("venv", "node_modules", "__pycache__", "index")
            ]
            for file in files:
                if file.endswith(".py"):
                    self.scan_file_for_relations(Path(root) / file, repo_dir)
        self.resolve_references()

    def to_json(self) -> str:
        """Serialize graph to JSON string."""
        return json.dumps({"nodes": self.nodes, "edges": self.edges}, indent=2)

    def from_json(self, data_str: str) -> None:
        """Load graph from JSON string."""
        data = json.loads(data_str)
        self.nodes = data.get("nodes", {})
        self.edges = data.get("edges", [])

        # Re-build adjacency list
        self.adj = {node_id: [] for node_id in self.nodes}
        for edge in self.edges:
            src = edge["source"]
            tgt = edge["target"]
            rel = edge["relationship"]
            if src not in self.adj:
                self.adj[src] = []
            self.adj[src].append((tgt, rel))
