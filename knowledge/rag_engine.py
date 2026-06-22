"""
Engineering Knowledge Base - RAG System
=========================================
Retrieval-Augmented Generation system for power system engineering knowledge.

Purpose:
- Prevent engineering hallucinations
- Ensure IEEE/IEC/NFPA standards compliance
- Provide authoritative references for calculations
- Support validation engine with standards data

Knowledge Sources:
- IEEE Standards (519, 1584, 399, 242, etc.)
- IEC Standards (60909, 60255, 61850, etc.)
- NFPA 70E (Electrical Safety)
- NEC (National Electrical Code)
- Power System Protection textbooks
- ETAP documentation

Architecture:
- Vector Database (ChromaDB / FAISS)
- Embedding Model (sentence-transformers)
- Retrieval Pipeline
- Citation System
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EngineeringDocument:
    """Represents an engineering standard or reference document."""

    doc_id: str
    title: str
    source: str  # IEEE, IEC, NFPA, etc.
    standard_number: str | None = None
    content: str = ""
    metadata: Dict = field(default_factory=dict)
    embedding: np.ndarray | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RetrievalResult:
    """Result from knowledge retrieval."""

    document: EngineeringDocument
    relevance_score: float
    excerpt: str
    page_reference: str | None = None


class EmbeddingModel:
    """
    Text embedding model for engineering documents.

    Supports:
    - Local models (sentence-transformers via Ollama/vLLM)
    - Cloud APIs (OpenAI, Azure OpenAI)
    - Model switching layer
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", use_local: bool = True):
        """
        Initialize embedding model.

        Parameters:
        model_name: Name of embedding model
        use_local: Use local model (True) or cloud API (False)
        """
        self.model_name = model_name
        self.use_local = use_local
        self.model = None

        if use_local:
            self._load_local_model()
        else:
            self._setup_cloud_api()

    def _load_local_model(self):
        """Load local embedding model using sentence-transformers."""
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded local embedding model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not installed. Using fallback.")
            self.model = None

    def _setup_cloud_api(self):
        """Setup cloud API for embeddings (OpenAI)."""
        try:
            import openai

            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                openai.api_key = api_key
                self.model = openai
                logger.info("Configured OpenAI API for embeddings")
            else:
                raise ValueError("OPENAI_API_KEY not set")
        except Exception as e:
            logger.error(f"Failed to setup cloud API: {e}")
            self.model = None

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts to embeddings.

        Parameters:
        texts: List of text strings

        Returns:
        Embedding vectors
        """
        if self.model is None:
            # Fallback: simple TF-IDF-like representation
            logger.warning("Using fallback embedding (not recommended)")
            return self._fallback_embedding(texts)

        if self.use_local:
            embeddings = self.model.encode(texts)
            return np.array(embeddings)
        else:
            # Cloud API call
            return self._cloud_encode(texts)

    def _cloud_encode(self, texts: List[str]) -> np.ndarray:
        """Encode using cloud API."""
        try:
            response = self.model.Embedding.create(model="text-embedding-ada-002", input=texts)
            embeddings = [item["embedding"] for item in response["data"]]
            return np.array(embeddings)
        except Exception as e:
            logger.error(f"Cloud embedding failed: {e}")
            return self._fallback_embedding(texts)

    def _fallback_embedding(self, texts: List[str]) -> np.ndarray:
        """
        Fallback embedding when cloud embedding is unavailable.

        Instead of producing meaningless SHA-256 hash vectors, this raises
        a RuntimeError to fail loudly. Operators must configure a valid
        embedding provider (OpenAI, local model, etc.) before using RAG.

        If you intentionally want a lightweight deterministic fallback for
        testing, set the environment variable RAG_ALLOW_HASH_FALLBACK=1.
        """
        import os

        if os.environ.get("RAG_ALLOW_HASH_FALLBACK") == "1":
            import hashlib

            dim = 384
            embeddings = []
            for text in texts:
                emb = np.zeros(dim)
                words = text.lower().split()
                for i, word in enumerate(words[:dim]):
                    word_hash = int(hashlib.sha256(word.encode()).hexdigest(), 16)
                    emb[i % dim] = (word_hash % 10000) / 10000.0
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                embeddings.append(emb)
            logger.warning(
                "Using SHA-256 hash fallback for embeddings — "
                "semantic similarity will NOT be meaningful. "
                "Configure a real embedding provider for production."
            )
            return np.array(embeddings)

        raise RuntimeError(
            "No embedding provider available. The SHA-256 hash fallback has been "
            "disabled because it produces meaningless vectors. Please configure "
            "a valid embedding provider (e.g., set OPENAI_API_KEY or run a local "
            "sentence-transformers model). To enable the hash fallback for testing, "
            "set RAG_ALLOW_HASH_FALLBACK=1."
        )


class VectorDatabase:
    """
    Vector database for storing and retrieving engineering knowledge.

    Supports:
    - ChromaDB (local, lightweight)
    - FAISS (Facebook AI Similarity Search)
    - In-memory storage (for testing)
    """

    def __init__(self, db_type: str = "chroma", db_path: str = "./knowledge_db"):
        """
        Initialize vector database.

        Parameters:
        db_type: Type of vector DB ('chroma', 'faiss', 'memory')
        db_path: Path to database storage
        """
        self.db_type = db_type
        self.db_path = db_path
        self.documents: Dict[str, EngineeringDocument] = {}
        self.embeddings: Dict[str, np.ndarray] = {}
        self.index = None

        self._initialize_db()

    def _initialize_db(self):
        """Initialize the vector database."""
        if self.db_type == "chroma":
            self._init_chroma()
        elif self.db_type == "faiss":
            self._init_faiss()
        else:
            self._init_memory()

    def _init_chroma(self):
        """Initialize ChromaDB."""
        try:
            import chromadb

            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(
                name="engineering_knowledge",
                metadata={"description": "Power system engineering standards"},
            )
            logger.info("Initialized ChromaDB vector database")
        except ImportError:
            logger.warning("ChromaDB not available. Using memory storage.")
            self._init_memory()

    def _init_faiss(self):
        """Initialize FAISS index."""
        try:
            import faiss

            dimension = 384  # Embedding dimension — must match embedding model output
            self.index = faiss.IndexFlatL2(dimension)
            self._faiss_id_map: List[str] = []
            logger.info("Initialized FAISS vector database")
        except ImportError:
            logger.warning("FAISS not available. Using memory storage.")
            self._init_memory()

    def _init_memory(self):
        """Initialize in-memory storage."""
        self.documents = {}
        self.embeddings = {}
        logger.info("Initialized in-memory vector database")

    def add_document(self, doc: EngineeringDocument, embedding: np.ndarray):
        """
        Add document to vector database.

        Parameters:
        doc: Engineering document
        embedding: Document embedding vector
        """
        doc_id = doc.doc_id
        self.documents[doc_id] = doc
        self.embeddings[doc_id] = embedding

        # Add to vector index
        if self.db_type == "chroma" and hasattr(self, "collection"):
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding.tolist()],
                metadatas=[
                    {
                        "title": doc.title,
                        "source": doc.source,
                        "standard_number": doc.standard_number,
                    }
                ],
                documents=[doc.content],
            )
        elif self.db_type == "faiss" and self.index is not None:
            self.index.add(embedding.reshape(1, -1))
            self._faiss_id_map.append(doc_id)

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[RetrievalResult]:
        """
        Search for similar documents.

        Parameters:
        query_embedding: Query embedding vector
        top_k: Number of results to return

        Returns:
        List of retrieval results ranked by relevance
        """
        if self.db_type == "chroma" and hasattr(self, "collection"):
            return self._search_chroma(query_embedding, top_k)
        elif self.db_type == "faiss" and self.index is not None:
            return self._search_faiss(query_embedding, top_k)
        else:
            return self._search_memory(query_embedding, top_k)

    def _search_chroma(self, query_embedding: np.ndarray, top_k: int) -> List[RetrievalResult]:
        """Search using ChromaDB."""
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()], n_results=top_k
        )

        retrieval_results = []
        for i, doc_id in enumerate(results["ids"][0]):
            if doc_id in self.documents:
                doc = self.documents[doc_id]
                distance = results["distances"][0][i]
                relevance_score = 1.0 / (1.0 + distance)

                retrieval_results.append(
                    RetrievalResult(
                        document=doc,
                        relevance_score=relevance_score,
                        excerpt=doc.content[:500],  # First 500 chars
                    )
                )

        return retrieval_results

    def _search_faiss(self, query_embedding: np.ndarray, top_k: int) -> List[RetrievalResult]:
        """Search using FAISS."""
        distances, indices = self.index.search(query_embedding.reshape(1, -1), top_k)

        retrieval_results = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(self._faiss_id_map):
                doc_id = self._faiss_id_map[idx]
                doc = self.documents.get(doc_id)
                if doc:
                    distance = distances[0][i]
                    relevance_score = 1.0 / (1.0 + distance)
                    retrieval_results.append(
                        RetrievalResult(
                            document=doc, relevance_score=relevance_score, excerpt=doc.content[:500]
                        )
                    )

        return retrieval_results

    def _search_memory(self, query_embedding: np.ndarray, top_k: int) -> List[RetrievalResult]:
        """Search using in-memory cosine similarity."""
        if not self.embeddings:
            return []

        # Calculate cosine similarity with all documents
        similarities = {}
        for doc_id, doc_emb in self.embeddings.items():
            # Cosine similarity
            dot_product = np.dot(query_embedding, doc_emb)
            norm_query = np.linalg.norm(query_embedding)
            norm_doc = np.linalg.norm(doc_emb)

            if norm_query > 0 and norm_doc > 0:
                similarity = dot_product / (norm_query * norm_doc)
                similarities[doc_id] = similarity

        # Sort by similarity
        sorted_docs = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:top_k]

        retrieval_results = []
        for doc_id, score in sorted_docs:
            doc = self.documents[doc_id]
            retrieval_results.append(
                RetrievalResult(
                    document=doc, relevance_score=float(score), excerpt=doc.content[:500]
                )
            )

        return retrieval_results


class EngineeringKnowledgeBase:
    """
    Main RAG system for engineering knowledge.

    Provides:
    - Document ingestion
    - Semantic search
    - Standards compliance checking
    - Citation generation
    """

    def __init__(self, embedding_model: EmbeddingModel | None = None,
                 vector_db: VectorDatabase | None = None):
        """
        Initialize knowledge base.

        Parameters:
        embedding_model: Embedding model instance
        vector_db: Vector database instance
        """
        self.embedding_model = embedding_model or EmbeddingModel()
        self.vector_db = vector_db or VectorDatabase()
        self.logger = logging.getLogger("knowledge_base")

        if hasattr(self.embedding_model, "model") and self.embedding_model.model is not None:
            test_emb = self.embedding_model.encode(["test"])
            actual_dim = test_emb.shape[1]
            if self.vector_db.db_type == "faiss" and self.vector_db.index is not None:
                faiss_dim = self.vector_db.index.d
                if actual_dim != faiss_dim:
                    logger.warning(
                        f"Embedding dimension ({actual_dim}) doesn't match FAISS index ({faiss_dim}). Reinitializing FAISS."
                    )
                    import faiss

                    self.vector_db.index = faiss.IndexFlatL2(actual_dim)

        # Load default engineering standards
        self._load_default_standards()

    def _load_default_standards(self):
        """Load default engineering standards into knowledge base."""
        standards = self._get_default_standards_content()

        for std_data in standards:
            doc = EngineeringDocument(
                doc_id=std_data["doc_id"],
                title=std_data["title"],
                source=std_data["source"],
                standard_number=std_data.get("standard_number"),
                content=std_data["content"],
                metadata=std_data.get("metadata", {}),
            )

            # Generate embedding
            embedding = self.embedding_model.encode([std_data["content"]])[0]

            # Add to database
            self.vector_db.add_document(doc, embedding)

        self.logger.info(f"Loaded {len(standards)} default engineering standards")

    def _get_default_standards_content(self) -> List[Dict]:
        """Get default engineering standards content."""
        return [
            {
                "doc_id": "ieee_519_2022_voltage_thd",
                "title": "IEEE 519-2022 Voltage THD Limits",
                "source": "IEEE",
                "standard_number": "519-2022",
                "content": """
                IEEE 519-2022 Table 1: Voltage Distortion Limits

                For systems rated 1.0 kV and below:
                - Individual harmonic: 5.0%
                - Total Harmonic Distortion (THD): 8.0%

                For systems rated 1.0 kV through 69 kV:
                - Individual harmonic: 3.0%
                - Total Harmonic Distortion (THD): 5.0%

                For systems rated 69.001 kV through 161 kV:
                - Individual harmonic: 1.5%
                - Total Harmonic Distortion (THD): 2.5%

                For systems rated above 161 kV:
                - Individual harmonic: 1.0%
                - Total Harmonic Distortion (THD): 1.5%
                """,
                "metadata": {"category": "power_quality", "topic": "harmonics"},
            },
            {
                "doc_id": "iec_60909_fault_types",
                "title": "IEC 60909 Short-Circuit Current Calculation",
                "source": "IEC",
                "standard_number": "60909-0:2016",
                "content": """
                IEC 60909-0:2016 defines methods for calculating short-circuit currents.

                Fault Types:
                1. Three-phase fault (balanced)
                   - Initial symmetrical short-circuit current: Ik"
                   - Peak making current: ip = κ * √2 * Ik"
                   - DC time constant: τ = X/R * 1/ω

                2. Line-to-ground fault (unbalanced)
                   - Uses positive, negative, and zero sequence impedances
                   - If = 3 * V / (Z1 + Z2 + Z0)

                3. Line-to-line fault
                   - If = V / (Z1 + Z2)

                4. Double line-to-ground fault
                   - Complex calculation involving all sequence networks

                Voltage Factor c:
                - For maximum short-circuit currents: c_max = 1.05 or 1.10
                - For minimum short-circuit currents: c_min = 0.95
                """,
                "metadata": {"category": "fault_analysis", "topic": "short_circuit"},
            },
            {
                "doc_id": "ieee_1584_arc_flash",
                "title": "IEEE 1584-2018 Arc Flash Hazard Calculation",
                "source": "IEEE",
                "standard_number": "1584-2018",
                "content": """
                IEEE 1584-2018 Standard for Calculating Incident Energy.

                Applicable Range:
                - Voltage: 208V to 15kV
                - Fault current: 500A to 106kA
                - Gap distance: 13mm to 152mm

                Arc Current Calculation:
                log(Iarc) = K + 0.662*log(Ibf) + 0.0966*V + 0.000526*G
                          + 0.5588*V*log(Ibf) - 0.00304*G*log(Ibf)

                Where:
                - Iarc: Arc current (kA)
                - Ibf: Bolted fault current (kA)
                - V: Voltage (kV)
                - G: Gap distance (mm)
                - K: Configuration factor

                Incident Energy:
                E = 4.184 * Cf * En * (t/0.2) * (610^x / D^x)

                Where:
                - E: Incident energy (cal/cm²)
                - Cf: Calculation factor
                - En: Normalized incident energy
                - t: Arc duration (seconds)
                - D: Working distance (mm)
                - x: Distance exponent

                PPE Categories (NFPA 70E):
                - Category 0: < 1.2 cal/cm²
                - Category 1: 1.2 to < 4 cal/cm²
                - Category 2: 4 to < 8 cal/cm²
                - Category 3: 8 to < 25 cal/cm²
                - Category 4: 25 to < 40 cal/cm²
                - Danger: ≥ 40 cal/cm²
                """,
                "metadata": {"category": "safety", "topic": "arc_flash"},
            },
            {
                "doc_id": "iec_60255_protection_curves",
                "title": "IEC 60255 Overcurrent Relay Characteristics",
                "source": "IEC",
                "standard_number": "60255",
                "content": """
                IEC 60255 Standard Inverse Time-Current Characteristics.

                Standard Inverse (SI):
                t = TMS * 0.14 / ((I/Ip)^0.02 - 1)

                Very Inverse (VI):
                t = TMS * 13.5 / ((I/Ip) - 1)

                Extremely Inverse (EI):
                t = TMS * 80 / ((I/Ip)^2 - 1)

                Long-Time Inverse (LTI):
                t = TMS * 120 / ((I/Ip) - 1)

                Where:
                - t: Operating time (seconds)
                - TMS: Time Multiplier Setting
                - I: Fault current
                - Ip: Pickup current setting

                Coordination Requirements:
                - Minimum coordination margin: 0.2 to 0.3 seconds
                - Downstream relay should trip before upstream
                - Consider breaker operating time (typically 3-5 cycles)
                """,
                "metadata": {"category": "protection", "topic": "relays"},
            },
            {
                "doc_id": "nec_article_110_safety",
                "title": "NEC Article 110 - Electrical Safety Requirements",
                "source": "NEC",
                "standard_number": "Article 110",
                "content": """
                National Electrical Code Article 110: Requirements for Electrical Installations.

                Key Safety Requirements:

                110.16 Arc-Flash Hazard Warning:
                - Equipment must be marked to warn qualified persons
                - Label must include nominal system voltage
                - Arc-flash boundary information required

                110.26 Working Space:
                - Minimum working space around electrical equipment
                - Depth: Based on voltage (typically 3-4 feet)
                - Width: At least 30 inches or equipment width
                - Height: 6.5 feet minimum

                110.34 Clear Working Space (Over 600V):
                - Increased clearance requirements for high voltage
                - Condition 1, 2, or 3 based on exposure

                Grounding Requirements:
                - All electrical systems must be properly grounded
                - Ground-fault protection required for certain systems
                - Equipment grounding conductor sizing per Table 250.122
                """,
                "metadata": {"category": "safety", "topic": "electrical_safety"},
            },
            {
                "doc_id": "ieee_399_load_flow",
                "title": "IEEE 399 Brown Book - Load Flow Analysis Methods",
                "source": "IEEE",
                "standard_number": "399",
                "content": """
                IEEE 399 (Brown Book): Recommended Practice for Industrial Power Systems Analysis.

                Load Flow Solution Methods:

                1. Gauss-Seidel Method:
                   - Simple but slow convergence
                   - Good for small systems
                   - May not converge for ill-conditioned systems

                2. Newton-Raphson Method:
                   - Fast quadratic convergence
                   - Handles large systems well
                   - Requires Jacobian matrix calculation
                   - Most widely used in industry

                3. Fast Decoupled Load Flow:
                   - Approximation of Newton-Raphson
                   - Exploits weak coupling between P-θ and Q-V
                   - Faster per iteration but more iterations needed
                   - Good for transmission systems

                Convergence Criteria:
                - Power mismatch: Typically 0.001 pu or less
                - Voltage change: Typically 0.0001 pu or less
                - Maximum iterations: Usually 20-50

                Bus Types:
                - Slack bus (Swing): Specifies V and θ
                - PV bus (Generator): Specifies P and V
                - PQ bus (Load): Specifies P and Q
                """,
                "metadata": {"category": "analysis", "topic": "load_flow"},
            },
        ]

    def ingest_document(self, doc: EngineeringDocument):
        """
        Ingest new engineering document into knowledge base.

        Parameters:
        doc: Engineering document to add
        """
        # Generate embedding
        embedding = self.embedding_model.encode([doc.content])[0]

        # Add to vector database
        self.vector_db.add_document(doc, embedding)

        self.logger.info(f"Ingested document: {doc.doc_id}")

    def retrieve_knowledge(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        Retrieve relevant engineering knowledge for a query.

        Parameters:
        query: Natural language query
        top_k: Number of results to return

        Returns:
        List of relevant documents with relevance scores
        """
        # Encode query
        query_embedding = self.embedding_model.encode([query])[0]

        # Search vector database
        results = self.vector_db.search(query_embedding, top_k)

        self.logger.info(f"Retrieved {len(results)} documents for query: {query[:50]}...")

        return results

    def check_compliance(self, calculation_type: str, parameters: Dict) -> Dict:
        """
        Check if calculation parameters comply with standards.

        Parameters:
        calculation_type: Type of calculation (e.g., 'arc_flash', 'fault_current')
        parameters: Calculation parameters

        Returns:
        Compliance check result with references
        """
        # Formulate query based on calculation type
        query = f"{calculation_type} standards requirements limits"

        # Retrieve relevant standards
        results = self.retrieve_knowledge(query, top_k=3)

        compliance_result = {
            "calculation_type": calculation_type,
            "compliant": True,
            "violations": [],
            "references": [],
            "recommendations": [],
        }

        # Check against retrieved standards
        for result in results:
            doc = result.document

            # Add reference
            compliance_result["references"].append(
                {
                    "title": doc.title,
                    "source": doc.source,
                    "standard_number": doc.standard_number,
                    "relevance_score": result.relevance_score,
                }
            )

            # Perform specific checks based on document content
            violations = self._check_specific_compliance(calculation_type, parameters, doc)

            if violations:
                compliance_result["compliant"] = False
                compliance_result["violations"].extend(violations)

        return compliance_result

    def _check_specific_compliance(
        self, calc_type: str, params: Dict, doc: EngineeringDocument
    ) -> List[str]:
        """Check specific compliance rules."""
        violations = []

        if calc_type == "arc_flash" and "voltage_kv" in params:
            voltage = params["voltage_kv"]
            if voltage < 0.208 or voltage > 15.0:
                violations.append(f"Voltage {voltage} kV outside IEEE 1584 range (0.208-15 kV)")

        elif calc_type == "harmonic" and "thd_voltage" in params:
            thd = params["thd_voltage"]
            if thd > 8.0:
                violations.append(f"Voltage THD {thd}% exceeds IEEE 519 limit (8% for <1kV)")

        elif calc_type == "voltage" and "magnitude_pu" in params:
            v_mag = params["magnitude_pu"]
            if v_mag < 0.95 or v_mag > 1.05:
                violations.append(f"Voltage {v_mag} pu outside acceptable range (0.95-1.05)")

        return violations

    def generate_citation(self, results: List[RetrievalResult]) -> str:
        """
        Generate formatted citation for retrieved documents.

        Parameters:
        results: Retrieval results

        Returns:
        Formatted citation string
        """
        citations = []
        for result in results:
            doc = result.document
            citation = f"[{doc.source} {doc.standard_number or ''}] {doc.title}"
            citations.append(citation)

        return "; ".join(citations)


# Singleton instance
_knowledge_base = None


def get_knowledge_base() -> EngineeringKnowledgeBase:
    """Get or create knowledge base singleton."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = EngineeringKnowledgeBase()
    return _knowledge_base
