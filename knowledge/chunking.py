"""Engineering document chunker for RAG knowledge ingestion.

Implements token-based chunking with 400-600 tokens per chunk, 15% overlap,
and structured metadata linkage to engineering standards (IEEE/IEC/NFPA).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TextChunk:
    """A semantic chunk of an engineering standard or technical document."""

    chunk_id: str
    content: str
    doc_id: str
    standard: str
    clause: str
    section_title: str
    chunk_index: int
    total_chunks: int
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "doc_id": self.doc_id,
            "standard": self.standard,
            "clause": self.clause,
            "section_title": self.section_title,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count (~4 characters per token for English, ~2.5 for Arabic)."""
    if not text:
        return 0
    # Check if text contains Arabic characters
    has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))
    char_per_token = 2.5 if has_arabic else 4.0
    return max(1, int(len(text) / char_per_token))


def _split_into_paragraphs_or_sentences(text: str) -> List[str]:
    """Split text into coherent blocks (paragraphs, or sentences if paragraphs are huge)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    blocks = []
    for p in paragraphs:
        if estimate_tokens(p) > 500:
            # Sub-split long paragraph by sentence boundaries
            sentences = [s.strip() for s in re.split(r"(?<=[.!?؟\n])\s+", p) if s.strip()]
            blocks.extend(sentences)
        else:
            blocks.append(p)
    return blocks


def chunk_document(
    text: str,
    doc_id: str,
    standard: str = "",
    clause: str = "",
    section_title: str = "",
    min_chunk_tokens: int = 400,
    max_chunk_tokens: int = 600,
    overlap_pct: float = 0.15,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> List[TextChunk]:
    """Chunk an engineering document into semantic chunks of 400-600 tokens with 15% overlap.

    Args:
        text: Document body text.
        doc_id: Unique document identifier.
        standard: Associated standard (e.g. 'IEC 60909', 'IEEE 1584').
        clause: Standard clause or section reference.
        section_title: Title of the document section.
        min_chunk_tokens: Target minimum tokens per chunk.
        max_chunk_tokens: Hard maximum tokens per chunk.
        overlap_pct: Fraction of chunk tokens to overlap (default 0.15 = 15%).
        extra_metadata: Additional arbitrary metadata.

    Returns:
        List of TextChunk instances with sequence metadata.
    """
    if not text or not text.strip():
        return []

    blocks = _split_into_paragraphs_or_sentences(text)
    raw_chunks: List[str] = []
    current_blocks: List[str] = []
    current_tokens = 0

    target_overlap_tokens = int(max_chunk_tokens * overlap_pct)

    for block in blocks:
        block_tokens = estimate_tokens(block)
        if current_tokens + block_tokens > max_chunk_tokens and current_blocks:
            # Finalize current chunk
            chunk_text = "\n\n".join(current_blocks)
            raw_chunks.append(chunk_text)

            # Compute overlap blocks for next chunk
            overlap_blocks = []
            overlap_accum = 0
            for b in reversed(current_blocks):
                b_tok = estimate_tokens(b)
                if overlap_accum + b_tok <= target_overlap_tokens:
                    overlap_blocks.insert(0, b)
                    overlap_accum += b_tok
                else:
                    break

            current_blocks = overlap_blocks + [block]
            current_tokens = sum(estimate_tokens(b) for b in current_blocks)
        else:
            current_blocks.append(block)
            current_tokens += block_tokens

    if current_blocks:
        raw_chunks.append("\n\n".join(current_blocks))

    total = len(raw_chunks)
    meta = extra_metadata or {}
    chunks: List[TextChunk] = []

    for i, c_text in enumerate(raw_chunks):
        c_tokens = estimate_tokens(c_text)
        chunk = TextChunk(
            chunk_id=f"{doc_id}_chunk_{i + 1:03d}",
            content=c_text,
            doc_id=doc_id,
            standard=standard,
            clause=clause,
            section_title=section_title,
            chunk_index=i + 1,
            total_chunks=total,
            token_count=c_tokens,
            metadata=meta,
        )
        chunks.append(chunk)

    return chunks
