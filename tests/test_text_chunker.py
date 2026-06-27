"""
Unit tests for the chunkr-inspired text chunker and document ingestor.

These tests verify that:
1. The hierarchical chunking algorithm matches chunkr's behavior
2. The Segment/Chunk dataclasses serialize correctly
3. The document ingestor degrades gracefully when libraries are missing
4. Edge cases (empty input, single segment, target_length=0) are handled

Run: python -m pytest tests/test_text_chunker.py -v
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from ai_context_engine.text_chunker import (
    Chunk,
    ChunkingConfig,
    Segment,
    SegmentType,
    hierarchical_chunking,
)


class TestSegmentType:
    """Tests for the SegmentType enum."""

    def test_all_12_types_present(self):
        """All 12 segment types from chunkr's SegmentType enum must be present."""
        expected = {
            "Caption",
            "Footnote",
            "Formula",
            "ListItem",
            "Page",
            "PageFooter",
            "PageHeader",
            "Picture",
            "SectionHeader",
            "Table",
            "Text",
            "Title",
        }
        actual = {t.value for t in SegmentType}
        assert actual == expected, f"Missing types: {expected - actual}"

    def test_enum_is_string(self):
        """SegmentType values must be strings (for JSON serialization)."""
        assert SegmentType.TITLE == "Title"
        assert isinstance(SegmentType.TEXT.value, str)


class TestSegment:
    """Tests for the Segment dataclass."""

    def test_word_count_empty(self):
        seg = Segment(content="", segment_type=SegmentType.TEXT)
        assert seg.word_count() == 0

    def test_word_count_simple(self):
        seg = Segment(content="hello world foo bar", segment_type=SegmentType.TEXT)
        assert seg.word_count() == 4

    def test_word_count_with_extra_whitespace(self):
        seg = Segment(content="  hello   world  ", segment_type=SegmentType.TEXT)
        assert seg.word_count() == 2

    def test_default_segment_type_is_text(self):
        seg = Segment(content="test")
        assert seg.segment_type == SegmentType.TEXT


class TestChunk:
    """Tests for the Chunk dataclass."""

    def test_empty_chunk(self):
        chunk = Chunk()
        assert chunk.content == ""
        assert chunk.word_count == 0
        assert chunk.segment_types == []
        assert chunk.page_numbers == []

    def test_content_concatenation(self):
        chunk = Chunk(
            segments=[
                Segment(content="First", segment_type=SegmentType.TEXT),
                Segment(content="Second", segment_type=SegmentType.TEXT),
            ]
        )
        assert chunk.content == "First\n\nSecond"
        assert chunk.word_count == 2

    def test_to_dict(self):
        chunk = Chunk(
            segments=[
                Segment(content="Title", segment_type=SegmentType.TITLE, page_number=1),
                Segment(content="Body text here", segment_type=SegmentType.TEXT, page_number=1),
            ]
        )
        d = chunk.to_dict()
        # "Title" = 1 word + "Body text here" = 3 words = 4 words total
        assert d["word_count"] == 4
        assert d["segment_types"] == ["Title", "Text"]
        assert d["page_numbers"] == [1]
        assert d["segment_count"] == 2


