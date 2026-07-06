"""
Tests for Knowledge Base RAG engine.

Note: EngineeringKnowledgeBase.__init__ calls self._load_default_standards()
which needs an embedding provider. Without sentence-transformers installed,
set RAG_ALLOW_HASH_FALLBACK=1 to use deterministic SHA-256 fallback.
"""

import contextlib
import os

import numpy as np
import pytest

# Allow hash-based fallback for test environments without sentence-transformers
os.environ["RAG_ALLOW_HASH_FALLBACK"] = "1"

# Chroma requires sqlite3 >= 3.35.0 and the chromadb package; skip if not available
_HAS_KNOWLEDGE_DEPS = False
try:
    import sqlite3

    if sqlite3.sqlite_version_info >= (3, 35, 0):
        from knowledge.rag_engine import (
            EngineeringDocument,
            EngineeringKnowledgeBase,
            get_knowledge_base,
        )

        _HAS_KNOWLEDGE_DEPS = True
except (ImportError, RuntimeError):  # NOSONAR — python:S5713: ModuleNotFoundError is a subclass of ImportError; kept for clarity
    _HAS_KNOWLEDGE_DEPS = False

pytestmark = pytest.mark.skipif(
    not _HAS_KNOWLEDGE_DEPS,
    reason="Chroma requires sqlite3 >= 3.35.0 and chromadb package",
)


@pytest.fixture(autouse=True)
def _reset_knowledge_base_singleton():
    """Reset the knowledge base singleton + clean chroma state before each test.

    Without this, the EngineeringKnowledgeBase singleton + the underlying
    PersistentClient (at ./knowledge_db) leak state between tests — earlier
    test ingests pollute the chroma collection, causing later tests to
    retrieve stale documents instead of the default engineering standards.
    """
    if _HAS_KNOWLEDGE_DEPS:
        # Reset the singleton so each test gets a fresh EngineeringKnowledgeBase
        import knowledge.rag_engine as _rag

        _rag._knowledge_base = None
        # Clean any persistent chroma collection so the next instantiation
        # starts with only the default engineering standards (not leftovers
        # from previous test ingests like 'test_doc_1' / 'custom_test').
        with contextlib.suppress(Exception):
            import chromadb

            client = chromadb.PersistentClient(path="./knowledge_db")
            for col_name in ["engineering_knowledge", "code_context"]:
                try:
                    client.delete_collection(col_name)
                except Exception:
                    pass
    yield


class TestEngineeringKnowledgeBase:
    def test_initialization(self):
        kb = EngineeringKnowledgeBase()
        # Removed redundant `assert kb is not None` (SonarCloud S5727:
        # constructor always returns an instance). The two checks below
        # verify the instance is internally consistent.
        assert kb.embedding_model is not None
        assert kb.vector_db is not None

    def test_loads_default_standards(self):
        kb = EngineeringKnowledgeBase()
        assert len(kb.vector_db.documents) >= 6  # 6 default standards loaded

    def test_retrieve_knowledge(self):
        kb = EngineeringKnowledgeBase()
        results = kb.retrieve_knowledge("short circuit fault analysis")
        assert len(results) > 0
        for r in results:
            assert r.relevance_score > 0
            assert hasattr(r.document, "source")

    def test_retrieve_no_match(self):
        kb = EngineeringKnowledgeBase()
        results = kb.retrieve_knowledge("xyznonexistent")
        # Smoke test: verify retrieval doesn't crash with a non-matching query.
        # The KB may use fuzzy matching, so we don't assert == 0; we only
        # assert the return type is a list (SonarCloud S3981: don't use
        # `len(x) >= 0` which is trivially true).
        assert isinstance(results, list)

    def test_ingest_new_document(self):
        kb = EngineeringKnowledgeBase()
        doc = EngineeringDocument(
            doc_id="test_doc_1",
            title="Test Standard",
            source="IEEE",
            standard_number="999",
            content="This is a test engineering document for testing purposes.",
            metadata={"category": "test"},
        )
        kb.ingest_document(doc)
        assert "test_doc_1" in kb.vector_db.documents

    def test_check_compliance_arc_flash(self):
        kb = EngineeringKnowledgeBase()
        result = kb.check_compliance("arc_flash", {"voltage_kv": 0.48})
        assert result["calculation_type"] == "arc_flash"
        assert isinstance(result["compliant"], bool)
        assert len(result["references"]) > 0

    def test_check_compliance_out_of_range(self):
        kb = EngineeringKnowledgeBase()
        result = kb.check_compliance("arc_flash", {"voltage_kv": 100.0})
        assert "calculation_type" in result

    def test_check_compliance_harmonic(self):
        kb = EngineeringKnowledgeBase()
        result = kb.check_compliance("harmonic", {"thd_voltage": 12.0})
        assert result["calculation_type"] == "harmonic"

    def test_check_compliance_voltage(self):
        kb = EngineeringKnowledgeBase()
        result = kb.check_compliance("voltage", {"magnitude_pu": 0.92})
        assert result["calculation_type"] == "voltage"

    def test_generate_citation(self):
        kb = EngineeringKnowledgeBase()
        results = kb.retrieve_knowledge("IEC 60909 short circuit")
        citation = kb.generate_citation(results)
        assert isinstance(citation, str)
        if results:
            assert "IEC" in citation or "IEEE" in citation or citation != ""

    def test_citation_empty_results(self):
        kb = EngineeringKnowledgeBase()
        citation = kb.generate_citation([])
        assert citation == ""

    def test_get_knowledge_base_singleton(self):
        kb1 = get_knowledge_base()
        kb2 = get_knowledge_base()
        assert kb1 is kb2

    def test_retrieve_multiple_topics(self):
        kb = EngineeringKnowledgeBase()
        results_arc = kb.retrieve_knowledge("arc flash safety incident energy", top_k=2)
        results_fault = kb.retrieve_knowledge("short circuit three phase fault", top_k=2)
        assert len(results_arc) >= 1
        assert len(results_fault) >= 1

    def test_ingest_retrieve_roundtrip(self):
        kb = EngineeringKnowledgeBase()
        doc = EngineeringDocument(
            doc_id="custom_test",
            title="Custom Test Doc",
            source="TEST",
            content="Unique test content for custom document roundtrip verification.",
        )
        kb.ingest_document(doc)
        results = kb.retrieve_knowledge("custom document roundtrip verification", top_k=5)
        found = any(r.document.doc_id == "custom_test" for r in results)
        assert found

    def test_retrieve_with_top_k(self):
        kb = EngineeringKnowledgeBase()
        results = kb.retrieve_knowledge("power system analysis", top_k=1)
        assert len(results) <= 1
