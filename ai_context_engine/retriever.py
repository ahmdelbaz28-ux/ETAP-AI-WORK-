"""
AI Context Engine - Code Retriever and Compressor
Implements Phase 2: Semantic retrieval from ChromaDB + Lexical & Semantic Compression (Pruning).
"""

import logging
from pathlib import Path
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_context_engine_retriever")

try:
    import chromadb

    CHROMA_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    CHROMA_AVAILABLE = False
    logger.warning(f"chromadb not available ({e}).")


class CodeCompressor:
    """Compresses retrieved code chunks to respect token budgets and prune irrelevant details."""

    @staticmethod
    def get_token_estimate(text: str) -> int:
        """Rough token estimator (4 characters per token as a general heuristic)."""
        return len(text) // 4

    @classmethod
    def compress_chunks(cls, chunks: List[Dict], query: str, max_tokens: int = 2000) -> List[Dict]:
        """
        Compresses chunks using Jaccard lexical overlap ranking and token budget enforcement.
        Keeps highest-scoring code snippets within the max_tokens limit.
        """
        query_words = set(query.lower().split())
        scored_chunks = []

        for chunk in chunks:
            code = chunk.get("code", "")
            code_words = set(code.lower().split())

            # Calculate Jaccard similarity overlap as a secondary ranker to semantic vector search
            intersection = query_words.intersection(code_words)
            union = query_words.union(code_words)
            jaccard_score = len(intersection) / len(union) if union else 0.0

            scored_chunks.append(
                {
                    **chunk,
                    "jaccard_score": jaccard_score,
                    "estimated_tokens": cls.get_token_estimate(code),
                }
            )

        # Sort by Jaccard score (highest first) to prioritize chunks containing query terms
        scored_chunks.sort(key=lambda x: x["jaccard_score"], reverse=True)

        compressed_chunks = []
        accumulated_tokens = 0

        for chunk in scored_chunks:
            tokens = chunk["estimated_tokens"]
            if accumulated_tokens + tokens <= max_tokens:
                compressed_chunks.append(chunk)
                accumulated_tokens += tokens
            else:
                # If chunk is too big, try to crop or just skip it
                remaining_tokens = max_tokens - accumulated_tokens
                if remaining_tokens > 200:  # Only crop if there's decent space left
                    lines = chunk["code"].splitlines()
                    cropped_code = []
                    current_est = 0
                    for line in lines:
                        line_tokens = cls.get_token_estimate(line)
                        if current_est + line_tokens <= remaining_tokens:
                            cropped_code.append(line)
                            current_est += line_tokens
                        else:
                            break
                    if cropped_code:
                        chunk["code"] = (
                            "\n".join(cropped_code)
                            + "\n# ... [Rest of code pruned to fit context budget]"
                        )
                        compressed_chunks.append(chunk)
                        accumulated_tokens += current_est
                break

        return compressed_chunks


class CodeRetriever:
    def __init__(self, index_dir: str, embedding_function=None):
        self.index_dir = Path(index_dir)
        self.client = None
        self.collection = None

        if CHROMA_AVAILABLE and self.index_dir.exists():
            try:
                self.client = chromadb.PersistentClient(path=str(self.index_dir))
                self.collection = self.client.get_collection(
                    name="code_context", embedding_function=embedding_function
                )
            except Exception as e:
                logger.error(f"Failed to load Chroma collection: {e}")

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """Query ChromaDB and return raw matching code chunks."""
        if not CHROMA_AVAILABLE or not self.collection:
            logger.warning("ChromaDB not initialized or code_context collection missing.")
            return []

        try:
            results = self.collection.query(query_texts=[query], n_results=top_k)

            chunks = []
            if results and results.get("documents"):
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                ids = results["ids"][0]

                for idx, doc in enumerate(documents):
                    chunks.append(
                        {
                            "id": ids[idx],
                            "code": doc,
                            "name": metadatas[idx].get("name", ""),
                            "type": metadatas[idx].get("type", ""),
                            "filepath": metadatas[idx].get("filepath", ""),
                        }
                    )
            return chunks
        except Exception as e:
            logger.error(f"Error querying index: {e}")
            return []

    def retrieve_and_compress(
        self, query: str, top_k: int = 5, max_tokens: int = 2000
    ) -> List[Dict]:
        """Fetches raw chunks and compresses them using Jaccard pruning."""
        raw_chunks = self.retrieve(query, top_k=top_k)
        return CodeCompressor.compress_chunks(raw_chunks, query, max_tokens=max_tokens)
