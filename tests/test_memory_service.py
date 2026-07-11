"""
tests/test_memory_service.py — Unit tests for the AI Memory Service (Qdrant & Neo4j).

Tests are written to work regardless of whether optional AI memory libraries
(langchain-neo4j, langchain-openai, etc.) are installed. Integration tests that
require live connections are marked with pytest.mark.integration.
"""

from __future__ import annotations

import importlib
import sys
from typing import List, Optional, Union
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: detect which optional packages are installed in the test environment
# ---------------------------------------------------------------------------


def _has_module(name: str) -> bool:
    """Return True if *name* can be imported."""
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


QDRANT_AVAILABLE = _has_module("qdrant_client")
LANGCHAIN_CORE_AVAILABLE = _has_module("langchain_core")
LANGCHAIN_NEO4J_AVAILABLE = _has_module("langchain_neo4j")
LANGCHAIN_OPENAI_AVAILABLE = _has_module("langchain_openai")
LANGCHAIN_QDRANT_AVAILABLE = _has_module("langchain_qdrant")


# ---------------------------------------------------------------------------
# 1. DeterministicFallbackEmbeddings — always available (no deps required)
# ---------------------------------------------------------------------------

from services.memory_service import DeterministicFallbackEmbeddings  # noqa: E402


class TestFallbackEmbeddings:
    """Pure-Python deterministic embeddings that work with zero optional dependencies."""

    def test_dimension_matches_config(self):
        """Verify returned vector has exactly the requested dimension."""
        fallback = DeterministicFallbackEmbeddings(dimension=1536)

        vec = fallback.embed_query("electrical grid topology")
        assert len(vec) == 1536, f"Expected 1536, got {len(vec)}"
        assert all(isinstance(x, float) for x in vec)

    def test_embed_documents_returns_multiple(self):
        """embed_documents must return one vector per text."""
        fallback = DeterministicFallbackEmbeddings(dimension=512)
        texts = ["busbar protection", "load flow Newton-Raphson", "IEC 60909 fault current"]

        vecs = fallback.embed_documents(texts)
        assert len(vecs) == len(texts)
        for v in vecs:
            assert len(v) == 512

    def test_determinism(self):
        """Same text must always produce identical vector."""
        fallback = DeterministicFallbackEmbeddings(dimension=1536)
        text = "cable sizing NEC Table 310.16"

        vec1 = fallback.embed_query(text)
        vec2 = fallback.embed_query(text)
        assert vec1 == vec2, "FallbackEmbeddings is not deterministic!"

    def test_different_texts_different_vectors(self):
        """Different texts should produce distinct vectors."""
        fallback = DeterministicFallbackEmbeddings(dimension=1536)
        vec_a = fallback.embed_query("transformer")
        vec_b = fallback.embed_query("motor starting")
        assert vec_a != vec_b

    def test_unit_normalization(self):
        """Vectors must be L2-normalized (||v| ≈ 1.0) for cosine search."""
        fallback = DeterministicFallbackEmbeddings(dimension=1536)
        vec = fallback.embed_query("arc flash incident energy calculation")
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-5, f"Vector not unit-normalized, ||v|| = {norm}"

    def test_small_dimension(self):
        """Works for any arbitrary dimension."""
        fallback = DeterministicFallbackEmbeddings(dimension=4)
        vec = fallback.embed_query("test")
        assert len(vec) == 4
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-5


# ---------------------------------------------------------------------------
# 2. AIMemoryService — configuration & initialization logic
# ---------------------------------------------------------------------------

from services.memory_service import AIMemoryService  # noqa: E402


