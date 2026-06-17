"""Knowledge - Engineering knowledge base and RAG system.

Provides retrieval-augmented generation (RAG) capabilities for querying
engineering documentation, standards, and domain knowledge using vector
database and embedding models.

PRIMARY AUTHORITATIVE REFERENCES:
- ETAP Official Manuals (knowledge_base/extracted/etap/)
- Zenon SCADA Manuals (knowledge_base/extracted/zenon/)
"""

from knowledge.rag_engine import (
    EmbeddingModel,
    EngineeringDocument,
    EngineeringKnowledgeBase,
    RetrievalResult,
    VectorDatabase,
    get_knowledge_base,
)

__all__ = [
    "EngineeringKnowledgeBase",
    "EngineeringDocument",
    "RetrievalResult",
    "EmbeddingModel",
    "VectorDatabase",
    "get_knowledge_base",
]
