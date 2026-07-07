"""
services/memory_service.py — AI Memory Service (RAG & GraphRAG)
================================================================
Handles vector-based semantic retrieval (Qdrant) and
graph-based relationship retrieval (Neo4j GraphRAG).
"""

import hashlib
import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Try importing LangChain + Qdrant + Neo4j components.
try:
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models

    QDRANT_AVAILABLE = True
except ImportError as err:
    logger.warning("Qdrant dependencies not fully available: %s", err)
    QDRANT_AVAILABLE = False

    class QdrantClient:
        pass

    class QdrantVectorStore:
        pass

    qdrant_models = None

try:
    from langchain_core.embeddings import Embeddings
except ImportError:

    class Embeddings:
        """Fallback empty class when langchain_core is not available."""

        pass


try:
    from langchain_core.documents import Document
    from langchain_experimental.graph_transformers import LLMGraphTransformer
    from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError as err:
    logger.warning("LangChain core/openai dependencies not fully available: %s", err)
    LANGCHAIN_CORE_AVAILABLE = False

    class Neo4jGraph:
        pass

    class LLMGraphTransformer:
        pass

    class ChatOpenAI:
        pass

    class OpenAIEmbeddings:
        pass

    class Document:
        pass

    class GraphCypherQAChain:
        pass


class DeterministicFallbackEmbeddings(Embeddings):
    """Deterministic offline fallback embeddings helper when API is unavailable or unconfigured."""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def _embed(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(self.dimension):
            val = (h[i % len(h)] + i) % 256
            # Normalize to [-1.0, 1.0]
            vector.append((val / 128.0) - 1.0)
        # Normalize to unit length
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]
        return vector