class TestAIMemoryServiceConfig:
    """Tests for configuration reading via environment variables."""

    def test_reads_qdrant_url_from_env(self, monkeypatch):
        monkeypatch.setenv("QDRANT_URL", "https://my-cloud.qdrant.io")
        monkeypatch.setenv("QDRANT_API_KEY", "test-key")
        svc = AIMemoryService()
        assert svc.qdrant_url == "https://my-cloud.qdrant.io"
        assert svc.qdrant_api_key == "test-key"

    def test_reads_neo4j_creds_from_env(self, monkeypatch):
        monkeypatch.setenv("NEO4J_URI", "bolt://testhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "secret")
        svc = AIMemoryService()
        assert svc.neo4j_uri == "bolt://testhost:7687"
        assert svc.neo4j_username == "neo4j"
        assert svc.neo4j_password == "secret"

    def test_reads_llm_model_from_env(self, monkeypatch):
        monkeypatch.setenv("LLM_MODEL", "zai-org/GLM-5.1-FP8")
        monkeypatch.setenv("OPENAI_API_BASE", "https://api.us-west-2.modal.direct/v1")
        svc = AIMemoryService()
        assert svc.llm_model == "zai-org/GLM-5.1-FP8"
        assert svc.openai_base_url == "https://api.us-west-2.modal.direct/v1"

    def test_default_initialized_flags_are_false(self):
        """Before initialize_*() is called, flags must be False."""
        svc = AIMemoryService()
        assert svc._initialized_neo4j is False
        assert svc._initialized_qdrant is False

    def test_get_embeddings_returns_fallback_without_api_key(self, monkeypatch):
        """When OPENAI_API_KEY is absent, must return DeterministicFallbackEmbeddings."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
        svc = AIMemoryService()
        embeddings = svc._get_embeddings()
        assert isinstance(embeddings, DeterministicFallbackEmbeddings)

    def test_get_embeddings_returns_fallback_with_placeholder_key(self, monkeypatch):
        """Placeholder key value triggers fallback, not a real API call."""
        monkeypatch.setenv("OPENAI_API_KEY", "your-openai-key-here")
        svc = AIMemoryService()
        embeddings = svc._get_embeddings()
        assert isinstance(embeddings, DeterministicFallbackEmbeddings)


# ---------------------------------------------------------------------------
# 3. Qdrant integration — mocked tests (no live server needed)
# ---------------------------------------------------------------------------


class TestQdrantIntegrationMocked:
    """Test Qdrant vector memory operations fully mocked."""

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="qdrant-client not installed")
    def test_initialize_qdrant_cloud_url(self, monkeypatch):
        """initialize_qdrant() should create QdrantClient with cloud URL."""
        monkeypatch.setenv("QDRANT_URL", "https://test.cloud.qdrant.io")
        monkeypatch.setenv("QDRANT_API_KEY", "test-api-key")

        with patch("services.memory_service.QdrantClient") as MockClient:
            MockClient.return_value = MagicMock()
            svc = AIMemoryService()
            result = svc.initialize_qdrant()

        assert result is True
        assert svc._initialized_qdrant is True
        MockClient.assert_called_once_with(
            url="https://test.cloud.qdrant.io", api_key="test-api-key"
        )

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="qdrant-client not installed")
    def test_initialize_qdrant_local(self, monkeypatch):
        """initialize_qdrant() without QDRANT_URL uses host/port."""
        monkeypatch.delenv("QDRANT_URL", raising=False)
        monkeypatch.setenv("QDRANT_HOST", "localhost")
        monkeypatch.setenv("QDRANT_PORT", "6333")

        with patch("services.memory_service.QdrantClient") as MockClient:
            MockClient.return_value = MagicMock()
            svc = AIMemoryService()
            result = svc.initialize_qdrant()

        assert result is True
        MockClient.assert_called_once_with(host="localhost", port=6333)

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="qdrant-client not installed")
    def test_initialize_qdrant_connection_failure(self):
        """initialize_qdrant() must return False on connection error."""
        with patch(
            "services.memory_service.QdrantClient", side_effect=Exception("connection refused")
        ):
            svc = AIMemoryService()
            result = svc.initialize_qdrant()

        assert result is False
        assert svc._initialized_qdrant is False

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="qdrant-client not installed")
    def test_save_creates_collection_if_missing(self):
        """save_to_vector_memory() must create a Qdrant collection if it doesn't exist."""
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False

        with patch("services.memory_service.QdrantClient", return_value=mock_client), \
            patch("services.memory_service.QdrantVectorStore") as MockVS:

            MockVS.return_value = MagicMock()
            svc = AIMemoryService()
            svc.initialize_qdrant()
            result = svc.save_to_vector_memory("T1 transformer rated 50MVA", index_name="test_col")

        assert result is True
        mock_client.collection_exists.assert_called_once_with(collection_name="test_col")
        mock_client.create_collection.assert_called_once()

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="qdrant-client not installed")
    def test_save_skips_collection_creation_if_exists(self):
        """save_to_vector_memory() must NOT re-create an existing collection."""
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True

        with patch("services.memory_service.QdrantClient", return_value=mock_client), \
     patch("services.memory_service.QdrantVectorStore") as MockVS:

            MockVS.return_value = MagicMock()
            svc = AIMemoryService()
            svc.initialize_qdrant()
            svc.save_to_vector_memory("Line 1 impedance 0.07+j0.28 Ω/km", index_name="test_col")

        mock_client.create_collection.assert_not_called()

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="qdrant-client not installed")
    def test_query_returns_answer_from_retrieved_docs(self, monkeypatch):
        """query_vector_memory() must retrieve docs, prompt LLM, and return result."""
        monkeypatch.setenv(
            "OPENAI_API_KEY", "modalresearch_TzUJFpXlhpM9zxRhymgDm4DZmIT_IFDGYuPtZT9Eekg"
        )
        monkeypatch.setenv("LLM_MODEL", "zai-org/GLM-5.1-FP8")

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True

        mock_doc = MagicMock()
        mock_doc.page_content = "T1 transformer rated 50MVA"
        mock_retriever = MagicMock()
        mock_retriever.get_relevant_documents.return_value = [mock_doc]
        mock_vs = MagicMock()
        mock_vs.as_retriever.return_value = mock_retriever

        mock_llm = MagicMock()
        mock_llm.predict.return_value = "T1 transformer rating is 50MVA."

        with patch("services.memory_service.QdrantClient", return_value=mock_client), \
             patch("services.memory_service.QdrantVectorStore", return_value=mock_vs), \
             patch("services.memory_service.ChatOpenAI", return_value=mock_llm):
            svc = AIMemoryService()
            svc.initialize_qdrant()
            answer = svc.query_vector_memory("What is T1 rating?", index_name="test_col")

        assert answer == "T1 transformer rating is 50MVA."
        mock_llm.predict.assert_called_once()

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="qdrant-client not installed")
    def test_query_returns_message_if_collection_missing(self):
        """query_vector_memory() must return message if collection doesn't exist."""
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False

        with patch("services.memory_service.QdrantClient", return_value=mock_client):
            svc = AIMemoryService()
            svc.initialize_qdrant()
            result = svc.query_vector_memory("Any question", index_name="empty_col")

        assert "does not exist" in result


