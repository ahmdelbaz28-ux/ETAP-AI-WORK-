"""
AI Context Engine - Code Indexer
Implements Phase 1: Indexing with Tree-Sitter (or AST fallback) and ChromaDB.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import logging
import os
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_context_engine")

# ---------------------------------------------------------------------------
# Optional Dependencies (Graceful Degradation)
# ---------------------------------------------------------------------------
try:
    import chromadb

    # SECURITY (CVE-2026-45829): Refuse chromadb 1.0+ (pre-auth RCE)
    _chromadb_version = getattr(chromadb, "__version__", "0.0.0")
    if _chromadb_version.startswith("1.") or _chromadb_version >= "1.0.0":
        raise RuntimeError(
            f"SECURITY: chromadb {_chromadb_version} is VULNERABLE to CVE-2026-45829 "
            f"(pre-auth RCE). Pin chromadb<1.0.0."
        )

    CHROMA_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    CHROMA_AVAILABLE = False
    logger.warning("chromadb not available (%s). Vector storage disabled.", e)

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
    def extract_with_ast(filepath: Path) -> list[dict]:
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
                        },
                    )
        except Exception as e:
            logger.exception("AST Error in %s: %s", filepath, e)
        return chunks

    @staticmethod
    def extract_with_tree_sitter(filepath: Path) -> list[dict]:
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
                        },
                    )
                for child in node.children:
                    traverse(child)

            traverse(tree.root_node)
        except Exception as e:
            logger.exception("Tree-sitter Error in %s: %s", filepath, e)

        return chunks

    @classmethod
    def extract(cls, filepath: Path) -> list[dict]:
        """Extract chunks using the best available method."""
        if TREE_SITTER_AVAILABLE:
            return cls.extract_with_tree_sitter(filepath)
        else:
            return cls.extract_with_ast(filepath)


def _is_within(path: Path, root: Path) -> bool:
    """Return True if `path` is `root` itself or lives somewhere below `root`."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class CodeIndexer:
    # Security Fix V-06: Resource limits for indexing operations
    MAX_FILES_PER_INDEX = 5000  # Maximum files to process in one index run
    MAX_CHUNKS_PER_FILE = 100  # Maximum chunks extracted per file
    MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB — skip files larger than this
    BATCH_SIZE = 50  # ChromaDB upsert batch size

    def __init__(self, output_dir: str, embedding_function=None):
        # SonarCloud pythonsecurity:S8707: validate the path before creating
        # the directory so an LLM-supplied CLI argument can't be tricked into
        # writing outside the project tree (e.g. via ../ escapes or absolute
        # paths). We resolve the path and confirm it stays within an allowed
        # root: the current working directory, the per-user indexer directory,
        # or the user's home directory.
        # Using per-user dir (~/.etap/indexer) instead of system tempdir to
        # avoid SonarCloud S5443 (publicly writable directories).
        _default_indexer_dir = str(Path.home() / ".etap" / "indexer")
        _indexer_root = Path(os.environ.get("ETAP_INDEXER_DIR", _default_indexer_dir)).resolve()
        _indexer_root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(_indexer_root, 0o700)
        except OSError:
            pass  # Best-effort: chmod can fail on some filesystems
        candidate = Path(output_dir).expanduser().resolve()
        allowed_roots = [
            Path.cwd().resolve(),
            _indexer_root,
            Path.home().resolve(),
            Path(tempfile.gettempdir()).resolve(),
        ]
        if not any(_is_within(candidate, root) for root in allowed_roots):
            raise ValueError(
                f"Refusing to create index directory outside allowed roots "
                f"(CWD, tempdir, HOME): {output_dir!r}"
            )
        self.output_dir = candidate
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = None
        self.collection = None

        if CHROMA_AVAILABLE:
            self.client = chromadb.PersistentClient(path=str(self.output_dir))
            self.collection = self.client.get_or_create_collection(
                name="code_context",
                embedding_function=embedding_function,
            )

    def hash_code(self, code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def index_repo(  # NOSONAR
        self, repo_path: str
    ):  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Index a repository with resource limits (V-06).

        Security Fix V-06: Enforces file count limits, file size limits,
        and per-file chunk limits to prevent CPU/memory starvation when
        indexing large projects. Uses batched upserts to avoid memory
        spikes in ChromaDB.
        """
        repo_dir = Path(repo_path)
        total_chunks = 0
        files_processed = 0
        batch_ids = []
        batch_docs = []
        batch_metas = []

        logger.info("Scanning repository: %s", repo_dir.absolute())
        for root, dirs, files in os.walk(repo_dir):
            # Prune hidden dirs, venvs, and node_modules
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("venv", "node_modules", "__pycache__", "index")
            ]

            for file in files:
                if not file.endswith(".py"):
                    continue

                # V-06: Enforce maximum file count
                if files_processed >= self.MAX_FILES_PER_INDEX:
                    logger.warning(
                        "V-06: Reached MAX_FILES_PER_INDEX (%d). "
                        "Stopping index to prevent resource exhaustion.",
                        self.MAX_FILES_PER_INDEX,
                    )
                    break

                filepath = Path(root) / file

                # V-06: Skip files exceeding size limit
                try:
                    file_size = filepath.stat().st_size
                    if file_size > self.MAX_FILE_SIZE_BYTES:
                        logger.warning(
                            "V-06: Skipping %s (%d bytes > %d limit)",
                            filepath,
                            file_size,
                            self.MAX_FILE_SIZE_BYTES,
                        )
                        continue
                except OSError:
                    continue

                # V-06: Enforce per-file chunk limit
                chunks = CodeExtractor.extract(filepath)
                if len(chunks) > self.MAX_CHUNKS_PER_FILE:
                    logger.warning(
                        "V-06: Truncating chunks for %s from %d to %d",
                        filepath,
                        len(chunks),
                        self.MAX_CHUNKS_PER_FILE,
                    )
                    chunks = chunks[: self.MAX_CHUNKS_PER_FILE]

                files_processed += 1

                if chunks and self.collection:
                    for chunk in chunks:
                        chunk_id = f"{chunk['filepath']}::{chunk['name']}"
                        chunk_hash = self.hash_code(chunk["code"])

                        batch_ids.append(chunk_id)
                        batch_docs.append(chunk["code"])
                        batch_metas.append(
                            {
                                "name": chunk["name"],
                                "type": chunk["type"],
                                "filepath": chunk["filepath"],
                                "hash": chunk_hash,
                            },
                        )

                        # V-06: Batched upsert to prevent memory spikes
                        if len(batch_ids) >= self.BATCH_SIZE:
                            self.collection.upsert(
                                ids=batch_ids, documents=batch_docs, metadatas=batch_metas
                            )
                            batch_ids.clear()
                            batch_docs.clear()
                            batch_metas.clear()

                total_chunks += len(chunks)
            else:
                continue
            break  # V-06: Outer break when MAX_FILES_PER_INDEX reached

        # V-06: Flush remaining batch
        if batch_ids and self.collection:
            self.collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)

        logger.info(
            "Indexing complete. Extracted %s code chunks from %d files.",
            total_chunks,
            files_processed,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Context Engine - Indexer")
    parser.add_argument("--repo", type=str, default=".", help="Path to the repository to index")
    parser.add_argument(
        "--output",
        type=str,
        default="./index/",
        help="Path to save the ChromaDB index",
    )
    args = parser.parse_args()

    indexer = CodeIndexer(args.output)
    indexer.index_repo(args.repo)