class AIMemoryService:
    """Service class for managing Qdrant Vector DB (RAG) and Neo4j Graph DB (Topology)."""

    def __init__(self):
        # Neo4j Settings
        self.neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_username = os.environ.get("NEO4J_USER", "neo4j")
        self.neo4j_password = os.environ.get("NEO4J_PASSWORD", "")  # no S2068: default empty; required from env in production

        # Qdrant Settings
        self.qdrant_url = os.environ.get("QDRANT_URL", "")
        self.qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.environ.get("QDRANT_PORT", "6333"))
        self.qdrant_api_key = os.environ.get("QDRANT_API_KEY", "")

        # LLM Provider settings (Modal custom endpoint by default if specified)
        self.openai_base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        self.llm_model = os.environ.get("LLM_MODEL", "gpt-4o")

        # Embeddings provider settings
        self.embedding_base_url = os.environ.get("EMBEDDING_API_BASE", self.openai_base_url)
        self.embedding_api_key = os.environ.get("EMBEDDING_API_KEY", self.openai_api_key)
        self.embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

        self._graph = None
        self._qdrant_client = None
        self._initialized_neo4j = False
        self._initialized_qdrant = False

    def initialize_neo4j(self) -> bool:
        """Initialize connection to Neo4j graph database."""
        if not LANGCHAIN_CORE_AVAILABLE:
            logger.warning("Neo4j RAG integration is disabled (missing libraries).")
            return False
        try:
            # Set credentials in environment for langchain_neo4j
            os.environ["NEO4J_URI"] = self.neo4j_uri
            os.environ["NEO4J_USERNAME"] = self.neo4j_username
            os.environ["NEO4J_PASSWORD"] = self.neo4j_password
            self._graph = Neo4jGraph()
            logger.info("Successfully connected to Neo4j Graph DB.")
            self._initialized_neo4j = True
            return True
        except Exception as exc:
            logger.exception("Failed to connect to Neo4j Graph DB: %s", exc)
            self._initialized_neo4j = False
            return False

    def initialize_qdrant(self) -> bool:
        """Initialize connection to Qdrant vector database."""
        if not QDRANT_AVAILABLE:
            logger.warning("Qdrant RAG integration is disabled (missing libraries).")
            return False
        try:
            if self.qdrant_url:
                logger.info("Connecting to Qdrant Cloud at %s", self.qdrant_url)
                self._qdrant_client = QdrantClient(
                    url=self.qdrant_url,
                    api_key=self.qdrant_api_key if self.qdrant_api_key else None,
                )
            else:
                logger.info("Connecting to local Qdrant at %s:%s", self.qdrant_host, self.qdrant_port)
                self._qdrant_client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
            self._initialized_qdrant = True
            return True
        except Exception as exc:
            logger.exception("Failed to connect to Qdrant: %s", exc)
            self._initialized_qdrant = False
            return False

    def _get_embeddings(self) -> Embeddings:
        """Configure embeddings model with offline fallback."""
        if not LANGCHAIN_CORE_AVAILABLE:
            return DeterministicFallbackEmbeddings()

        # If no API key is specified and we're using default settings, fallback immediately
        if not self.embedding_api_key or "your-openai-key" in self.embedding_api_key.lower():
            logger.info(
                "No embedding API key provided. Using deterministic offline fallback embeddings.",
            )
            return DeterministicFallbackEmbeddings()

        try:
            return OpenAIEmbeddings(
                model=self.embedding_model,
                base_url=self.embedding_base_url,
                api_key=self.embedding_api_key,
            )
        except Exception as exc:
            logger.warning(
                "Failed to initialize OpenAIEmbeddings (%s). Using offline fallback.",
                exc,
            )
            return DeterministicFallbackEmbeddings()

    def _get_llm(self) -> Any:
        """Configure LLM model."""
        if not LANGCHAIN_CORE_AVAILABLE:
            raise RuntimeError("Langchain core libraries not available.")

        # Ensure we have some API key for ChatOpenAI compatibility
        api_key = self.openai_api_key if self.openai_api_key else "dummy-api-key"
        return ChatOpenAI(
            model=self.llm_model, base_url=self.openai_base_url, api_key=api_key, temperature=0,
        )

    def add_knowledge_to_graph(self, text: str, allowed_nodes: Optional[List[str]] = None) -> bool:
        """Parse text, extract entities and relationships, and save them to Neo4j graph."""
        if not self._initialized_neo4j and not self.initialize_neo4j():
            logger.error("Neo4j not initialized.")
            return False
        try:
            llm = self._get_llm()
            transformer = LLMGraphTransformer(llm=llm, allowed_nodes=allowed_nodes)
            docs = [Document(page_content=text)]
            graph_documents = transformer.convert_to_graph_documents(docs)
            self._graph.add_graph_documents(graph_documents)
            logger.info("Successfully loaded relations into Neo4j graph.")
            return True
        except Exception as exc:
            logger.exception("Failed to populate graph: %s", exc)
            return False

    def query_graph(self, query: str) -> str:
        """Run a Cypher query chain on Neo4j Graph DB."""
        if not self._initialized_neo4j and not self.initialize_neo4j():
            return "AI Memory Service is not connected to Neo4j."
        try:
            llm = self._get_llm()
            chain = GraphCypherQAChain.from_llm(llm=llm, graph=self._graph, verbose=True)
            return chain.run(query)
        except Exception as exc:
            logger.exception("Cypher query execution failed: %s", exc)
            return f"Error querying graph database: {exc}"

    def save_to_vector_memory(self, fact_text: str, index_name: str = "ai_memory_index") -> bool:
        """Convert a fact text into embeddings and save it to the Qdrant Vector index."""
        if not self._initialized_qdrant and not self.initialize_qdrant():
            logger.error("Qdrant not initialized.")
            return False
        try:
            embeddings = self._get_embeddings()

            # Programmatically check and create collection if it doesn't exist
            # Check dimension of the selected embedding model
            dimension = 1536
            if "large" in self.embedding_model:
                dimension = 3072

            if not self._qdrant_client.collection_exists(collection_name=index_name):
                logger.info("Creating Qdrant collection: %s", index_name)
                self._qdrant_client.create_collection(
                    collection_name=index_name,
                    vectors_config=qdrant_models.VectorParams(
                        size=dimension, distance=qdrant_models.Distance.COSINE,
                    ),
                )

            # Store using QdrantVectorStore wrapper
            vector_db = QdrantVectorStore(
                client=self._qdrant_client, collection_name=index_name, embedding=embeddings,
            )
            vector_db.add_texts([fact_text])
            logger.info("Successfully added fact to Qdrant collection '%s'", index_name)
            return True
        except Exception as exc:
            logger.exception("Failed to save fact to Qdrant vector memory: %s", exc)
            return False

    def query_vector_memory(self, question: str, index_name: str = "ai_memory_index") -> str:
        """Search the Qdrant Vector store to retrieve relevant facts and formulate an answer."""
        if not self._initialized_qdrant and not self.initialize_qdrant():
            return "AI Memory Service is not connected to Qdrant."
        try:
            embeddings = self._get_embeddings()

            if not self._qdrant_client.collection_exists(collection_name=index_name):
                return "Vector memory collection does not exist."

            vector_db = QdrantVectorStore(
                client=self._qdrant_client, collection_name=index_name, embedding=embeddings,
            )
            retriever = vector_db.as_retriever()
            docs = retriever.get_relevant_documents(question)

            if not docs:
                return "No relevant vector memory found."

            context = "\n".join([doc.page_content for doc in docs])
            llm = self._get_llm()
            prompt = f"Answer the question based only on this context:\n{context}\n\nQuestion: {question}"
            response = llm.predict(prompt)
            return response
        except Exception as exc:
            logger.exception("Vector retrieval query failed: %s", exc)
            return f"Error searching vector memory: {exc}"
