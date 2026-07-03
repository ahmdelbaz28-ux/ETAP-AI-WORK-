"""
Zenon User Guide RAG Engine
===========================
Specialized RAG (Retrieval-Augmented Generation) engine for Zenon SCADA User Guide.

This engine:
1. Loads extracted text from Zenon manuals
2. Retrieves relevant information for SCADA configuration queries
3. Provides authoritative answers based on official documentation

MANDATORY RULE:
- This guide is the PRIMARY reference for all Zenon/SCADA operations
- All decisions must be validated against this guide
- If information is not found, explicitly state it
"""

import json
from pathlib import Path


class ZenonGuideRAG:
    """
    RAG Engine specialized for Zenon SCADA User Guide.
    This is the AUTHORITATIVE source for all Zenon SCADA operations.
    """

    MANDATORY_INSTRUCTIONS = """
    ╔════════════════════════════════════════════════════════════════════════════╗
    ║                    ZENON USER GUIDE - MANDATORY RULES                      ║
    ╠════════════════════════════════════════════════════════════════════════════╣
    ║                                                                            ║
    ║  1. This guide is the PRIMARY and AUTHORITATIVE reference for ALL Zenon    ║
    ║     SCADA configurations. No other source takes precedence.                ║
    ║                                                                            ║
    ║  2. BEFORE performing ANY SCADA integration or configuration, you MUST:    ║
    ║     - Query this guide for the correct procedure                           ║
    ║     - Verify the steps match the official documentation                    ║
    ║     - Follow the exact sequence specified in the guide                     ║
    ║                                                                            ║
    ║  3. If this guide provides specific instructions:                          ║
    ║     - Follow them EXACTLY as written                                       ║
    ║     - Do NOT deviate or improvise                                          ║
    ║                                                                            ║
    ║  4. If information is NOT FOUND in this guide:                             ║
    ║     - Explicitly state: "Not documented in Zenon User Guide"               ║
    ║     - Do NOT guess or assume                                               ║
    ║                                                                            ║
    ║  5. When providing answers:                                                ║
    ║     - Cite the specific section/page from the guide                        ║
    ║     - Quote exact text when relevant                                       ║
    ║                                                                            ║
    ║  6. VIOLATION of these rules is NOT PERMITTED.                             ║
    ║                                                                            ║
    ╚════════════════════════════════════════════════════════════════════════════╝
    """

    def __init__(self, guide_path: str = "zenon_user_guide"):
        self.guide_path = Path(guide_path)
        self.chunks_dir = self.guide_path / "chunks"
        self.index_dir = self.guide_path / "index"

        self.documents: list[dict] = []
        self.chunks: list[str] = []
        self.chunk_metadata: list[dict] = []

        self._load_guide()

    def _load_guide(self):
        """Load the Zenon guide from extracted files."""
        master_index_file = self.index_dir / "master_index.json"
        if master_index_file.exists():
            try:
                with open(master_index_file, encoding="utf-8") as f:
                    master_index = json.load(f)

                for doc in master_index.get("documents", []):
                    self.documents.append(
                        {
                            "filename": doc["filename"],
                            "source": doc["source"],
                            "pages": doc["pages"],
                            "characters": doc["characters"],
                        },
                    )

                    for idx, chunk in enumerate(doc.get("chunks", [])):
                        self.chunks.append(chunk)
                        self.chunk_metadata.append(
                            {
                                "document": doc["filename"],
                                "chunk_index": idx,
                                "source": doc["source"],
                            },
                        )
            except Exception as e:
                print(f"Error loading Zenon master index: {e}")
        else:
            print("Warning: Zenon master index not found.")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search the Zenon guide for relevant information."""
        if not self.chunks:
            return []

        results = []
        query_terms = query.lower().split()

        for idx, chunk in enumerate(self.chunks):
            chunk_lower = chunk.lower()
            score = 0
            for term in query_terms:
                if term in chunk_lower:
                    score += chunk_lower.count(term)

            if score > 0:
                results.append(
                    {"chunk": chunk, "score": score, "metadata": self.chunk_metadata[idx]},
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_zenon_procedure(self, operation: str) -> dict:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """Get the official Zenon procedure for a specific operation."""
        results = self.search(operation, top_k=5)

        if not results:
            return {
                "found": False,
                "operation": operation,
                "message": f"Procedure for '{operation}' not found in Zenon User Guide",
                "recommendation": "Consult Zenon documentation or support",
            }

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

            lines = chunk.split("\n")
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                    procedure["steps"].append(line)

                if (
                    "warning" in line.lower()
                    or "caution" in line.lower()
                    or "danger" in line.lower()
                ):
                    procedure["warnings"].append(line)

                if "note" in line.lower() or "important" in line.lower():
                    procedure["notes"].append(line)

        return procedure

    def validate_zenon_operation(self, operation: str, proposed_steps: list[str]) -> dict:
        """Validate proposed Zenon SCADA steps against the official guide."""
        official = self.get_zenon_procedure(operation)

        if not official["found"]:
            return {
                "valid": False,
                "reason": "Operation not documented in Zenon User Guide",
                "recommendation": "Cannot validate - consult Zenon support",
            }

        validation = {
            "valid": True,
            "operation": operation,
            "official_steps": official["steps"],
            "proposed_steps": proposed_steps,
            "compliance": [],
            "issues": [],
            "warnings": official["warnings"],
        }

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
        return self.MANDATORY_INSTRUCTIONS

    def query(self, question: str) -> dict:
        """Answer a question about Zenon using the official guide."""
        results = self.search(question, top_k=5)

        if not results:
            return {
                "answered": False,
                "question": question,
                "answer": "Information not found in Zenon User Guide",
                "sources": [],
                "confidence": 0,
            }

        answer_parts = []
        sources = []

        for result in results:
            chunk = result["chunk"]
            metadata = result["metadata"]
            answer_parts.append(chunk)
            sources.append({"document": metadata["document"], "relevance": result["score"]})

        return {
            "answered": True,
            "question": question,
            "answer": "\n\n".join(answer_parts),
            "sources": sources,
            "confidence": results[0]["score"] if results else 0,
        }
