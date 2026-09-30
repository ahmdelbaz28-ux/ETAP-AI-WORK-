"""
context_fabric/providers.py — adapters over EXISTING components (M4.1).

These providers *wrap* live components; they never reimplement retrieval:

- ``MemoryKnowledgeProvider`` → ``services/memory_service.py`` (Qdrant+Neo4j)
- ``CodeContextProvider``     → ``ai_context_engine`` (ChromaDB code-RAG)
- ``StandardsProvider``       → ``skills/etap-expert.md`` knowledge base
- ``CallableContextProvider`` → any injected callable (HISTORY / PROJECT_STATE
  / USER_CONTEXT and ML-agent bindings)

Fail-closed: unregistered or failing providers report unavailable; nothing
is fabricated.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from context_fabric.fabric import ContextFabric, ContextType

logger = logging.getLogger("context_fabric.providers")

# ML agents are bound to CONTEXT only — never registered as StudyTypes (M4.4).
# Live state pinned by tests: predictive/anomaly are not StudyType members and
# goalless in STUDY_DISPATCH; digital_twin stays fail-closed on dispatch.
ML_CONTEXT_BINDINGS: dict[str, ContextType] = {
    "predictive": ContextType.ENGINEERING_HISTORY,
    "anomaly": ContextType.ENGINEERING_HISTORY,
    "digital_twin": ContextType.PROJECT_STATE,
}


class CallableContextProvider:
    """Adapts a plain callable ``fn(query, tenant_id, limit) -> list[dict]``."""

    def __init__(self, provider_id: str, fn: Callable[[str, str, int], list[dict]]) -> None:
        self.provider_id = str(provider_id)
        self._fn = fn

    def retrieve(self, query: str, tenant_id: str, limit: int) -> list[dict]:
        items = self._fn(query, tenant_id, limit) or []
        return [i for i in items if isinstance(i, dict)]


class MemoryKnowledgeProvider:
    """Engineering knowledge via the existing AIMemoryService (Qdrant+Neo4j).

    NOTE (tenant scope): the backing Qdrant store is process-global; tenant
    identity is attached to every evidence item at the fabric boundary and is
    now persisted as Qdrant metadata by ``save_to_vector_memory`` (M4.1 fix),
    enabling future per-tenant filtering without changing this interface.
    """

    provider_id = "memory_service.query_vector_memory"

    def __init__(self, memory_service: Any) -> None:
        self._service = memory_service

    def retrieve(self, query: str, tenant_id: str, limit: int) -> list[dict]:
        answer = self._service.query_vector_memory(str(query))
        if not answer or not str(answer).strip():
            return []
        lowered = str(answer).lower()
        unavailable_markers = (
            "not connected",
            "unavailable",
            "does not exist",
            "refusing to query",
        )
        if any(marker in lowered for marker in unavailable_markers):
            return []
        return [
            {
                "key": f"knowledge:{abs(hash(query)) % 10**8}",
                "value": str(answer),
                "source_ref": "services/memory_service.py",
            }
        ][:limit]


class CodeContextProvider:
    """Code-RAG via the existing ai_context_engine (tenant passthrough fixed)."""

    provider_id = "ai_context_engine.code_rag"

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    def retrieve(self, query: str, tenant_id: str, limit: int) -> list[dict]:
        result = self._adapter.retrieve_blueprint_context(
            query,
            top_k=max(1, int(limit)),
            tenant_id=tenant_id if tenant_id else None,
        )
        chunks = (result or {}).get("chunks") or []
        items: list[dict] = []
        for chunk in chunks:
            chunk_id = str(chunk.get("id", chunk.get("name", "unknown")))
            items.append(
                {
                    "key": f"code_chunk:{chunk_id}",
                    "value": {
                        "name": chunk.get("name", ""),
                        "filepath": chunk.get("filepath", ""),
                        "code": chunk.get("code", ""),
                    },
                    "source_ref": chunk.get("filepath") or "ai_context_engine",
                }
            )
        return items[:limit]



class StandardsProvider:
    """STANDARDS context over the existing skills/etap-expert.md knowledge base."""

    provider_id = "skills.etap_expert"

    def __init__(self, skills_dir: str | Path = "skills", max_snippet_chars: int = 400) -> None:
        self._path = Path(skills_dir) / "etap-expert.md"
        self._max = int(max_snippet_chars)

    def retrieve(self, query: str, tenant_id: str, limit: int) -> list[dict]:
        if not self._path.exists():
            return []
        tokens = [t for t in str(query).lower().split() if len(t) >= 3]
        if not tokens:
            return []
        items: list[dict] = []
        seen_lines: set[int] = set()
        try:
            lines = self._path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        for idx, line in enumerate(lines, start=1):
            lowered = line.lower()
            if any(token in lowered for token in tokens):
                if idx in seen_lines:
                    continue
                seen_lines.add(idx)
                snippet = line.strip()[: self._max]
                if not snippet:
                    continue
                items.append(
                    {
                        "key": f"standards:line_{idx}",
                        "value": snippet,
                        "source_ref": f"{self._path}#L{idx}",
                    }
                )
                if len(items) >= limit:
                    break
        return items


def build_default_fabric(skills_dir: str | Path = "skills") -> ContextFabric:
    """Assemble the default fabric over live components (stdlib-safe imports)."""
    fabric = ContextFabric()
    try:
        from services.memory_service import AIMemoryService

        fabric.register_provider(
            ContextType.ENGINEERING_KNOWLEDGE, MemoryKnowledgeProvider(AIMemoryService())
        )
    except Exception as exc:  # noqa: BLE001 - component may be unavailable
        logger.info("MemoryKnowledgeProvider not registered: %s", exc)

    try:
        from ai_context_engine.rag_blueprint_adapter import RAGBlueprintAdapter

        fabric.register_provider(ContextType.CODE_CONTEXT, CodeContextProvider(RAGBlueprintAdapter()))
    except Exception as exc:  # noqa: BLE001
        logger.info("CodeContextProvider not registered: %s", exc)

    fabric.register_provider(ContextType.STANDARDS, StandardsProvider(skills_dir=skills_dir))
    return fabric


def bind_ml_agents(fabric: ContextFabric, agent_callables: dict[str, Callable[..., Any]]) -> list[str]:
    """Bind predictive/anomaly/digital_twin agents as CONTEXT providers (M4.4).

    Returns the list of agent keys actually bound. Callers supply callables;
    absences are explicit (the corresponding context type stays unavailable
    unless another provider is registered).
    """
    bound: list[str] = []
    for agent_key, context_type in ML_CONTEXT_BINDINGS.items():
        fn = agent_callables.get(agent_key)
        if fn is None:
            continue
        fabric.register_provider(
            context_type,
            CallableContextProvider(f"ml_agent:{agent_key}", fn),
        )
        bound.append(agent_key)
    return bound
