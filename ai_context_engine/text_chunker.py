"""
Text Chunker — Hierarchical Document Chunking
==============================================

A Python port of chunkr's hierarchical chunking algorithm (originally in Rust).
https://github.com/lumina-ai-inc/chunkr/blob/main/core/src/utils/services/chunking.rs

WHY THIS EXISTS:
The original chunkr project is a full Rust microservice (PostgreSQL + Redis +
S3 + GPU + VLM) — too heavy to embed directly. However, its chunking
algorithm is excellent for RAG: it respects document hierarchy (Title >
SectionHeader > Text), pairs captions with pictures/tables, and enforces
token budgets. We port just that algorithm to Python, zero new dependencies.

ADAPTER PATTERN (no conflict with existing code):
- This module is self-contained — imports only stdlib + typing
- It does NOT modify ai_context_engine/indexer.py (which indexes Python code)
- It does NOT modify knowledge/rag_engine.py (which indexes IEEE/IEC text)
- It IS consumed by the new document_ingestor.py module

ALGORITHM (from chunkr/core/src/utils/services/chunking.rs):
1. Walk segments in order
2. If segment is a Title/SectionHeader AND hierarchy level increased →
   finalize current chunk, start a new one
3. If segment is PageHeader/PageFooter AND ignore_headers_and_footers → skip
4. If segment is Picture/Table and next is Caption (or vice versa) →
   pair them together in the same chunk
5. Otherwise: add to current chunk if it fits within target_length (words),
   else finalize and start a new chunk

SEGMENT TYPES (from chunkr SegmentType enum):
    Caption, Footnote, Formula, ListItem, Page, PageFooter, PageHeader,
    Picture, SectionHeader, Table, Text, Title
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class SegmentType(str, Enum):  # noqa: UP042  (StrEnum is 3.11+ only; we support 3.10+)
    """All possible types for a document segment (mirrors chunkr's SegmentType).

    Inherits from (str, Enum) for JSON serialization compatibility with
    Python 3.10+ (enum.StrEnum was added in 3.11).
    """

    CAPTION = "Caption"
    FOOTNOTE = "Footnote"
    FORMULA = "Formula"
    LIST_ITEM = "ListItem"
    PAGE = "Page"
    PAGE_FOOTER = "PageFooter"
    PAGE_HEADER = "PageHeader"
    PICTURE = "Picture"
    SECTION_HEADER = "SectionHeader"
    TABLE = "Table"
    TEXT = "Text"
    TITLE = "Title"


# Hierarchy levels — higher = more important structurally.
# When we encounter a segment with higher hierarchy than the previous one,
# we finalize the current chunk and start fresh (respects document structure).
def _get_hierarchy_level(segment_type: SegmentType) -> int:
    """Return the hierarchy level for a segment type (higher = more structural)."""
    if segment_type == SegmentType.TITLE:
        return 3
    if segment_type == SegmentType.SECTION_HEADER:
        return 2
    return 1


@dataclass
class Segment:
    """A single document segment (paragraph, heading, image, table, etc.).

    Mirrors chunkr's Segment model. Only the fields needed for chunking
    are kept — content, segment_type, and optional page_number.
    """

    content: str
    segment_type: SegmentType = SegmentType.TEXT
    page_number: Optional[int] = None
    bbox: Optional[tuple[float, float, float, float]] = None
    confidence: Optional[float] = None
    # Optional metadata for source tracking (file path, section path, etc.)
    metadata: dict = field(default_factory=dict)

    def word_count(self) -> int:
        """Count words in the segment content (whitespace-separated)."""
        if not self.content:
            return 0
        return len(self.content.split())


@dataclass
class Chunk:
    """A group of related segments that form a single RAG chunk."""

    segments: List[Segment] = field(default_factory=list)

    @property
    def content(self) -> str:
        """Concatenate all segment contents into a single text block."""
        return "\n\n".join(s.content for s in self.segments if s.content)

    @property
    def word_count(self) -> int:
        """Total word count across all segments."""
        return sum(s.word_count() for s in self.segments)

    @property
    def segment_types(self) -> List[SegmentType]:
        """List of segment types in this chunk (for filtering/metadata)."""
        return [s.segment_type for s in self.segments]

    @property
    def page_numbers(self) -> List[int]:
        """Unique page numbers referenced by segments in this chunk."""
        return list({s.page_number for s in self.segments if s.page_number is not None})

    def to_dict(self) -> dict:
        """Serialize to dict for storage in ChromaDB / FAISS."""
        return {
            "content": self.content,
            "word_count": self.word_count,
            "segment_types": [st.value for st in self.segment_types],
            "page_numbers": self.page_numbers,
            "segment_count": len(self.segments),
            "metadata": {
                **{k: v for s in self.segments for k, v in s.metadata.items()},
            },
        }


@dataclass
class ChunkingConfig:
    """Configuration for the hierarchical chunker.

    Mirrors the relevant subset of chunkr's Configuration.chunk_processing.
    """

    target_length: int = 500
    """Target word count per chunk. 0 disables chunking (1 chunk per segment)."""

    ignore_headers_and_footers: bool = True
    """Skip PageHeader and PageFooter segments entirely."""

    tokenizer: Optional[str] = None
    """Optional tokenizer name (for future LLM token-count support)."""


def _finalize_and_start_new_chunk(chunks: List[Chunk], current_segments: List[Segment]) -> None:
    """Push the current segments as a Chunk, then clear the accumulator.

    Mirrors chunkr's `finalize_and_start_new_chunk` helper.
    """
    if current_segments:
        chunks.append(Chunk(segments=current_segments.copy()))
        current_segments.clear()


def hierarchical_chunking(segments: List[Segment], configuration: ChunkingConfig) -> List[Chunk]:
    """Hierarchical chunking of document segments.

    This is a direct Python port of chunkr's `hierarchical_chunking` function
    in core/src/utils/services/chunking.rs. The algorithm:

    1. Walks segments in order
    2. Starts a new chunk when a Title/SectionHeader increases hierarchy
    3. Pairs Picture/Table segments with adjacent Captions
    4. Enforces target_length (in words) per chunk
    5. Optionally skips PageHeader/PageFooter segments

    Args:
        segments: Ordered list of document segments to chunk
        configuration: Chunking parameters (target_length, etc.)

    Returns:
        List of Chunk objects, each containing 1+ related segments

    Raises:
        ValueError: If configuration.target_length is negative
    """
    if configuration.target_length < 0:
        raise ValueError("target_length must be >= 0")

    chunks: List[Chunk] = []
    current_segments: List[Segment] = []
    current_word_count = 0
    target_length = configuration.target_length
    ignore_headers_and_footers = configuration.ignore_headers_and_footers

    prev_hierarchy_level = 1
    segment_paired = False  # True if previous segment was paired with current

    for i, segment in enumerate(segments):
        segment_word_count = segment.word_count()
        current_hierarchy_level = _get_hierarchy_level(segment.segment_type)

        if segment.segment_type in (SegmentType.TITLE, SegmentType.SECTION_HEADER):
            # Structural break: if we're going UP in hierarchy, finalize the
            # current chunk so the new section starts fresh.
            if current_hierarchy_level > prev_hierarchy_level:
                _finalize_and_start_new_chunk(chunks, current_segments)
            current_segments.append(segment)
            current_word_count = segment_word_count

        elif segment.segment_type in (SegmentType.PAGE_HEADER, SegmentType.PAGE_FOOTER):
            if ignore_headers_and_footers:
                # Skip entirely — don't add to any chunk
                continue
            # If not ignoring: header/footer gets its own chunk (chunkr behavior)
            _finalize_and_start_new_chunk(chunks, current_segments)
            current_segments.append(segment)
            _finalize_and_start_new_chunk(chunks, current_segments)
            current_word_count = 0

        else:
            # Default chunking behavior for Text, ListItem, Picture, Table, Caption, etc.
            default_chunk_behavior = True

            # Picture/Table + Caption pairing (or Caption + Picture/Table)
            is_asset = segment.segment_type in (SegmentType.PICTURE, SegmentType.TABLE)
            is_caption = segment.segment_type == SegmentType.CAPTION

            if is_asset and not segment_paired:
                next_seg = segments[i + 1] if i + 1 < len(segments) else None
                next_is_caption = (
                    next_seg is not None and next_seg.segment_type == SegmentType.CAPTION
                )
                if next_is_caption:
                    caption_word_count = next_seg.word_count() if next_seg else 0
                    if current_word_count + segment_word_count + caption_word_count > target_length:
                        # Doesn't fit — start a new chunk with this asset + caption
                        _finalize_and_start_new_chunk(chunks, current_segments)
                        current_segments.append(segment)
                        current_word_count = segment_word_count
                        default_chunk_behavior = False
                        segment_paired = True  # Mark caption as paired

            if is_caption and not segment_paired:
                next_seg = segments[i + 1] if i + 1 < len(segments) else None
                next_is_asset = next_seg is not None and next_seg.segment_type in (
                    SegmentType.PICTURE,
                    SegmentType.TABLE,
                )
                if next_is_asset:
                    asset_word_count = next_seg.word_count() if next_seg else 0
                    if current_word_count + segment_word_count + asset_word_count > target_length:
                        _finalize_and_start_new_chunk(chunks, current_segments)
                        current_segments.append(segment)
                        current_word_count = segment_word_count
                        default_chunk_behavior = False
                        segment_paired = True  # Mark asset as paired

            if default_chunk_behavior:
                # Standard accumulation: add to current chunk if it fits
                if current_word_count + segment_word_count > target_length:
                    _finalize_and_start_new_chunk(chunks, current_segments)
                    current_segments.append(segment)
                    current_word_count = segment_word_count
                else:
                    current_segments.append(segment)
                    current_word_count += segment_word_count
                segment_paired = False  # Reset pairing flag after default behavior

        prev_hierarchy_level = current_hierarchy_level

    # Flush any remaining segments as the final chunk
    _finalize_and_start_new_chunk(chunks, current_segments)

    logger.debug(
        "hierarchical_chunking: %d segments → %d chunks (target_length=%d words)",
        len(segments),
        len(chunks),
        target_length,
    )
    return chunks


__all__ = [
    "SegmentType",
    "Segment",
    "Chunk",
    "ChunkingConfig",
    "hierarchical_chunking",
]
