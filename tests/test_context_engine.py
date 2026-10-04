"""Fix 12 regression tests: AI Context Engine / RAG tenant isolation.

Verifies:
  - CodeRetriever scopes query to tenant_id via ChromaDB where clause.
  - Tenant B querying for Tenant A's indexed documents receives no results.
  - POST /api/v1/context/retrieve propagates CurrentUser.tenant_id.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_context_engine.retriever import CodeRetriever
from api.dependencies import CurrentUser
from api.shared_handlers import SharedContextRetrieveRequest


class TestContextEngineTenantIsolation:
    """Verify tenant isolation in RAG retrieval."""

    def test_retriever_where_clause_filters_by_tenant_id(self, monkeypatch):
        """CodeRetriever queries collection with where={'tenant_id': tenant_id}."""
        import ai_context_engine.retriever as ret_mod

        monkeypatch.setattr(ret_mod, "CHROMA_AVAILABLE", True)
        retriever = CodeRetriever.__new__(CodeRetriever)
        retriever.client = MagicMock()
        mock_col = MagicMock()
        retriever.collection = mock_col

        # Setup mock return
        mock_col.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "ids": [[]],
        }

        # Query as Tenant B
        retriever.retrieve(query="calculate_short_circuit", top_k=5, tenant_id="tenant-B")

        mock_col.query.assert_called_once_with(
            query_texts=["calculate_short_circuit"],
            n_results=5,
            where={"tenant_id": "tenant-B"},
        )

    def test_tenant_b_receives_empty_when_documents_belong_to_tenant_a(self, monkeypatch):
        """When collection only has documents for Tenant A, Tenant B query returns empty."""
        import ai_context_engine.retriever as ret_mod

        monkeypatch.setattr(ret_mod, "CHROMA_AVAILABLE", True)
        retriever = CodeRetriever.__new__(CodeRetriever)
        retriever.client = MagicMock()
        mock_col = MagicMock()
        retriever.collection = mock_col

        def fake_query(**kwargs):
            where = kwargs.get("where", {})
            if where.get("tenant_id") == "tenant-A":
                return {
                    "documents": [["def run_study(): pass"]],
                    "metadatas": [[{"name": "run_study", "type": "function", "filepath": "a.py", "tenant_id": "tenant-A"}]],
                    "ids": [["doc-1"]],
                }
            return {
                "documents": [[]],
                "metadatas": [[]],
                "ids": [[]],
            }

        mock_col.query.side_effect = fake_query

        # Tenant A retrieves its doc
        results_a = retriever.retrieve("run_study", tenant_id="tenant-A")
        assert len(results_a) == 1
        assert results_a[0]["tenant_id"] == "tenant-A"

        # Tenant B receives empty results
        results_b = retriever.retrieve("run_study", tenant_id="tenant-B")
        assert len(results_b) == 0

    @pytest.mark.asyncio
    async def test_endpoint_propagates_current_user_tenant_id(self, monkeypatch):
        """POST /api/v1/context/retrieve passes user.tenant_id to handle_context_retrieval."""
        from api.context_engine import retrieve_context

        captured = {}

        def fake_handle(query, top_k, max_tokens, tenant_id):
            captured["tenant_id"] = tenant_id
            return {"success": True, "count": 0, "chunks": []}

        monkeypatch.setattr("api.context_engine.handle_context_retrieval", fake_handle)

        user = CurrentUser(
            user_id="u123",
            username="eng1",
            email="eng1@etap.com",
            role="engineer",
            tenant_id="tenant-alpha",
        )
        req = SharedContextRetrieveRequest(query="load flow analysis")

        response = await retrieve_context(request=req, user=user)
        assert response.status_code == 200
        assert captured.get("tenant_id") == "tenant-alpha"
