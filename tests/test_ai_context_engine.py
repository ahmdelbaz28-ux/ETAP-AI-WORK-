"""
Tests for AI Context Engine Phase 1: Indexing.
"""
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ai_context_engine.indexer import CodeExtractor, CodeIndexer, CHROMA_AVAILABLE

# A sample python code string to test extraction
SAMPLE_PYTHON_CODE = """
import os

class DatabaseHandler:
    def __init__(self):
        self.connected = False
        
    def connect(self):
        self.connected = True
        return True

def standalone_function(x, y):
    return x + y
"""

@pytest.fixture
def sample_code_file(tmp_path):
    """Fixture to create a temporary python file with sample code."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")
    return file_path

class TestCodeExtractor:
    def test_extract_with_ast_finds_classes_and_functions(self, sample_code_file):
        """Test that the AST extractor successfully finds classes and functions."""
        chunks = CodeExtractor.extract_with_ast(sample_code_file)
        
        # We expect 3 chunks: DatabaseHandler, __init__, connect, and standalone_function
        # Wait, AST walk will find class, then its methods.
        assert len(chunks) == 4
        
        names = [chunk['name'] for chunk in chunks]
        assert "DatabaseHandler" in names
        assert "__init__" in names
        assert "connect" in names
        assert "standalone_function" in names
        
        # Verify types
        class_chunk = next(c for c in chunks if c['name'] == "DatabaseHandler")
        assert class_chunk['type'] == "class"
        
        func_chunk = next(c for c in chunks if c['name'] == "standalone_function")
        assert func_chunk['type'] == "function"

    def test_extract_with_ast_captures_code(self, sample_code_file):
        """Test that the extracted code block actually contains the source code."""
        chunks = CodeExtractor.extract_with_ast(sample_code_file)
        func_chunk = next(c for c in chunks if c['name'] == "standalone_function")
        assert "return x + y" in func_chunk['code']
        assert "def standalone_function(x, y):" in func_chunk['code']


class TestCodeIndexer:
    @pytest.fixture
    def mock_indexer(self, tmp_path):
        """Create an indexer with a temporary output directory."""
        return CodeIndexer(output_dir=str(tmp_path / "index"))

    def test_hash_code_is_deterministic(self, mock_indexer):
        """Test that the same code string always produces the same hash."""
        code1 = "def test(): pass"
        code2 = "def test(): pass"
        code3 = "def test(): return True"
        
        assert mock_indexer.hash_code(code1) == mock_indexer.hash_code(code2)
        assert mock_indexer.hash_code(code1) != mock_indexer.hash_code(code3)

    @pytest.mark.skipif(not CHROMA_AVAILABLE, reason="ChromaDB not installed")
    def test_chroma_collection_creation(self, mock_indexer):
        """Test that ChromaDB client and collection are initialized."""
        assert mock_indexer.client is not None
        assert mock_indexer.collection is not None
        assert mock_indexer.collection.name == "code_context"

    @patch("ai_context_engine.indexer.CodeExtractor.extract")
    def test_index_repo_walks_directories_and_upserts(self, mock_extract, mock_indexer, tmp_path):
        """Test that the index_repo function traverses files and calls upsert on the collection."""
        # Setup fake repo
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "file1.py").write_text("def func1(): pass")
        
        # Setup mock extraction
        mock_extract.return_value = [
            {"name": "func1", "type": "function", "filepath": str(repo_dir / "file1.py"), "code": "def func1(): pass"}
        ]
        
        # Mock ChromaDB collection to avoid actual DB operations in this test
        if mock_indexer.collection:
            mock_indexer.collection.upsert = MagicMock()
            
        mock_indexer.index_repo(str(repo_dir))
        
        # Verify extraction was called
        mock_extract.assert_called()
        
        # Verify upsert was called if collection exists
        if mock_indexer.collection:
            mock_indexer.collection.upsert.assert_called_once()
            args, kwargs = mock_indexer.collection.upsert.call_args
            assert len(kwargs['ids']) == 1
            assert len(kwargs['documents']) == 1
            assert len(kwargs['metadatas']) == 1
            assert kwargs['metadatas'][0]['name'] == "func1"