# ---------------------------------------------------------------------------
# 4. Neo4j integration — mocked tests
# ---------------------------------------------------------------------------


class TestNeo4jIntegrationMocked:
    """Test Neo4j graph memory operations fully mocked."""

    @pytest.mark.skipif(not LANGCHAIN_NEO4J_AVAILABLE, reason="langchain-neo4j not installed")
    def test_initialize_neo4j_sets_flag(self):
        """initialize_neo4j() must set _initialized_neo4j=True on success."""
        with patch("services.memory_service.Neo4jGraph") as MockGraph:
            MockGraph.return_value = MagicMock()
            svc = AIMemoryService()
            result = svc.initialize_neo4j()

        assert result is True
        assert svc._initialized_neo4j is True

    @pytest.mark.skipif(not LANGCHAIN_NEO4J_AVAILABLE, reason="langchain-neo4j not installed")
    def test_initialize_neo4j_failure_returns_false(self):
        """initialize_neo4j() must return False when Neo4j is unreachable."""
        with patch(
            "services.memory_service.Neo4jGraph", side_effect=Exception("connection refused")
        ):
            svc = AIMemoryService()
            result = svc.initialize_neo4j()

        assert result is False
        assert svc._initialized_neo4j is False

    @pytest.mark.skipif(not LANGCHAIN_NEO4J_AVAILABLE, reason="langchain-neo4j not installed")
    def test_add_knowledge_transforms_text_to_graph(self):
        """add_knowledge_to_graph() must call LLMGraphTransformer and add_graph_documents."""
        with patch("services.memory_service.Neo4jGraph") as MockGraph, \
             patch("services.memory_service.LLMGraphTransformer") as MockTransformer, \
             patch("services.memory_service.ChatOpenAI"):
            mock_graph = MagicMock()
            MockGraph.return_value = mock_graph
            mock_transformer = MagicMock()
            mock_transformer.convert_to_graph_documents.return_value = ["g_doc"]
            MockTransformer.return_value = mock_transformer

            svc = AIMemoryService()
            svc.initialize_neo4j()
            result = svc.add_knowledge_to_graph(
                "Bus 1 is connected to Bus 2 via Line 10", allowed_nodes=["Bus", "Line"]
            )

        assert result is True
        mock_transformer.convert_to_graph_documents.assert_called_once()
        mock_graph.add_graph_documents.assert_called_once_with(["g_doc"])

    @pytest.mark.skipif(not LANGCHAIN_NEO4J_AVAILABLE, reason="langchain-neo4j not installed")
    def test_query_graph_invokes_cypher_chain(self):
        """query_graph() must route the question through GraphCypherQAChain."""
        with patch("services.memory_service.Neo4jGraph") as MockGraph, \
             patch("services.memory_service.GraphCypherQAChain") as MockChain, \
             patch("services.memory_service.ChatOpenAI"):
            MockGraph.return_value = MagicMock()
            mock_chain = MagicMock()
            mock_chain.run.return_value = "Bus 1 and Bus 2 are connected via Line 10."
            MockChain.from_llm.return_value = mock_chain

            svc = AIMemoryService()
            svc.initialize_neo4j()
            answer = svc.query_graph("Are Bus 1 and Bus 2 connected?")

        assert answer == "Bus 1 and Bus 2 are connected via Line 10."
        mock_chain.run.assert_called_once_with("Are Bus 1 and Bus 2 connected?")


