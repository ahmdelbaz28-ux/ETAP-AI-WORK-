"""
tests/test_context_fabric.py — M4.1 Gate: ContextFabric evidence provenance.

Acceptance gate G2 (M4): every Evidence produced by the ContextFabric carries
``source_type`` + ``content_hash`` (sha256) + ``tenant_id``; tenant scope is a
precondition; providers are fail-closed (explicit unavailability, never
fabrication). Also pins the two live M4.1 fixes:
- ai_context_engine tenant passthrough (adapter previously dropped tenant_id)
- services/memory_service provenance metadata (add_texts was bare)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from context_fabric import (
    ML_CONTEXT_BINDINGS,
    CallableContextProvider,
    ContextEvidence,
    ContextEvidenceError,
    ContextFabric,
    ContextIsolationError,
    ContextType,
    bind_ml_agents,
    build_default_fabric,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _expected_hash(value) -> str:
    canonical = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Evidence identity invariants (G2)
# ---------------------------------------------------------------------------


def test_evidence_requires_tenant():
    """ContextEvidence refuses to exist without a tenant (fail-closed)."""
    with pytest.raises(ContextIsolationError):
        ContextEvidence.build(ContextType.STANDARDS, "k", "v", tenant_id="")
    with pytest.raises(ContextIsolationError):
        ContextEvidence.build(ContextType.STANDARDS, "k", "v", tenant_id="   ")


def test_evidence_requires_key_and_value():
    with pytest.raises(ContextEvidenceError):
        ContextEvidence.build(ContextType.STANDARDS, "", "v", tenant_id="t1")
    with pytest.raises(ContextEvidenceError):
        ContextEvidence.build(ContextType.STANDARDS, "k", None, tenant_id="t1")


def test_query_requires_tenant():
    fabric = ContextFabric()
    with pytest.raises(ContextIsolationError):
        fabric.query(ContextType.STANDARDS, "ieee 1584", tenant_id="")


def test_every_evidence_carries_source_type_hash_tenant():
    """G2: query over a live callable provider → all evidence fully tagged."""
    payload = {"standard": "IEC 60909", "value": 12.5}
    provider = CallableContextProvider(
        "test-provider",
        lambda q, t, n: [{"key": "ieee60909.ik", "value": payload, "source_ref": "unit-test"}],
    )
    fabric = ContextFabric({ContextType.ENGINEERING_KNOWLEDGE: provider})

    result = fabric.query(ContextType.ENGINEERING_KNOWLEDGE, "fault current", tenant_id="tenant-x")

    assert result.available is True
    assert len(result.evidence) == 1
    ev = result.evidence[0]
    assert ev.source_type is ContextType.ENGINEERING_KNOWLEDGE
    assert ev.tenant_id == "tenant-x"
    assert ev.content_hash == _expected_hash(payload)
    assert ev.key == "ieee60909.ik"
    assert ev.value == payload


# ---------------------------------------------------------------------------
# Fail-closed provider behaviour
# ---------------------------------------------------------------------------


def test_unregistered_provider_is_explicitly_unavailable():
    fabric = ContextFabric()
    result = fabric.query(ContextType.PROJECT_STATE, "switch position", tenant_id="t1")
    assert result.available is False
    assert result.reason == "no_provider_registered"
    assert result.evidence == []


def test_provider_error_is_fail_closed():
    def _boom(q, t, n):
        raise RuntimeError("backend down")

    fabric = ContextFabric({ContextType.USER_CONTEXT: CallableContextProvider("boom", _boom)})
    result = fabric.query(ContextType.USER_CONTEXT, "prefs", tenant_id="t1")
    assert result.available is False
    assert result.reason.startswith("provider_error:")
    assert result.evidence == []


def test_malformed_provider_items_skipped_never_guessed():
    provider = CallableContextProvider(
        "partial",
        lambda q, t, n: [
            {"no_value": 1},  # skipped
            "not-a-dict",  # skipped
            {"key": "ok", "value": "valid"},  # kept
        ],
    )
    fabric = ContextFabric({ContextType.STANDARDS: provider})
    result = fabric.query(ContextType.STANDARDS, "q", tenant_id="t1")
    assert result.available is True
    assert [e.key for e in result.evidence] == ["ok"]


# ---------------------------------------------------------------------------
# M4.1 live fixes
# ---------------------------------------------------------------------------


def test_rag_blueprint_adapter_forwards_tenant_id():
    """The adapter previously dropped tenant_id before calling the retriever."""
    from ai_context_engine.rag_blueprint_adapter import RAGBlueprintAdapter

    adapter = RAGBlueprintAdapter(index_dir=str(REPO_ROOT / "ai_context_engine" / "index"))
    captured: dict = {}

    def _fake_retrieve(query, top_k=5, tenant_id=None):
        captured["tenant_id"] = tenant_id
        captured["top_k"] = top_k
        return []

    adapter.base_retriever.retrieve = _fake_retrieve  # type: ignore[assignment]
    adapter.retrieve_blueprint_context("fault current", top_k=3, tenant_id="tenant-42")

    assert captured.get("tenant_id") == "tenant-42"


def test_memory_service_add_texts_carries_provenance():
    """add_texts must receive metadatas with tenant_id + source fields."""
    import services.memory_service as ms

    captured: dict = {}

    class _FakeStore:
        def __init__(self, **kwargs):
            pass

        def add_texts(self, texts, metadatas=None, **kwargs):
            captured["texts"] = texts
            captured["metadatas"] = metadatas
            return ["id-1"]

    class _FakeClient:
        def collection_exists(self, collection_name):
            return True

    class _FakeModels:
        pass

    svc = ms.AIMemoryService()
    svc._initialized_qdrant = True
    svc._qdrant_client = _FakeClient()
    svc._get_embeddings = lambda: object()  # type: ignore[method-assign]

    original_store = ms.QdrantVectorStore
    original_models = getattr(ms, "qdrant_models", None)
    ms.QdrantVectorStore = _FakeStore  # type: ignore[assignment]
    ms.qdrant_models = _FakeModels  # type: ignore[assignment]
    try:
        ok = svc.save_to_vector_memory(
            "Bus 4 fault current is 12.5 kA",
            tenant_id="tenant-7",
            provenance={"source_type": "standards", "source_ref": "IEC 60909:2016 §4.3"},
        )
    finally:
        ms.QdrantVectorStore = original_store  # type: ignore[assignment]
        ms.qdrant_models = original_models  # type: ignore[assignment]

    assert ok is True
    metadata = captured["metadatas"][0]
    assert metadata["tenant_id"] == "tenant-7"
    assert metadata["source_type"] == "standards"
    assert metadata["source_ref"] == "IEC 60909:2016 §4.3"


# ---------------------------------------------------------------------------
# ML agent context bindings (M4.4 interplay) + default fabric
# ---------------------------------------------------------------------------


def test_ml_agents_bind_to_context_not_study_types():
    """predictive/anomaly/digital_twin bind via ContextFabric providers only."""
    assert ML_CONTEXT_BINDINGS["predictive"] is ContextType.ENGINEERING_HISTORY
    assert ML_CONTEXT_BINDINGS["anomaly"] is ContextType.ENGINEERING_HISTORY
    assert ML_CONTEXT_BINDINGS["digital_twin"] is ContextType.PROJECT_STATE

    fabric = ContextFabric()
    bound = bind_ml_agents(
        fabric,
        {
            "predictive": lambda q, t, n: [{"key": "health_index", "value": 0.87}],
            "digital_twin": lambda q, t, n: [{"key": "sync_error", "value": 0.02}],
        },
    )
    assert sorted(bound) == ["digital_twin", "predictive"]

    hist = fabric.query(ContextType.ENGINEERING_HISTORY, "health", tenant_id="t1")
    assert hist.available
    assert hist.evidence[0].value == 0.87

    # anomaly was not supplied → explicit unavailability, no fabrication
    unbound = bind_ml_agents(ContextFabric(), {})
    assert unbound == []


def test_default_fabric_standards_provider_is_live():
    """build_default_fabric wires STANDARDS over skills/etap-expert.md."""
    fabric = build_default_fabric(skills_dir=REPO_ROOT / "skills")
    result = fabric.query(ContextType.STANDARDS, "IEEE 1584 arc flash", tenant_id="t1", limit=3)
    if not (REPO_ROOT / "skills" / "etap-expert.md").exists():  # pragma: no cover
        pytest.skip("skills knowledge base not present")
    assert result.available is True
    assert result.evidence, "expected at least one standards snippet"
    for ev in result.evidence:
        assert ev.source_type is ContextType.STANDARDS
        assert ev.tenant_id == "t1"
        assert len(ev.content_hash) == 64


def test_context_fabric_production_caller_prohibitory_guard():
    """M4.1 / R-4 Prohibitory Gate: ContextFabric MUST be consumed by production code."""
    import ast

    prod_files = [
        REPO_ROOT / "agents" / "orchestrator.py",
        REPO_ROOT / "api" / "context_engine.py",
    ]
    found_prod_importers: list[str] = []

    for pf in prod_files:
        assert pf.exists(), f"Production file {pf} missing"
        tree = ast.parse(pf.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "context_fabric" in node.module:
                found_prod_importers.append(str(pf.relative_to(REPO_ROOT)))
                break

    assert len(found_prod_importers) >= 1, (
        f"ContextFabric isolated! Expected production importers in {prod_files}, "
        f"found {found_prod_importers}. Anti-pattern 'built but unconnected' violated."
    )


def test_orchestrator_assemble_context_fail_closed_without_tenant():
    """Verify ChiefEngineeringOrchestrator.assemble_task_context raises ContextIsolationError if tenant_id is missing/empty."""
    from agents.orchestrator import ChiefEngineeringOrchestrator, EngineeringTask
    from context_fabric.fabric import ContextIsolationError

    orch = ChiefEngineeringOrchestrator()
    task = EngineeringTask(task_id="t1", description="IEC 60909 fault study", study_types=[], parameters={})

    with pytest.raises(ContextIsolationError, match="explicit non-empty tenant_id"):
        orch.assemble_task_context(task, tenant_id="")

    with pytest.raises(ContextIsolationError, match="explicit non-empty tenant_id"):
        orch.assemble_task_context(task, tenant_id=None)  # type: ignore[arg-type]

    # Valid tenant_id succeeds
    ctx = orch.assemble_task_context(task, tenant_id="tenant-123")
    assert isinstance(ctx, dict)


