"""
AI Context Engine - Code Indexer
Implements Phase 1: Indexing with Tree-Sitter (or AST fallback) and ChromaDB.
"""

import argparse
import ast
import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_context_engine")

# ---------------------------------------------------------------------------
# Optional Dependencies (Graceful Degradation)
# ---------------------------------------------------------------------------
try:
    import chromadb

    CHROMA_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    CHROMA_AVAILABLE = False
    logger.warning(f"chromadb not available ({e}). Vector storage disabled.")

try:
    import tree_sitter  # noqa: F401 — imported for the side-effect of being available
    import tree_sitter_python  # noqa: F401
    from tree_sitter import Language, Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter or tree-sitter-python not installed. Falling back to built-in AST.")


class CodeExtractor:
    """Extracts classes and functions from Python code using Tree-sitter or AST."""

    @staticmethod
    def extract_with_ast(filepath: Path) -> List[Dict]:
        """Fallback extractor using standard library AST (100% reliable for Python)."""
        chunks = []
        try:
            with open(filepath, encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(filepath))
            lines = source.splitlines()

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start = node.lineno - 1
                    # AST end_lineno is available in Python 3.8+
                    end = getattr(node, "end_lineno", len(lines))
                    chunk_code = "\n".join(lines[start:end])

                    chunks.append(
                        {
                            "name": node.name,
                            "type": "class" if isinstance(node, ast.ClassDef) else "function",
                            "filepath": str(filepath),
                            "code": chunk_code,
                        }
                    )
        except Exception as e:
            logger.error(f"AST Error in {filepath}: {e}")
        return chunks

    @staticmethod
    def extract_with_tree_sitter(filepath: Path) -> List[Dict]:
        """Primary extractor using Tree-sitter."""
        chunks = []
        try:
            PY_LANGUAGE = Language(tree_sitter_python.language())
            parser = Parser(PY_LANGUAGE)

            with open(filepath, "rb") as f:
                source_bytes = f.read()

            tree = parser.parse(source_bytes)

            def traverse(node):
                if node.type in ("function_definition", "class_definition"):
                    name_node = node.child_by_field_name("name")
                    name = (
                        source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                        if name_node
                        else "unknown"
                    )
                    code = source_bytes[node.start_byte : node.end_byte].decode("utf-8")

                    chunks.append(
                        {
                            "name": name,
                            "type": "class" if node.type == "class_definition" else "function",
                            "filepath": str(filepath),
                            "code": code,
                        }
                    )
                for child in node.children:
                    traverse(child)

            traverse(tree.root_node)
        except Exception as e:
            logger.error(f"Tree-sitter Error in {filepath}: {e}")

        return chunks

    @classmethod
    def extract(cls, filepath: Path) -> List[Dict]:
        """Extract chunks using the best available method."""
        if TREE_SITTER_AVAILABLE:
            return cls.extract_with_tree_sitter(filepath)
        else:
            return cls.extract_with_ast(filepath)


class CodeIndexer:
    def __init__(self, output_dir: str, embedding_function=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = None
        self.collection = None

        if CHROMA_AVAILABLE:
            self.client = chromadb.PersistentClient(path=str(self.output_dir))
            self.collection = self.client.get_or_create_collection(
                name="code_context", embedding_function=embedding_function
            )

    def hash_code(self, code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def index_repo(self, repo_path: str):
        repo_dir = Path(repo_path)
        total_chunks = 0

        logger.info(f"Scanning repository: {repo_dir.absolute()}")
        for root, dirs, files in os.walk(repo_dir):
            # Prune hidden dirs, venvs, and node_modules
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("venv", "node_modules", "__pycache__", "index")
            ]

            for file in files:
                if file.endswith(".py"):
                    filepath = Path(root) / file
                    chunks = CodeExtractor.extract(filepath)

                    if chunks and self.collection:
                        ids = []
                        documents = []
                        metadatas = []

                        for chunk in chunks:
                            chunk_id = f"{chunk['filepath']}::{chunk['name']}"
                            # Add a hash to avoid re-indexing unchanged code later
                            chunk_hash = self.hash_code(chunk["code"])

                            ids.append(chunk_id)
                            documents.append(chunk["code"])
                            metadatas.append(
                                {
                                    "name": chunk["name"],
                                    "type": chunk["type"],
                                    "filepath": chunk["filepath"],
                                    "hash": chunk_hash,
                                }
                            )

                        # Upsert automatically handles inserts and updates
                        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                    total_chunks += len(chunks)

        logger.info(f"Indexing complete. Extracted {total_chunks} code chunks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Context Engine - Indexer")
    parser.add_argument("--repo", type=str, default=".", help="Path to the repository to index")
    parser.add_argument(
        "--output", type=str, default="./index/", help="Path to save the ChromaDB index"
    )
    args = parser.parse_args()

    indexer = CodeIndexer(args.output)
    indexer.index_repo(args.repo)
