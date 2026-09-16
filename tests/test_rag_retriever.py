"""
tests/test_rag_retriever.py — Unit tests for RAG Retriever.
"""

import time
import pytest

from api.rag_retriever import RAGRetriever, get_rag_retriever, reset_rag_retriever
from api.telemetry import tracker


@pytest.fixture(autouse=True)
def clean_rag():
    reset_rag_retriever()
    tracker.reset()
    yield
    reset_rag_retriever()
    tracker.reset()


@pytest.mark.asyncio
async def test_rag_index_and_retrieve_under_200ms():
    rag = RAGRetriever(similarity_threshold=0.80)
    result_id = "res_12345678"
    summary = {
        "study_type": "load_flow",
        "bus_count": 14,
        "max_voltage_pu": 1.05,
        "min_voltage_pu": 0.98,
        "converged": True,
    }
    metadata = {
        "agent_handle": "load_flow_agent",
        "tokens_used": 1500,
        "project": "Substation 11kV Expansion",
    }

    await rag.index_result(result_id, summary, metadata)

    start = time.perf_counter()
    results = await rag.retrieve(
        query="Substation 11kV Expansion load flow bus count voltage",
        system_context={"buses": 14},
        agent_handle="load_flow_agent",
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    # Must complete in < 200ms
    assert elapsed_ms < 200.0
    assert len(results) == 1
    assert results[0].result_id == result_id
    assert results[0].similarity >= 0.80
    assert results[0].summary["converged"] is True

    # Check telemetry recorded RAG retrieval
    metrics = tracker.get_metrics()
    assert metrics["rag_retrieved"] == 1


@pytest.mark.asyncio
async def test_rag_filters_irrelevant_or_cross_agent_queries():
    rag = RAGRetriever(similarity_threshold=0.85)

    # Index a short circuit result
    await rag.index_result(
        "sc_001",
        {"study_type": "short_circuit", "ikss_ka": 31.5},
        {"agent_handle": "short_circuit_agent"},
    )

    # Querying for arc flash with unrelated context shouldn't return short circuit result
    results = await rag.retrieve(
        query="arc flash PPE boundary incident energy cal/cm2",
        system_context={"working_distance_mm": 450},
        agent_handle="arcflash_agent",
    )
    assert len(results) == 0


@pytest.mark.asyncio
async def test_rag_respects_top_k():
    rag = RAGRetriever(top_k=2, similarity_threshold=0.70)
    for i in range(5):
        await rag.index_result(
            f"id_{i}",
            {"study_type": "protection_coordination", "relay_curve": f"51-{i}"},
            {"agent_handle": "protection_agent"},
        )

    results = await rag.retrieve(
        query="protection coordination relay curve 51",
        system_context={},
        agent_handle="protection_agent",
    )
    assert len(results) <= 2
