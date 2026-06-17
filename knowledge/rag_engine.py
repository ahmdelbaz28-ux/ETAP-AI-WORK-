"""
Engineering Knowledge Base - RAG System (with ETAP & Zenon Integration)
=========================================================================
Retrieval-Augmented Generation system for power system engineering knowledge.

PRIMARY AUTHORITATIVE REFERENCES:
- ETAP Official Manuals (knowledge_base/extracted/etap/)
- Zenon (COPA-DATA) SCADA Manuals (knowledge_base/extracted/zenon/)
- ETAP User Guide (etap_user_guide/)

All AI agents MUST consult these references BEFORE performing any operation.

Knowledge Sources:
- ETAP User Guide & Study Manuals (PRIMARY)
- Zenon SCADA/HMI Documentation (PRIMARY for SCADA)
- IEEE Standards (519, 1584, 399, 242, etc.)
- IEC Standards (60909, 60255, 61850, etc.)
- NFPA 70E (Electrical Safety)
- NEC (National Electrical Code)
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EngineeringDocument:
    """Represents an engineering standard or reference document."""
    doc_id: str
    title: str
    source: str  # IEEE, IEC, NFPA, ETAP, Zenon, etc.
    standard_number: Optional[str] = None
    content: str = ""
    metadata: Dict = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RetrievalResult:
    """Result from knowledge retrieval."""
    document: EngineeringDocument
    relevance_score: float
    excerpt: str
    page_reference: Optional[str] = None


class EmbeddingModel:
    """
    Text embedding model for engineering documents.

    Supports:
    - Local models (sentence-transformers via Ollama/vLLM)
    - Cloud APIs (OpenAI, Azure OpenAI)
    - Model switching layer
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2",
                 use_local: bool = True):
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
            api_key = os.environ.get('OPENAI_API_KEY')
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
        """Encode texts to embeddings."""
        if self.model is None:
            return self._fallback_embedding(texts)

        if self.use_local:
            embeddings = self.model.encode(texts)
            return np.array(embeddings)
        else:
            return self._cloud_encode(texts)

    def _cloud_encode(self, texts: List[str]) -> np.ndarray:
        """Encode using cloud API."""
        try:
            response = self.model.Embedding.create(
                model="text-embedding-ada-002",
                input=texts
            )
            embeddings = [item['embedding'] for item in response['data']]
            return np.array(embeddings)
        except Exception as e:
            logger.error(f"Cloud embedding failed: {e}")
            return self._fallback_embedding(texts)

    def _fallback_embedding(self, texts: List[str]) -> np.ndarray:
        """Fallback embedding — raises RuntimeError unless explicitly allowed."""
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
            logger.warning("Using SHA-256 hash fallback for embeddings")
            return np.array(embeddings)

        raise RuntimeError(
            "No embedding provider available. Configure OPENAI_API_KEY or "
            "install sentence-transformers. Set RAG_ALLOW_HASH_FALLBACK=1 for testing."
        )


