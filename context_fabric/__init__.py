"""
Context Fabric (M4.1)
=====================

Structured context aggregation layer over the EXISTING components — it does
not replace them:

+--------------------------+--------------------------------------------+
| Context type             | Existing backing component                 |
+==========================+============================================+
| ENGINEERING_KNOWLEDGE    | services/memory_service.py (Qdrant+Neo4j)  |
| ENGINEERING_HISTORY      | injectable (orchestrator task history)     |
| PROJECT_STATE            | injectable (project store / digital twin)  |
| CODE_CONTEXT             | ai_context_engine (ChromaDB code-RAG)      |
| STANDARDS                | skills/etap-expert.md knowledge base       |
| USER_CONTEXT             | injectable (user settings provider)        |
+--------------------------+--------------------------------------------+

Every piece of evidence leaving this layer is a ``ContextEvidence`` that
MANDATORILY carries ``source_type`` + ``content_hash`` (sha256) + ``tenant_id``
(M4.1 acceptance gate). Unregistered providers are reported explicitly as
unavailable — never fabricated.
"""

from context_fabric.fabric import (
    ContextEvidence,
    ContextEvidenceError,
    ContextFabric,
    ContextIsolationError,
    ContextProvider,
    ContextQueryResult,
    ContextType,
)
from context_fabric.providers import (
    ML_CONTEXT_BINDINGS,
    CallableContextProvider,
    CodeContextProvider,
    MemoryKnowledgeProvider,
    StandardsProvider,
    bind_ml_agents,
    build_default_fabric,
)

__all__ = [
    "ContextEvidence",
    "ContextEvidenceError",
    "ContextIsolationError",
    "ContextProvider",
    "ContextQueryResult",
    "ContextType",
    "ContextFabric",
    "CallableContextProvider",
    "CodeContextProvider",
    "MemoryKnowledgeProvider",
    "StandardsProvider",
    "ML_CONTEXT_BINDINGS",
    "bind_ml_agents",
    "build_default_fabric",
]
