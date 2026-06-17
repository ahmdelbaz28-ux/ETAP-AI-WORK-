"""
ETAP & Zenon Manual Ingestion Engine
======================================
Extracts text from official ETAP and Zenon (COPA-DATA) PDF manuals,
creates searchable text chunks, and builds a master index for the
RAG knowledge base.

These manuals are the PRIMARY AUTHORITATIVE REFERENCE for all AI agents.

Usage::

    # Ingest all manuals
    python -m knowledge_base.ingest_manuals

    # Or programmatically
    from knowledge_base.ingest_manuals import ingest_all_manuals
    ingest_all_manuals()
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default paths — overridden by environment variables
_DEFAULT_ETAP_PATH = r"C:\Users\Repair SC\Desktop\New folder\etap"
_DEFAULT_ZENON_PATH = r"C:\Users\Repair SC\Desktop\New folder\zenon"

# Output directories
_OUTPUT_BASE = _PROJECT_ROOT / "knowledge_base" / "extracted"
_ETAP_OUTPUT = _OUTPUT_BASE / "etap"
_ZENON_OUTPUT = _OUTPUT_BASE / "zenon"
_INDEX_OUTPUT = _OUTPUT_BASE / "index"

# Chunking parameters
_CHUNK_SIZE = 1500       # characters per chunk
_CHUNK_OVERLAP = 200     # overlap between chunks


# ---------------------------------------------------------------------------
# PDF Text Extraction
# ---------------------------------------------------------------------------

def _extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file using available libraries.

    Tries pdfplumber first (best quality), then PyPDF2, then returns empty.
    """
    # Try pdfplumber (best quality extraction)
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("pdfplumber failed for %s: %s", pdf_path.name, exc)

    # Try PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("PyPDF2 failed for %s: %s", pdf_path.name, exc)

    # Try pypdf (newer fork)
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("pypdf failed for %s: %s", pdf_path.name, exc)

    logger.error("No PDF library available to extract: %s", pdf_path.name)
    return ""


def _extract_text_from_html(html_path: Path) -> str:
    """Extract text from an HTML file."""
    try:
        content = html_path.read_text(encoding="utf-8", errors="replace")
        # If it's just a URL link, return the URL
        content_stripped = content.strip()
        if content_stripped.startswith("http"):
            return f"Reference URL: {content_stripped}"
        # Basic HTML tag stripping
        import re
        text = re.sub(r'<[^>]+>', ' ', content)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as exc:
        logger.warning("HTML extraction failed for %s: %s", html_path.name, exc)
        return ""