class VectorDatabase:
    """Vector database for storing and retrieving engineering knowledge."""

    def __init__(self, db_type: str = "chroma", db_path: str = "./knowledge_db"):
        self.db_type = db_type
        self.db_path = db_path
        self.documents: Dict[str, EngineeringDocument] = {}
        self.embeddings: Dict[str, np.ndarray] = {}
        self.index = None
        self._initialize_db()

    def _initialize_db(self):
        if self.db_type == "chroma":
            self._init_chroma()
        elif self.db_type == "faiss":
            self._init_faiss()
        else:
            self._init_memory()

    def _init_chroma(self):
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(
                name="engineering_knowledge",
                metadata={"description": "Power system engineering standards"}
            )
            logger.info("Initialized ChromaDB vector database")
        except ImportError:
            logger.warning("ChromaDB not available. Using memory storage.")
            self._init_memory()

    def _init_faiss(self):
        try:
            import faiss
            dimension = 384
            self.index = faiss.IndexFlatL2(dimension)
            self._faiss_id_map: List[str] = []
            logger.info("Initialized FAISS vector database")
        except ImportError:
            logger.warning("FAISS not available. Using memory storage.")
            self._init_memory()

    def _init_memory(self):
        self.documents = {}
        self.embeddings = {}
        logger.info("Initialized in-memory vector database")

    def add_document(self, doc: EngineeringDocument, embedding: np.ndarray):
        doc_id = doc.doc_id
        self.documents[doc_id] = doc
        self.embeddings[doc_id] = embedding

        if self.db_type == "chroma" and hasattr(self, 'collection'):
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding.tolist()],
                metadatas=[{
                    'title': doc.title,
                    'source': doc.source,
                    'standard_number': doc.standard_number
                }],
                documents=[doc.content]
            )
        elif self.db_type == "faiss" and self.index is not None:
            self.index.add(embedding.reshape(1, -1))
            self._faiss_id_map.append(doc_id)

    def search(self, query_embedding: np.ndarray,
               top_k: int = 5) -> List[RetrievalResult]:
        if self.db_type == "chroma" and hasattr(self, 'collection'):
            return self._search_chroma(query_embedding, top_k)
        elif self.db_type == "faiss" and self.index is not None:
            return self._search_faiss(query_embedding, top_k)
        else:
            return self._search_memory(query_embedding, top_k)

    def _search_chroma(self, query_embedding: np.ndarray,
                       top_k: int) -> List[RetrievalResult]:
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k
        )
        retrieval_results = []
        for i, doc_id in enumerate(results['ids'][0]):
            if doc_id in self.documents:
                doc = self.documents[doc_id]
                distance = results['distances'][0][i]
                relevance_score = 1.0 / (1.0 + distance)
                retrieval_results.append(RetrievalResult(
                    document=doc, relevance_score=relevance_score,
                    excerpt=doc.content[:500]
                ))
        return retrieval_results

    def _search_faiss(self, query_embedding: np.ndarray,
                      top_k: int) -> List[RetrievalResult]:
        distances, indices = self.index.search(
            query_embedding.reshape(1, -1), top_k
        )
        retrieval_results = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(self._faiss_id_map):
                doc_id = self._faiss_id_map[idx]
                doc = self.documents.get(doc_id)
                if doc:
                    distance = distances[0][i]
                    relevance_score = 1.0 / (1.0 + distance)
                    retrieval_results.append(RetrievalResult(
                        document=doc, relevance_score=relevance_score,
                        excerpt=doc.content[:500]
                    ))
        return retrieval_results

    def _search_memory(self, query_embedding: np.ndarray,
                       top_k: int) -> List[RetrievalResult]:
        if not self.embeddings:
            return []
        similarities = {}
        for doc_id, doc_emb in self.embeddings.items():
            dot_product = np.dot(query_embedding, doc_emb)
            norm_query = np.linalg.norm(query_embedding)
            norm_doc = np.linalg.norm(doc_emb)
            if norm_query > 0 and norm_doc > 0:
                similarity = dot_product / (norm_query * norm_doc)
                similarities[doc_id] = similarity

        sorted_docs = sorted(
            similarities.items(), key=lambda x: x[1], reverse=True
        )[:top_k]

        retrieval_results = []
        for doc_id, score in sorted_docs:
            doc = self.documents[doc_id]
            retrieval_results.append(RetrievalResult(
                document=doc, relevance_score=float(score),
                excerpt=doc.content[:500]
            ))
        return retrieval_results


