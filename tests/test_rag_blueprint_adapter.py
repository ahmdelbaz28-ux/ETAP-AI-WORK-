"""
Unit tests for NVIDIA RAG Blueprint Adapter (ai_context_engine/rag_blueprint_adapter.py).
Verifies hybrid BM25 + dense ranking, token budget compression, and NeMo Guardrails compliance.
"""

from __future__ import annotations

import pytest
from ai_context_engine.rag_blueprint_adapter import BM25Ranker, RAGBlueprintAdapter


def test_bm25_ranker_scoring():
    ranker = BM25Ranker()
    query_tokens = ["iec", "60909", "short", "circuit"]
    doc1 = ["iec", "60909", "defines", "short", "circuit", "calculation", "methods"]
    doc2 = ["python", "code", "for", "gui", "interface"]

    score1 = ranker.score(query_tokens, doc1)
    score2 = ranker.score(query_tokens, doc2)

    assert score1 > 0.0
    assert score2 == 0.0
    assert score1 > score2


def test_rag_blueprint_hybrid_rerank():
    adapter = RAGBlueprintAdapter(index_dir="ai_context_engine/index")
    sample_chunks = [
        {
            "id": "chunk_1",
            "code": "def calculate_short_circuit_iec60909(voltage, impedance): return voltage / (math.sqrt(3) * impedance)",
            "name": "calculate_short_circuit_iec60909",
            "jaccard_score": 0.3,
        },
        {
            "id": "chunk_2",
            "code": "def update_ui_theme(color_theme): set_theme(color_theme)",
            "name": "update_ui_theme",
            "jaccard_score": 0.0,
        },
    ]

    query = "IEC 60909 short circuit calculation formula"
    reranked = adapter.hybrid_rerank(sample_chunks, query, top_k=2)

    assert len(reranked) == 2
    assert reranked[0]["id"] == "chunk_1"
    assert reranked[0]["hybrid_score"] > reranked[1]["hybrid_score"]
    assert "bm25_score" in reranked[0]


def test_rag_blueprint_guardrails():
    adapter = RAGBlueprintAdapter(index_dir="ai_context_engine/index")
    good_chunks = [
        {
            "id": "chunk_1",
            "code": "IEC 60909 short circuit breaking capacity limits",
            "hybrid_score": 0.85,
        }
    ]
    empty_chunks: list[dict] = []

    res_good = adapter.apply_guardrails("IEC 60909", good_chunks)
    assert res_good["compliant"] is True
    assert len(res_good["verified_chunks"]) == 1

    res_empty = adapter.apply_guardrails("Unknown Query", empty_chunks)
    assert res_empty["compliant"] is False
    assert "No relevant reference" in res_empty["reason"]


def test_retrieve_blueprint_context_graceful_fallback():
    adapter = RAGBlueprintAdapter(index_dir="non_existent_dir")
    result = adapter.retrieve_blueprint_context(query="transformer thermal limit", top_k=3, max_tokens=1000)

    assert result["query"] == "transformer thermal limit"
    assert isinstance(result["chunks"], list)
    assert "guardrails" in result
    assert result["total_tokens"] >= 0