# ---------------------------------------------------------------------------
# Text Chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE,
                overlap: int = _CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks for RAG ingestion."""
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# Ingestor Classes
# ---------------------------------------------------------------------------

class ETAPManualIngestor:
    """Ingests official ETAP manuals into the knowledge base."""

    def __init__(self, manuals_path: Optional[str] = None):
        self.manuals_path = Path(
            manuals_path or os.environ.get("ETAP_MANUALS_PATH", _DEFAULT_ETAP_PATH)
        )
        self.output_dir = _ETAP_OUTPUT
        self.documents: List[Dict] = []

    def ingest(self) -> List[Dict]:
        """Extract text from all ETAP PDFs and save as chunks."""
        if not self.manuals_path.exists():
            logger.error("ETAP manuals path not found: %s", self.manuals_path)
            return []

        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = Path(__file__).resolve().parent / "manifest.json"

        # Load manifest
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        etap_docs = manifest["sources"]["etap"]["documents"]
        print(f"\n{'='*70}")
        print(f"  Ingesting ETAP Manuals from: {self.manuals_path}")
        print(f"  Documents to process: {len(etap_docs)}")
        print(f"{'='*70}\n")

        for doc_info in etap_docs:
            doc_id = doc_info["id"]
            filename = doc_info["filename"]
            pdf_path = self.manuals_path / filename

            if not pdf_path.exists():
                print(f"  [SKIP] {filename} - file not found")
                continue

            print(f"  [OK] Processing: {filename}...")

            # Extract text
            if filename.lower().endswith('.pdf'):
                text = _extract_text_from_pdf(pdf_path)
            elif filename.lower().endswith(('.htm', '.html')):
                text = _extract_text_from_html(pdf_path)
            else:
                text = pdf_path.read_text(encoding='utf-8', errors='replace')

            if not text:
                print(f"         No text extracted from {filename}")
                continue

            # Save extracted
            txt_file = self.output_dir / f"{doc_id}.txt"
            txt_file.write_text(text, encoding='utf-8')

            # Create chunks
            chunks = _chunk_text(text)
            chunks_file = self.output_dir / f"{doc_id}_chunks.json"
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "doc_id": doc_id,
                    "title": doc_info["title"],
                    "category": doc_info["category"],
                    "priority": doc_info["priority"],
                    "source_file": filename,
                    "chunks": chunks
                }, f, ensure_ascii=False, indent=2)

            self.documents.append({
                "doc_id": doc_id,
                "filename": filename,
                "title": doc_info["title"],
                "category": doc_info["category"],
                "priority": doc_info["priority"],
                "characters": len(text),
                "chunks": len(chunks),
                "source": "ETAP"
            })

            print(f"         {len(text):,} chars, {len(chunks)} chunks")

        print(f"\n  ETAP ingestion complete: {len(self.documents)} documents\n")
        return self.documents


class ZenonManualIngestor:
    """Ingests official Zenon (COPA-DATA) SCADA manuals into the knowledge base."""

    def __init__(self, manuals_path: Optional[str] = None):
        self.manuals_path = Path(
            manuals_path or os.environ.get("ZENON_MANUALS_PATH", _DEFAULT_ZENON_PATH)
        )
        self.output_dir = _ZENON_OUTPUT
        self.documents: List[Dict] = []

    def ingest(self) -> List[Dict]:
        """Extract text from all Zenon PDFs and save as chunks."""
        if not self.manuals_path.exists():
            logger.error("Zenon manuals path not found: %s", self.manuals_path)
            return []

        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = Path(__file__).resolve().parent / "manifest.json"

        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        zenon_docs = manifest["sources"]["zenon"]["documents"]
        print(f"\n{'='*70}")
        print(f"  Ingesting Zenon (COPA-DATA) Manuals from: {self.manuals_path}")
        print(f"  Documents to process: {len(zenon_docs)}")
        print(f"{'='*70}\n")

        for doc_info in zenon_docs:
            doc_id = doc_info["id"]
            filename = doc_info["filename"]
            file_path = self.manuals_path / filename

            if not file_path.exists():
                print(f"  [SKIP] {filename} - file not found")
                continue

            print(f"  [OK] Processing: {filename}...")

            # Extract text
            if filename.lower().endswith('.pdf'):
                text = _extract_text_from_pdf(file_path)
            elif filename.lower().endswith(('.htm', '.html')):
                text = _extract_text_from_html(file_path)
            else:
                text = file_path.read_text(encoding='utf-8', errors='replace')

            if not text:
                print(f"         No text extracted from {filename}")
                continue

            # Save extracts
            txt_file = self.output_dir / f"{doc_id}.txt"
            txt_file.write_text(text, encoding='utf-8')

            chunks = _chunk_text(text)
            chunks_file = self.output_dir / f"{doc_id}_chunks.json"
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "doc_id": doc_id,
                    "title": doc_info["title"],
                    "category": doc_info["category"],
                    "priority": doc_info["priority"],
                    "source_file": filename,
                    "chunks": chunks
                }, f, ensure_ascii=False, indent=2)

            self.documents.append({
                "doc_id": doc_id,
                "filename": filename,
                "title": doc_info["title"],
                "category": doc_info["category"],
                "priority": doc_info["priority"],
                "characters": len(text),
                "chunks": len(chunks),
                "source": "Zenon (COPA-DATA)"
            })

            print(f"         {len(text):,} chars, {len(chunks)} chunks")

        print(f"\n  Zenon ingestion complete: {len(self.documents)} documents\n")
        return self.documents


# ---------------------------------------------------------------------------
# Master Index Builder
# ---------------------------------------------------------------------------

def _build_master_index(etap_docs: List[Dict], zenon_docs: List[Dict]):
    """Build master index JSON for the RAG engine."""
    _INDEX_OUTPUT.mkdir(parents=True, exist_ok=True)

    total_chars = sum(d["characters"] for d in etap_docs + zenon_docs)
    total_chunks = sum(d["chunks"] for d in etap_docs + zenon_docs)

    master_index = {
        "version": "1.0",
        "description": "Master index of ETAP & Zenon documentation for RAG",
        "total_documents": len(etap_docs) + len(zenon_docs),
        "total_characters": total_chars,
        "total_chunks": total_chunks,
        "documents": etap_docs + zenon_docs,
        "sources": {
            "etap": {
                "count": len(etap_docs),
                "characters": sum(d["characters"] for d in etap_docs),
                "chunks": sum(d["chunks"] for d in etap_docs)
            },
            "zenon": {
                "count": len(zenon_docs),
                "characters": sum(d["characters"] for d in zenon_docs),
                "chunks": sum(d["chunks"] for d in zenon_docs)
            }
        }
    }

    index_file = _INDEX_OUTPUT / "master_index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(master_index, f, ensure_ascii=False, indent=2)

    print(f"\n  Master index saved: {index_file}")
    print(f"  Total: {master_index['total_documents']} docs, "
          f"{total_chars:,} chars, {total_chunks} chunks")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_manual_paths() -> Dict[str, str]:
    """Get configured manual paths from environment or defaults."""
    return {
        "etap": os.environ.get("ETAP_MANUALS_PATH", _DEFAULT_ETAP_PATH),
        "zenon": os.environ.get("ZENON_MANUALS_PATH", _DEFAULT_ZENON_PATH),
    }


def ingest_all_manuals(etap_path: Optional[str] = None,
                       zenon_path: Optional[str] = None) -> Dict:
    """Ingest all ETAP and Zenon manuals into the knowledge base.

    Parameters
    ----------
    etap_path : str, optional
        Path to ETAP manuals directory. Defaults to env var or default path.
    zenon_path : str, optional
        Path to Zenon manuals directory. Defaults to env var or default path.

    Returns
    -------
    dict
        Summary of ingestion results.
    """
    print("\n" + "=" * 70)
    print("  ETAP & Zenon Documentation Ingestion")
    print("  These manuals are the PRIMARY REFERENCE for all AI agents")
    print("=" * 70)

    # Ingest ETAP
    etap_ingestor = ETAPManualIngestor(etap_path)
    etap_docs = etap_ingestor.ingest()

    # Ingest Zenon
    zenon_ingestor = ZenonManualIngestor(zenon_path)
    zenon_docs = zenon_ingestor.ingest()

    # Build master index
    _build_master_index(etap_docs, zenon_docs)

    return {
        "etap_documents": len(etap_docs),
        "zenon_documents": len(zenon_docs),
        "total_documents": len(etap_docs) + len(zenon_docs),
        "status": "completed"
    }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = ingest_all_manuals()
    print(f"\nResult: {json.dumps(result, indent=2)}")