class EngineeringKnowledgeBase:
    """
    Main RAG system for engineering knowledge.

    PRIMARY AUTHORITATIVE REFERENCES:
    - ETAP Official Manuals (knowledge_base/extracted/etap/)
    - Zenon SCADA Manuals (knowledge_base/extracted/zenon/)

    All agents MUST consult these references before any operation.
    """

    # MANDATORY REFERENCE INSTRUCTIONS
    MANDATORY_REFERENCE = """
    ╔══════════════════════════════════════════════════════════════════╗
    ║         PRIMARY REFERENCE - MANDATORY FOR ALL AGENTS             ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║                                                                  ║
    ║  The official ETAP and Zenon manuals are your PRIMARY and        ║
    ║  AUTHORITATIVE references. You MUST:                             ║
    ║                                                                  ║
    ║  1. ALWAYS consult the knowledge base BEFORE any operation       ║
    ║  2. FOLLOW procedures EXACTLY as documented in the manuals       ║
    ║  3. CITE the specific document and section in every response     ║
    ║  4. NEVER guess — if info is missing, say:                       ║
    ║     "Not documented in ETAP/Zenon official manuals"              ║
    ║  5. Query the RAG engine:                                        ║
    ║     from knowledge.rag_engine import get_knowledge_base          ║
    ║     kb = get_knowledge_base()                                    ║
    ║     results = kb.query_etap_manuals("your query")                ║
    ║     results = kb.query_zenon_manuals("your query")               ║
    ║                                                                  ║
    ║  VIOLATION of these rules is NOT PERMITTED.                      ║
    ╚══════════════════════════════════════════════════════════════════╝
    """

    def __init__(self, embedding_model: Optional[EmbeddingModel] = None,
                 vector_db: Optional[VectorDatabase] = None):
        self.embedding_model = embedding_model or EmbeddingModel()
        self.vector_db = vector_db or VectorDatabase()
        self.logger = logging.getLogger("knowledge_base")

        # Dimension check for FAISS
        if hasattr(self.embedding_model, 'model') and self.embedding_model.model is not None:
            test_emb = self.embedding_model.encode(["test"])
            actual_dim = test_emb.shape[1]
            if self.vector_db.db_type == "faiss" and self.vector_db.index is not None:
                faiss_dim = self.vector_db.index.d
                if actual_dim != faiss_dim:
                    import faiss
                    self.vector_db.index = faiss.IndexFlatL2(actual_dim)

        # Track loaded manuals
        self._etap_docs_loaded = False
        self._zenon_docs_loaded = False
        self._etap_text_cache: Dict[str, str] = {}
        self._zenon_text_cache: Dict[str, str] = {}

        # Load default standards + ETAP/Zenon manuals
        self._load_default_standards()
        self.load_etap_zenon_manuals()

    def _load_default_standards(self):
        """Load default engineering standards into knowledge base."""
        standards = self._get_default_standards_content()
        for std_data in standards:
            doc = EngineeringDocument(
                doc_id=std_data['doc_id'],
                title=std_data['title'],
                source=std_data['source'],
                standard_number=std_data.get('standard_number'),
                content=std_data['content'],
                metadata=std_data.get('metadata', {})
            )
            embedding = self.embedding_model.encode([std_data['content']])[0]
            self.vector_db.add_document(doc, embedding)
        self.logger.info(f"Loaded {len(standards)} default engineering standards")

    # ------------------------------------------------------------------
    # ETAP & Zenon Manual Loading
    # ------------------------------------------------------------------

    def load_etap_zenon_manuals(self):
        """Load extracted ETAP and Zenon manual text into the knowledge base.

        Reads from knowledge_base/extracted/etap/ and knowledge_base/extracted/zenon/
        directories. If extracted text is not found, logs a warning with instructions
        to run the ingestion script.
        """
        project_root = Path(__file__).resolve().parent.parent
        extracted_base = project_root / "knowledge_base" / "extracted"

        etap_dir = extracted_base / "etap"
        zenon_dir = extracted_base / "zenon"

        # Load ETAP manuals
        if etap_dir.exists():
            self._load_manual_directory(etap_dir, "ETAP", self._etap_text_cache)
            self._etap_docs_loaded = True
        else:
            self.logger.warning(
                "ETAP extracted manuals not found at %s. "
                "Run: python -m knowledge_base.ingest_manuals",
                etap_dir
            )

        # Load Zenon manuals
        if zenon_dir.exists():
            self._load_manual_directory(zenon_dir, "Zenon", self._zenon_text_cache)
            self._zenon_docs_loaded = True
        else:
            self.logger.warning(
                "Zenon extracted manuals not found at %s. "
                "Run: python -m knowledge_base.ingest_manuals",
                zenon_dir
            )

    def _load_manual_directory(self, directory: Path, source: str,
                               cache: Dict[str, str]):
        """Load all text files from a directory into the knowledge base."""
        loaded = 0

        # Load chunk JSON files (preferred — pre-chunked)
        for chunks_file in sorted(directory.glob("*_chunks.json")):
            try:
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_id = data["doc_id"]
                title = data.get("title", doc_id)
                category = data.get("category", "general")
                priority = data.get("priority", "MEDIUM")
                chunks = data.get("chunks", [])

                # Cache full text
                full_text = "\n".join(chunks)
                cache[doc_id] = full_text

                # Add each chunk as a separate document
                for i, chunk_text in enumerate(chunks):
                    if not chunk_text.strip():
                        continue
                    chunk_doc = EngineeringDocument(
                        doc_id=f"{doc_id}_chunk_{i}",
                        title=f"{title} (chunk {i+1}/{len(chunks)})",
                        source=source,
                        content=chunk_text,
                        metadata={
                            "category": category,
                            "priority": priority,
                            "original_doc": doc_id,
                            "chunk_index": i
                        }
                    )
                    embedding = self.embedding_model.encode([chunk_text])[0]
                    self.vector_db.add_document(chunk_doc, embedding)

                loaded += 1
            except Exception as exc:
                self.logger.warning("Failed to load %s: %s", chunks_file, exc)

        # Fallback: load raw .txt files if no chunks exist
        if loaded == 0:
            for txt_file in sorted(directory.glob("*.txt")):
                try:
                    doc_id = txt_file.stem
                    text = txt_file.read_text(encoding='utf-8')
                    if not text.strip():
                        continue
                    cache[doc_id] = text
                    doc = EngineeringDocument(
                        doc_id=doc_id,
                        title=doc_id.replace('_', ' ').title(),
                        source=source,
                        content=text
                    )
                    embedding = self.embedding_model.encode([text])[0]
                    self.vector_db.add_document(doc, embedding)
                    loaded += 1
                except Exception as exc:
                    self.logger.warning("Failed to load %s: %s", txt_file, exc)

        self.logger.info(f"Loaded {loaded} {source} manual documents")

    # ------------------------------------------------------------------
    # Specialized Query Methods
    # ------------------------------------------------------------------

    def query_etap_manuals(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Query ETAP manuals for specific procedures and information.

        This is the PRIMARY reference for all ETAP operations.

        Parameters
        ----------
        query : str
            Natural language query about ETAP operations.
        top_k : int
            Number of results to return.

        Returns
        -------
        List[RetrievalResult]
            Relevant ETAP documentation excerpts.
        """
        if not self._etap_docs_loaded:
            self.logger.warning("ETAP manuals not loaded. Run ingest_manuals first.")
            return []

        query_embedding = self.embedding_model.encode([f"ETAP {query}"])[0]
        results = self.vector_db.search(query_embedding, top_k)

        # Filter to only ETAP sources
        etap_results = [r for r in results if r.document.source == "ETAP"]
        return etap_results[:top_k]

    def query_zenon_manuals(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Query Zenon SCADA manuals for SCADA/HMI procedures.

        This is the PRIMARY reference for SCADA operations.

        Parameters
        ----------
        query : str
            Natural language query about Zenon SCADA operations.
        top_k : int
            Number of results to return.

        Returns
        -------
        List[RetrievalResult]
            Relevant Zenon documentation excerpts.
        """
        if not self._zenon_docs_loaded:
            self.logger.warning("Zenon manuals not loaded. Run ingest_manuals first.")
            return []

        query_embedding = self.embedding_model.encode([f"Zenon SCADA {query}"])[0]
        results = self.vector_db.search(query_embedding, top_k)

        # Filter to only Zenon sources
        zenon_results = [r for r in results if r.document.source == "Zenon"]
        return zenon_results[:top_k]

    def query_all_manuals(self, query: str, top_k: int = 5) -> Dict[str, List[RetrievalResult]]:
        """Query both ETAP and Zenon manuals simultaneously.

        Returns
        -------
        Dict with 'etap' and 'zenon' keys containing relevant results.
        """
        return {
            "etap": self.query_etap_manuals(query, top_k),
            "zenon": self.query_zenon_manuals(query, top_k),
        }

    def get_etap_procedure(self, operation: str) -> Dict:
        """Get the official ETAP procedure for a specific operation.

        AUTHORITATIVE source — all agents MUST use this before ETAP operations.
        """
        results = self.query_etap_manuals(operation, top_k=10)

        if not results:
            return {
                "found": False,
                "operation": operation,
                "message": f"Procedure for '{operation}' not found in ETAP manuals",
                "recommendation": "Consult ETAP support or run: python -m knowledge_base.ingest_manuals"
            }

        procedure = {
            "found": True,
            "operation": operation,
            "sources": [],
            "content": [],
            "references": []
        }

        for result in results:
            doc = result.document
            procedure["sources"].append({
                "title": doc.title,
                "document_id": doc.metadata.get("original_doc", doc.doc_id),
                "relevance": result.relevance_score
            })
            procedure["content"].append(result.excerpt)
            procedure["references"].append(
                f"[{doc.source}] {doc.title} (relevance: {result.relevance_score:.2f})"
            )

        return procedure

    def get_zenon_procedure(self, operation: str) -> Dict:
        """Get the official Zenon SCADA procedure for a specific operation.

        AUTHORITATIVE source — all agents MUST use this before SCADA operations.
        """
        results = self.query_zenon_manuals(operation, top_k=10)

        if not results:
            return {
                "found": False,
                "operation": operation,
                "message": f"Procedure for '{operation}' not found in Zenon manuals",
                "recommendation": "Consult COPA-DATA support or run: python -m knowledge_base.ingest_manuals"
            }

        procedure = {
            "found": True,
            "operation": operation,
            "sources": [],
            "content": [],
            "references": []
        }

        for result in results:
            doc = result.document
            procedure["sources"].append({
                "title": doc.title,
                "document_id": doc.metadata.get("original_doc", doc.doc_id),
                "relevance": result.relevance_score
            })
            procedure["content"].append(result.excerpt)
            procedure["references"].append(
                f"[{doc.source}] {doc.title} (relevance: {result.relevance_score:.2f})"
            )

        return procedure

    # ------------------------------------------------------------------
    # Original Methods (preserved for backward compatibility)
    # ------------------------------------------------------------------

    def _get_default_standards_content(self) -> List[Dict]:
        """Get default engineering standards content."""
        return [
            {
                'doc_id': 'ieee_519_2022_voltage_thd',
                'title': 'IEEE 519-2022 Voltage THD Limits',
                'source': 'IEEE',
                'standard_number': '519-2022',
                'content': """IEEE 519-2022 Table 1: Voltage Distortion Limits
For systems rated 1.0 kV and below: Individual harmonic 5.0%, THD 8.0%
For systems rated 1.0 kV through 69 kV: Individual harmonic 3.0%, THD 5.0%
For systems rated 69.001 kV through 161 kV: Individual harmonic 1.5%, THD 2.5%
For systems rated above 161 kV: Individual harmonic 1.0%, THD 1.5%""",
                'metadata': {'category': 'power_quality', 'topic': 'harmonics'}
            },
            {
                'doc_id': 'iec_60909_fault_types',
                'title': 'IEC 60909 Short-Circuit Current Calculation',
                'source': 'IEC',
                'standard_number': '60909-0:2016',
                'content': """IEC 60909-0:2016 Short-circuit current calculation methods.
Fault Types: 1) Three-phase (balanced): Ik", ip = kappa*sqrt(2)*Ik"
2) Line-to-ground: If = 3*V/(Z1+Z2+Z0)
3) Line-to-line: If = V/(Z1+Z2)
4) Double line-to-ground: Complex all-sequence calculation
Voltage Factor c: c_max=1.05 or 1.10, c_min=0.95""",
                'metadata': {'category': 'fault_analysis', 'topic': 'short_circuit'}
            },
            {
                'doc_id': 'ieee_1584_arc_flash',
                'title': 'IEEE 1584-2018 Arc Flash Hazard Calculation',
                'source': 'IEEE',
                'standard_number': '1584-2018',
                'content': """IEEE 1584-2018 Incident Energy Calculation.
Range: 208V-15kV, 500A-106kA, gap 13-152mm
log(Iarc) = K + 0.662*log(Ibf) + 0.0966*V + 0.000526*G + 0.5588*V*log(Ibf) - 0.00304*G*log(Ibf)
E = 4.184 * Cf * En * (t/0.2) * (610^x / D^x)
PPE Categories: Cat0<1.2, Cat1:1.2-4, Cat2:4-8, Cat3:8-25, Cat4:25-40 cal/cm2""",
                'metadata': {'category': 'safety', 'topic': 'arc_flash'}
            },
            {
                'doc_id': 'iec_60255_protection_curves',
                'title': 'IEC 60255 Overcurrent Relay Characteristics',
                'source': 'IEC',
                'standard_number': '60255',
                'content': """IEC 60255 Inverse Time-Current Characteristics.
Standard Inverse: t = TMS * 0.14 / ((I/Ip)^0.02 - 1)
Very Inverse: t = TMS * 13.5 / ((I/Ip) - 1)
Extremely Inverse: t = TMS * 80 / ((I/Ip)^2 - 1)
Coordination margin: 0.2-0.3 seconds minimum""",
                'metadata': {'category': 'protection', 'topic': 'relays'}
            },
            {
                'doc_id': 'iec_61850_scada',
                'title': 'IEC 61850 SCADA Communication Standard',
                'source': 'IEC',
                'standard_number': '61850',
                'content': """IEC 61850 Communication Networks for Power Utility Automation.
Defines: GOOSE messaging, Sampled Values, MMS protocol, SCL configuration language
Key concepts: Logical Nodes, Data Objects, ACSI services, GOOSE/SV multicast
Used by: zenon SCADA (COPA-DATA) for substation automation integration""",
                'metadata': {'category': 'communication', 'topic': 'scada'}
            },
            {
                'doc_id': 'ieee_399_load_flow',
                'title': 'IEEE 399 Brown Book - Load Flow Analysis Methods',
                'source': 'IEEE',
                'standard_number': '399',
                'content': """IEEE 399: Load Flow Methods - Gauss-Seidel (simple/slow),
Newton-Raphson (fast quadratic convergence, industry standard),
Fast Decoupled (P-theta/Q-V decoupling, good for transmission).
Convergence: Power mismatch <0.001pu, Voltage change <0.0001pu
Bus types: Slack(V,theta), PV(P,V), PQ(P,Q)""",
                'metadata': {'category': 'analysis', 'topic': 'load_flow'}
            }
        ]

    def ingest_document(self, doc: EngineeringDocument):
        """Ingest new engineering document into knowledge base."""
        embedding = self.embedding_model.encode([doc.content])[0]
        self.vector_db.add_document(doc, embedding)
        self.logger.info(f"Ingested document: {doc.doc_id}")

    def retrieve_knowledge(self, query: str,
                          top_k: int = 5) -> List[RetrievalResult]:
        """Retrieve relevant engineering knowledge for a query."""
        query_embedding = self.embedding_model.encode([query])[0]
        results = self.vector_db.search(query_embedding, top_k)
        self.logger.info(f"Retrieved {len(results)} documents for query: {query[:50]}...")
        return results

    def check_compliance(self, calculation_type: str,
                         parameters: Dict) -> Dict:
        """Check if calculation parameters comply with standards."""
        query = f"{calculation_type} standards requirements limits"
        results = self.retrieve_knowledge(query, top_k=3)

        compliance_result = {
            'calculation_type': calculation_type,
            'compliant': True,
            'violations': [],
            'references': [],
            'recommendations': []
        }

        for result in results:
            doc = result.document
            compliance_result['references'].append({
                'title': doc.title,
                'source': doc.source,
                'standard_number': doc.standard_number,
                'relevance_score': result.relevance_score
            })
            violations = self._check_specific_compliance(
                calculation_type, parameters, doc
            )
            if violations:
                compliance_result['compliant'] = False
                compliance_result['violations'].extend(violations)

        return compliance_result

    def _check_specific_compliance(self, calc_type: str,
                                   params: Dict,
                                   doc: EngineeringDocument) -> List[str]:
        violations = []
        if calc_type == 'arc_flash' and 'voltage_kv' in params:
            voltage = params['voltage_kv']
            if voltage < 0.208 or voltage > 15.0:
                violations.append(f"Voltage {voltage} kV outside IEEE 1584 range (0.208-15 kV)")
        elif calc_type == 'harmonic' and 'thd_voltage' in params:
            thd = params['thd_voltage']
            if thd > 8.0:
                violations.append(f"Voltage THD {thd}% exceeds IEEE 519 limit (8% for <1kV)")
        elif calc_type == 'voltage' and 'magnitude_pu' in params:
            v_mag = params['magnitude_pu']
            if v_mag < 0.95 or v_mag > 1.05:
                violations.append(f"Voltage {v_mag} pu outside acceptable range (0.95-1.05)")
        return violations

    def generate_citation(self, results: List[RetrievalResult]) -> str:
        """Generate formatted citation for retrieved documents."""
        citations = []
        for result in results:
            doc = result.document
            citation = f"[{doc.source} {doc.standard_number or ''}] {doc.title}"
            citations.append(citation)
        return "; ".join(citations)

    def get_mandatory_instructions(self) -> str:
        """Get the mandatory reference instructions for all agents."""
        return self.MANDATORY_REFERENCE


# Singleton instance
_knowledge_base = None

def get_knowledge_base() -> EngineeringKnowledgeBase:
    """Get or create knowledge base singleton."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = EngineeringKnowledgeBase()
    return _knowledge_base
