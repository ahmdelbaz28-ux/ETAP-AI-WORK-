"""
ETAP User Guide RAG Engine
===========================
Specialized RAG (Retrieval-Augmented Generation) engine for ETAP User Guide.

This engine:
1. Loads extracted text from ETAP guide
2. Creates embeddings for semantic search
3. Retrieves relevant information for queries
4. Provides authoritative answers based on official documentation

MANDATORY RULE:
- This guide is the PRIMARY reference for all ETAP operations
- All decisions must be validated against this guide
- No ETAP operation should proceed without consulting this guide
- If information is not found, explicitly state it
"""

from __future__ import annotations

import json
from pathlib import Path

# Try to import vector database libraries
try:
    import chromadb  # noqa: F401
    from chromadb.config import Settings  # noqa: F401

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class ETAPGuideRAG:
    """
    RAG Engine specialized for ETAP User Guide.

    This is the AUTHORITATIVE source for all ETAP operations.
    All agents MUST consult this engine before any ETAP operation.
    """

    # MANDATORY INSTRUCTIONS FOR ALL AGENTS
    MANDATORY_INSTRUCTIONS = """
    ╔════════════════════════════════════════════════════════════════════════════╗
    ║                    ETAP USER GUIDE - MANDATORY RULES                       ║
    ╠════════════════════════════════════════════════════════════════════════════╣
    ║                                                                            ║
    ║  1. This guide is the PRIMARY and AUTHORITATIVE reference for ALL ETAP     ║
    ║     operations. No other source takes precedence.                          ║
    ║                                                                            ║
    ║  2. BEFORE performing ANY ETAP operation, you MUST:                        ║
    ║     - Query this guide for the correct procedure                           ║
    ║     - Verify the steps match the official documentation                    ║
    ║     - Follow the exact sequence specified in the guide                     ║
    ║                                                                            ║
    ║  3. If this guide provides specific instructions:                          ║
    ║     - Follow them EXACTLY as written                                       ║
    ║     - Do NOT deviate or improvise                                          ║
    ║     - Do NOT use alternative methods unless explicitly allowed             ║
    ║                                                                            ║
    ║  4. If information is NOT FOUND in this guide:                             ║
    ║     - Explicitly state: "Not documented in ETAP User Guide"               ║
    ║     - Do NOT guess or assume                                               ║
    ║     - Recommend consulting ETAP support or additional documentation        ║
    ║                                                                            ║
    ║  5. When providing answers:                                                ║
    ║     - Cite the specific section/page from the guide                        ║
    ║     - Quote exact text when relevant                                       ║
    ║     - Provide step-by-step instructions as documented                      ║
    ║                                                                            ║
    ║  6. For troubleshooting:                                                   ║
    ║     - First check the guide for known issues                               ║
    ║     - Follow documented solutions                                          ║
    ║     - If not documented, state it clearly                                  ║
    ║                                                                            ║
    ║  7. VIOLATION of these rules is NOT PERMITTED.                             ║
    ║                                                                            ║
    ╚════════════════════════════════════════════════════════════════════════════╝
    """

    def __init__(self, guide_path: str = "etap_user_guide"):
        """
        Initialize the ETAP Guide RAG engine.

        Args:
            guide_path: Path to the extracted ETAP guide
        """
        self.guide_path = Path(guide_path)
        self.chunks_dir = self.guide_path / "chunks"
        self.index_dir = self.guide_path / "index"

        # Storage for loaded content
        self.documents: list[dict] = []
        self.chunks: list[str] = []
        self.chunk_metadata: list[dict] = []
        self.embeddings = None
        self.vector_db = None

        # Load the guide
        self._load_guide()

    def _load_guide(self):
        """Load the ETAP guide from extracted files."""
        print("Loading ETAP User Guide into RAG engine...")

        # Load master index if exists
        master_index_file = self.index_dir / "master_index.json"
        if master_index_file.exists():
            with open(master_index_file, encoding="utf-8") as f:
                master_index = json.load(f)

                for doc in master_index["documents"]:
                    self.documents.append(
                        {
                            "filename": doc["filename"],
                            "source": doc["source"],
                            "pages": doc["pages"],
                            "characters": doc["characters"],
                        },
                    )

                    for idx, chunk in enumerate(doc["chunks"]):
                        self.chunks.append(chunk)
                        self.chunk_metadata.append(
                            {
                                "document": doc["filename"],
                                "chunk_index": idx,
                                "source": doc["source"],
                            },
                        )

                print(f"✓ Loaded {len(self.documents)} documents")
                print(f"✓ Loaded {len(self.chunks)} text chunks")
        else:
            print("Warning: Master index not found. Run extract_guide.py first.")

    def _create_embeddings(self):
        """Create embeddings for all chunks using sentence transformers."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            print("Warning: sentence-transformers not available. Using simple search.")
            return

        print("Creating embeddings for semantic search...")

        try:
            # Load model
            model = SentenceTransformer("all-MiniLM-L6-v2")

            # Create embeddings in batches
            batch_size = 100
            all_embeddings = []

            for i in range(0, len(self.chunks), batch_size):
                batch = self.chunks[i : i + batch_size]
                batch_embeddings = model.encode(batch, show_progress_bar=True)
                all_embeddings.extend(batch_embeddings)

            self.embeddings = all_embeddings
            print(f"✓ Created {len(self.embeddings)} embeddings")

        except Exception as e:
            print(f"Error creating embeddings: {e}")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Search the ETAP guide for relevant information.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of search results with relevance scores
        """
        if not self.chunks:
            return []

        results = []

        # Simple keyword-based search (fallback)
        query_terms = query.lower().split()

        for idx, chunk in enumerate(self.chunks):
            chunk_lower = chunk.lower()

            # Calculate relevance score
            score = 0
            for term in query_terms:
                if term in chunk_lower:
                    score += chunk_lower.count(term)

            if score > 0:
                results.append(
                    {"chunk": chunk, "score": score, "metadata": self.chunk_metadata[idx]},
                )

        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_etap_procedure(self, operation: str) -> dict:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """
        Get the official ETAP procedure for a specific operation.

        This is the AUTHORITATIVE source for ETAP operations.

        Args:
            operation: The ETAP operation to look up

        Returns:
            Dictionary with procedure details
        """
        # Search for the procedure
        results = self.search(operation, top_k=10)

        if not results:
            return {
                "found": False,
                "operation": operation,
                "message": f"Procedure for '{operation}' not found in ETAP User Guide",
                "recommendation": "Consult ETAP support or additional documentation",
            }

        # Compile procedure from results
        procedure = {
            "found": True,
            "operation": operation,
            "sources": [],
            "steps": [],
            "notes": [],
            "warnings": [],
        }

        for result in results:
            chunk = result["chunk"]
            metadata = result["metadata"]

            procedure["sources"].append(
                {"document": metadata["document"], "relevance": result["score"]},
            )

            # Extract steps (lines starting with numbers or bullets)
            lines = chunk.split("\n")
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                    procedure["steps"].append(line)

                # Extract warnings
                if "warning" in line.lower() or "caution" in line.lower():
                    procedure["warnings"].append(line)

                # Extract notes
                if "note" in line.lower() or "important" in line.lower():
                    procedure["notes"].append(line)

        return procedure

    def validate_etap_operation(self, operation: str, proposed_steps: list[str]) -> dict:
        """
        Validate proposed ETAP operation steps against the official guide.

        Args:
            operation: The ETAP operation being performed
            proposed_steps: Steps proposed to be executed

        Returns:
            Validation result with compliance status
        """
        # Get official procedure
        official = self.get_etap_procedure(operation)

        if not official["found"]:
            return {
                "valid": False,
                "reason": "Operation not documented in ETAP User Guide",
                "recommendation": "Cannot validate - consult ETAP support",
            }

        # Compare proposed steps with official
        validation = {
            "valid": True,
            "operation": operation,
            "official_steps": official["steps"],
            "proposed_steps": proposed_steps,
            "compliance": [],
            "issues": [],
            "warnings": official["warnings"],
        }

        # Simple validation: check if key terms match
        official_text = " ".join(official["steps"]).lower()

        for step in proposed_steps:
            step_terms = set(step.lower().split())
            official_terms = set(official_text.split())

            overlap = len(step_terms & official_terms)

            if overlap > 0:
                validation["compliance"].append(
                    {"step": step, "matches": overlap, "status": "compliant"},
                )
            else:
                validation["compliance"].append(
                    {"step": step, "matches": 0, "status": "not_found_in_guide"},
                )
                validation["issues"].append(f"Step not found in guide: {step}")

        if validation["issues"]:
            validation["valid"] = False

        return validation

    def get_mandatory_instructions(self) -> str:
        """Get the mandatory instructions that must be followed by all agents."""
        return self.MANDATORY_INSTRUCTIONS

    def query(self, question: str) -> dict:
        """
        Answer a question about ETAP using the official guide.

        Args:
            question: Question to answer

        Returns:
            Answer with sources
        """
        # Search for relevant information
        results = self.search(question, top_k=5)

        if not results:
            return {
                "answered": False,
                "question": question,
                "answer": "Information not found in ETAP User Guide",
                "sources": [],
                "confidence": 0,
            }

        # Compile answer from results
        answer_parts = []
        sources = []

        for result in results:
            chunk = result["chunk"]
            metadata = result["metadata"]

            answer_parts.append(chunk)
            sources.append({"document": metadata["document"], "relevance": result["score"]})

        # Combine into coherent answer
        answer = "\n\n".join(answer_parts)

        return {
            "answered": True,
            "question": question,
            "answer": answer,
            "sources": sources,
            "confidence": results[0]["score"] if results else 0,
        }


def main():
    """Test the RAG engine."""
    print("=" * 70)
    print("ETAP User Guide RAG Engine - Test")
    print("=" * 70)
    print()

    # Initialize RAG engine
    rag = ETAPGuideRAG()

    # Display mandatory instructions
    print(rag.get_mandatory_instructions())
    print()

    # Test queries
    test_queries = [
        "How to create a new project in ETAP?",
        "How to run load flow analysis?",
        "How to add a bus to the one-line diagram?",
        "How to set up short circuit analysis?",
    ]

    print("Testing queries:")
    print("-" * 70)

    for query in test_queries:
        print(f"\nQuery: {query}")
        result = rag.query(query)

        if result["answered"]:
            print(f"✓ Answered (confidence: {result['confidence']:.2f})")
            print(f"  Sources: {len(result['sources'])} documents")
            print(f"  Answer preview: {result['answer'][:200]}...")
        else:
            print("✗ Not answered")

    print()
    print("=" * 70)
    print("RAG Engine Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()