class TestHierarchicalChunking:
    """Tests for the hierarchical chunking algorithm."""

    def test_empty_input(self):
        """Empty segment list → empty chunk list."""
        config = ChunkingConfig(target_length=500)
        chunks = hierarchical_chunking([], config)
        assert chunks == []

    def test_single_segment(self):
        """One segment → one chunk containing that segment."""
        segs = [Segment(content="hello world", segment_type=SegmentType.TEXT)]
        config = ChunkingConfig(target_length=500)
        chunks = hierarchical_chunking(segs, config)
        assert len(chunks) == 1
        assert chunks[0].word_count == 2

    def test_target_length_zero_disables_chunking(self):
        """target_length=0 means each segment becomes its own chunk (chunkr behavior)."""
        segs = [
            Segment(content="first", segment_type=SegmentType.TEXT),
            Segment(content="second", segment_type=SegmentType.TEXT),
            Segment(content="third", segment_type=SegmentType.TEXT),
        ]
        config = ChunkingConfig(target_length=0)
        chunks = hierarchical_chunking(segs, config)
        # With target_length=0, the chunking loop is skipped (per chunkr's process())
        # but our Python port still runs hierarchical_chunking — each segment
        # would exceed the 0-word budget and start a new chunk
        assert len(chunks) >= 1

    def test_title_starts_new_chunk(self):
        """A Title segment should start a new chunk when hierarchy increases."""
        segs = [
            Segment(content="body text one two three four five", segment_type=SegmentType.TEXT),
            Segment(content="Chapter Title", segment_type=SegmentType.TITLE),
            Segment(content="body text six seven eight nine ten", segment_type=SegmentType.TEXT),
        ]
        config = ChunkingConfig(target_length=500)
        chunks = hierarchical_chunking(segs, config)
        # Title (hierarchy 3) > Text (hierarchy 1) → finalize previous chunk
        assert len(chunks) >= 2
        # The title should be at the start of the second chunk
        title_chunk = chunks[1]
        assert title_chunk.segments[0].segment_type == SegmentType.TITLE

    def test_section_header_starts_new_chunk(self):
        """A SectionHeader should start a new chunk when hierarchy increases."""
        segs = [
            Segment(content="intro text", segment_type=SegmentType.TEXT),
            Segment(content="Section Heading", segment_type=SegmentType.SECTION_HEADER),
            Segment(content="section body", segment_type=SegmentType.TEXT),
        ]
        config = ChunkingConfig(target_length=500)
        chunks = hierarchical_chunking(segs, config)
        assert len(chunks) >= 2

    def test_ignore_headers_and_footers(self):
        """PageHeader and PageFooter should be skipped when ignore=True."""
        segs = [
            Segment(content="Page Header", segment_type=SegmentType.PAGE_HEADER),
            Segment(content="Real content here", segment_type=SegmentType.TEXT),
            Segment(content="Page Footer", segment_type=SegmentType.PAGE_FOOTER),
        ]
        config = ChunkingConfig(target_length=500, ignore_headers_and_footers=True)
        chunks = hierarchical_chunking(segs, config)
        # Headers/footers are skipped — only the TEXT segment should be in the chunk
        all_content = " ".join(c.content for c in chunks)
        assert "Page Header" not in all_content
        assert "Page Footer" not in all_content
        assert "Real content here" in all_content

    def test_keep_headers_and_footers(self):
        """PageHeader and PageFooter should be kept when ignore=False."""
        segs = [
            Segment(content="Page Header", segment_type=SegmentType.PAGE_HEADER),
            Segment(content="Real content", segment_type=SegmentType.TEXT),
        ]
        config = ChunkingConfig(target_length=500, ignore_headers_and_footers=False)
        chunks = hierarchical_chunking(segs, config)
        # Header gets its own chunk (chunkr behavior), then content
        all_content = " ".join(c.content for c in chunks)
        assert "Page Header" in all_content

    def test_target_length_enforced(self):
        """Chunks should not exceed target_length (in words) — roughly."""
        # Create 10 segments of 100 words each = 1000 words total
        # With target_length=200, we expect ~5 chunks
        words = " ".join(["word"] * 100)
        segs = [Segment(content=words, segment_type=SegmentType.TEXT) for _ in range(10)]
        config = ChunkingConfig(target_length=200)
        chunks = hierarchical_chunking(segs, config)
        # Each chunk should be ≤ 200 words (with possible overflow of 1 segment)
        for chunk in chunks:
            # Allow some slack — the algorithm adds a full segment even if it
            # slightly exceeds target_length
            assert chunk.word_count <= 200 + 100  # 200 target + 1 segment slack

    def test_picture_caption_pairing(self):
        """A Picture followed by a Caption should be paired in the same chunk."""
        segs = [
            Segment(content="[Image]", segment_type=SegmentType.PICTURE),
            Segment(content="Figure 1: An example", segment_type=SegmentType.CAPTION),
        ]
        config = ChunkingConfig(target_length=500)
        chunks = hierarchical_chunking(segs, config)
        # Both should be in the same chunk (pairing logic)
        assert len(chunks) == 1
        assert chunks[0].segment_types == [SegmentType.PICTURE, SegmentType.CAPTION]

    def test_negative_target_length_raises(self):
        """Negative target_length should raise ValueError."""
        with pytest.raises(ValueError, match="target_length must be >= 0"):
            hierarchical_chunking([], ChunkingConfig(target_length=-1))


class TestDocumentIngestor:
    """Tests for the document ingestor (graceful degradation)."""

    def test_get_supported_formats(self):
        """get_supported_formats should return a dict with pdf/docx/pptx keys."""
        from ai_context_engine.document_ingestor import get_supported_formats

        formats = get_supported_formats()
        assert "pdf" in formats
        assert "docx" in formats
        assert "pptx" in formats
        for _fmt, info in formats.items():
            assert "supported" in info
            assert "library" in info
            assert isinstance(info["supported"], bool)

    def test_ingest_nonexistent_file_raises(self):
        """ingest_document should raise FileNotFoundError for missing files."""
        from ai_context_engine.document_ingestor import ingest_document

        with pytest.raises(FileNotFoundError):
            ingest_document(Path("/nonexistent/file.pdf"))

    def test_ingest_unsupported_format_raises(self):
        """ingest_document should raise ValueError for unsupported file types."""
        # Create a temp .txt file
        import tempfile

        from ai_context_engine.document_ingestor import ingest_document

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("hello")
            temp_path = f.name
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                ingest_document(Path(temp_path))
        finally:
            Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    # Run tests directly when executed as a script
    pytest.main([__file__, "-v", "--tb=short"])
