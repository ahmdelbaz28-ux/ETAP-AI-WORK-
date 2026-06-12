"""Knowledge - Engineering knowledge base and RAG system.

Provides retrieval-augmented generation (RAG) capabilities for querying
engineering documentation, standards, and domain knowledge using vector
database and embedding models.
"""

from knowledge.rag_engine import (
    EngineeringKnowledgeBase,
    EngineeringDocument,
    RetrievalResult,
    EmbeddingModel,
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
