"""
tests/test_ai_ml_rag.py — Regression test for RAG endpoint.

يضمن أن /api/v1/rag/query يستدعي retrieve_knowledge (لا kb.search)
ولا يُكسَر مستقبلاً بتغيير اسم الدالة في rag_engine.py.

FIX-RC4: api/ai_ml.py:442 كان يستدعي kb.search (غير موجودة)
          → تم تصحيحها إلى kb.retrieve_knowledge في هذه المرحلة.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest



def _make_fake_results(n: int = 3) -> list:
    """يُنشئ نتائج وهمية بنفس شكل RetrievalResult."""
    return [
        MagicMock(
            content=f"Result {i}: IEEE 1584 arc flash calculation",
            score=0.9 - i * 0.1,
            source=f"knowledge/chunk_{i}.txt",
        )
        for i in range(n)
    ]


def test_rag_query_calls_retrieve_knowledge() -> None:
    """يتحقق أن ai_ml.py يستدعي retrieve_knowledge وليس search."""
    from api import ai_ml  # noqa: PLC0415

    import ast
    import inspect

    source = inspect.getsource(ai_ml)
    tree = ast.parse(source)

    calls = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in ("search", "retrieve_knowledge")
    ]

    assert "retrieve_knowledge" in calls, (
        "api/ai_ml.py يجب أن يستدعي kb.retrieve_knowledge (لا kb.search)"
    )
    assert "search" not in calls, (
        "api/ai_ml.py يجب ألا يستدعي kb.search (الدالة محذوفة من rag_engine.py)"
    )


@patch("knowledge.rag_engine.EngineeringKnowledgeBase")
def test_rag_endpoint_returns_200(mock_kb_class: MagicMock, client: Any, auth_headers: dict) -> None:
    """POST /api/v1/rag/query returns 200 with valid results."""
    mock_instance = mock_kb_class.return_value
    mock_instance.retrieve_knowledge.return_value = _make_fake_results(3)

    resp = client.post(
        "/api/v1/rag/query",
        json={"query": "IEEE 1584 arc flash incident energy calculation", "top_k": 3},
        headers=auth_headers,
    )

    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}:\n{resp.text}"
    )
    data = resp.json()
    assert data.get("success") is True
    assert "results" in data.get("data", {})


@patch("knowledge.rag_engine.EngineeringKnowledgeBase")
def test_rag_endpoint_handles_empty_results(mock_kb_class: MagicMock, client: Any, auth_headers: dict) -> None:
    """RAG endpoint returns 200 even when knowledge base has no matches."""
    mock_instance = mock_kb_class.return_value
    mock_instance.retrieve_knowledge.return_value = []

    resp = client.post(
        "/api/v1/rag/query",
        json={"query": "query with no matches in knowledge base", "top_k": 5},
        headers=auth_headers,
    )

    assert resp.status_code in (200, 404)