# ---------------------------------------------------------------------------
# 5. Graceful degradation (always run — no deps required)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Verify the service fails safely when optional libraries are unavailable."""

    def test_save_to_vector_memory_returns_false_when_qdrant_unavailable(self):
        """save_to_vector_memory() must return False when Qdrant is not installed/connected."""
        svc = AIMemoryService()
        # Don't call initialize_qdrant() and patch QDRANT_AVAILABLE to False
        with patch("services.memory_service.QDRANT_AVAILABLE", False):
            result = svc.save_to_vector_memory("any fact")
        assert result is False

    def test_query_vector_returns_error_string_when_not_connected(self):
        """query_vector_memory() must return a string error, not raise an exception."""
        svc = AIMemoryService()
        with patch("services.memory_service.QDRANT_AVAILABLE", False):
            result = svc.query_vector_memory("any question")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_add_graph_returns_false_when_neo4j_unavailable(self):
        """add_knowledge_to_graph() must return False when Neo4j is not connected."""
        svc = AIMemoryService()
        with patch("services.memory_service.LANGCHAIN_CORE_AVAILABLE", False):
            result = svc.add_knowledge_to_graph("any text")
        assert result is False

    def test_query_graph_returns_string_when_not_connected(self):
        """query_graph() must return a string, not raise an exception."""
        svc = AIMemoryService()
        with patch("services.memory_service.LANGCHAIN_CORE_AVAILABLE", False):
            result = svc.query_graph("any question")
        assert isinstance(result, str)
        assert len(result) > 0
