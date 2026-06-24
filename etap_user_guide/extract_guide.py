"""
ETAP User Guide PDF Text Extractor
===================================
Extracts text content from ETAP User Guide PDFs for RAG integration.

This module:
1. Extracts text from all PDF files
2. Processes and cleans the text
3. Creates searchable text chunks
4. Builds a knowledge base for the RAG engine
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# PDF processing libraries
try:
    import PyPDF2  # noqa: F401
    from PyPDF2 import PdfReader

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("Warning: PyPDF2 not installed. Install with: pip install PyPDF2")

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("Warning: pdfplumber not installed. Install with: pip install pdfplumber")


class ETAPGuideExtractor:
    """Extracts and processes text from ETAP User Guide PDFs."""

    def __init__(self, guide_path: str, output_path: str):
        """
        Initialize the extractor.

        Args:
            guide_path: Path to the ETAP guide PDFs
            output_path: Path to save extracted text
        """
        self.guide_path = Path(guide_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Ensure output subdirectories exist
        (self.output_path / "extracted").mkdir(exist_ok=True)
        (self.output_path / "chunks").mkdir(exist_ok=True)
        (self.output_path / "index").mkdir(exist_ok=True)

        self.extraction_results = {
            "total_files": 0,
            "successful": 0,
            "failed": 0,
            "total_pages": 0,
            "total_characters": 0,
            "files": [],
        }

    def extract_text_from_pdf(self, pdf_path: Path) -> Tuple[Optional[str], int]:
        """
        Extract text from a single PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (extracted_text, page_count)
        """
        if not PDF_AVAILABLE:
            return None, 0

        try:
            text_parts = []

            # Try pdfplumber first (better for complex layouts)
            if PDFPLUMBER_AVAILABLE:
                with pdfplumber.open(pdf_path) as pdf:
                    page_count = len(pdf.pages)
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)

                    full_text = "\n\n".join(text_parts)
                    return full_text, page_count

            # Fallback to PyPDF2
            with open(pdf_path, "rb") as file:
                reader = PdfReader(file)
                page_count = len(reader.pages)

                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                full_text = "\n\n".join(text_parts)
                return full_text, page_count

        except Exception as e:
            print(f"Error extracting {pdf_path.name}: {str(e)}")
            return None, 0

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            # Strip whitespace
            line = line.strip()

            # Skip empty lines (but keep paragraph breaks)
            if not line:
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
                continue

            # Remove page numbers (common patterns)
            if line.isdigit() and len(line) <= 4:
                continue

            # Remove headers/footers (common patterns)
            if "ETAP" in line and len(line) < 50:
                continue

            cleaned_lines.append(line)

        # Join and normalize whitespace
        text = "\n".join(cleaned_lines)

        # Remove multiple blank lines
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text.strip()

    def create_text_chunks(
        self, text: str, chunk_size: int = 1000, overlap: int = 100
    ) -> List[str]:
        """
        Split text into overlapping chunks for RAG.

        Args:
            text: Full text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        if not text:
            return []

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + chunk_size

            # Try to break at sentence or paragraph boundary
            if end < text_length:
                # Look for paragraph break
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + chunk_size // 2:
                    end = para_break
                else:
                    # Look for sentence break
                    sent_break = text.rfind(". ", start, end)
                    if sent_break > start + chunk_size // 2:
                        end = sent_break + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move to next chunk with overlap
            start = end - overlap

        return chunks

    def extract_all_pdfs(self) -> Dict:
        """
        Extract text from all PDF files in the guide directory.

        Returns:
            Dictionary with extraction results
        """
        print("=" * 70)
        print("ETAP User Guide - PDF Text Extraction")
        print("=" * 70)
        print()

        # Find all PDF files
        pdf_files = list(self.guide_path.rglob("*.pdf"))
        self.extraction_results["total_files"] = len(pdf_files)

        print(f"Found {len(pdf_files)} PDF files")
        print()

        for idx, pdf_path in enumerate(pdf_files, 1):
            print(f"[{idx}/{len(pdf_files)}] Processing: {pdf_path.name}")

            # Extract text
            text, page_count = self.extract_text_from_pdf(pdf_path)

            if text and len(text) > 100:
                # Clean text
                cleaned_text = self.clean_text(text)

                # Save extracted text
                output_file = self.output_path / "extracted" / f"{pdf_path.stem}.txt"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(cleaned_text)

                # Create chunks
                chunks = self.create_text_chunks(cleaned_text)

                # Save chunks
                chunk_file = self.output_path / "chunks" / f"{pdf_path.stem}_chunks.json"
                with open(chunk_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "source": str(pdf_path),
                            "filename": pdf_path.name,
                            "chunks": chunks,
                            "chunk_count": len(chunks),
                            "metadata": {
                                "pages": page_count,
                                "characters": len(cleaned_text),
                                "extracted_at": datetime.now().isoformat(),
                            },
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

                # Update results
                self.extraction_results["successful"] += 1
                self.extraction_results["total_pages"] += page_count
                self.extraction_results["total_characters"] += len(cleaned_text)

                self.extraction_results["files"].append(
                    {
                        "filename": pdf_path.name,
                        "pages": page_count,
                        "characters": len(cleaned_text),
                        "chunks": len(chunks),
                        "status": "success",
                    }
                )

                print(
                    f"  ✓ Extracted {page_count} pages, {len(cleaned_text)} chars, {len(chunks)} chunks"
                )
            else:
                self.extraction_results["failed"] += 1
                self.extraction_results["files"].append(
                    {
                        "filename": pdf_path.name,
                        "status": "failed",
                        "error": "No text extracted or too short",
                    }
                )
                print("  ✗ Failed to extract meaningful text")

        # Save extraction summary
        summary_file = self.output_path / "extraction_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(self.extraction_results, f, indent=2, ensure_ascii=False)

        print()
        print("=" * 70)
        print("Extraction Complete!")
        print("=" * 70)
        print(f"Total files: {self.extraction_results['total_files']}")
        print(f"Successful: {self.extraction_results['successful']}")
        print(f"Failed: {self.extraction_results['failed']}")
        print(f"Total pages: {self.extraction_results['total_pages']}")
        print(f"Total characters: {self.extraction_results['total_characters']:,}")
        print()

        return self.extraction_results

    def create_master_index(self) -> Dict:
        """
        Create a master index of all extracted content.

        Returns:
            Master index dictionary
        """
        print("Creating master index...")

        master_index = {
            "created_at": datetime.now().isoformat(),
            "total_documents": 0,
            "total_chunks": 0,
            "total_characters": 0,
            "documents": [],
        }

        # Load all chunk files
        chunk_files = list((self.output_path / "chunks").glob("*_chunks.json"))

        for chunk_file in chunk_files:
            with open(chunk_file, encoding="utf-8") as f:
                data = json.load(f)

                doc_entry = {
                    "filename": data["filename"],
                    "source": data["source"],
                    "chunk_count": data["chunk_count"],
                    "pages": data["metadata"]["pages"],
                    "characters": data["metadata"]["characters"],
                    "chunks": data["chunks"],
                }

                master_index["documents"].append(doc_entry)
                master_index["total_documents"] += 1
                master_index["total_chunks"] += data["chunk_count"]
                master_index["total_characters"] += data["metadata"]["characters"]

        # Save master index
        index_file = self.output_path / "index" / "master_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(master_index, f, indent=2, ensure_ascii=False)

        print(
            f"Master index created: {master_index['total_documents']} documents, {master_index['total_chunks']} chunks"
        )

        return master_index


def main():
    """Main execution function."""
    # Configuration
    GUIDE_PATH = Path("etap_user_guide/pdfs")
    OUTPUT_PATH = Path("etap_user_guide")

    # Check if guide exists
    if not GUIDE_PATH.exists():
        print(f"Error: Guide path not found: {GUIDE_PATH}")
        print("Please ensure the ETAP guide PDFs are in the correct location.")
        sys.exit(1)

    # Create extractor
    extractor = ETAPGuideExtractor(GUIDE_PATH, OUTPUT_PATH)

    # Extract all PDFs
    extractor.extract_all_pdfs()

    # Create master index
    extractor.create_master_index()

    print()
    print("=" * 70)
    print("ETAP User Guide Integration Complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. The extracted text is available in: etap_user_guide/extracted/")
    print("2. Text chunks are in: etap_user_guide/chunks/")
    print("3. Master index is in: etap_user_guide/index/master_index.json")
    print()
    print("The RAG engine can now use this knowledge base for:")
    print("- Answering ETAP-related questions")
    print("- Providing step-by-step instructions")
    print("- Validating ETAP operations")
    print("- Troubleshooting ETAP issues")
    print()


if __name__ == "__main__":
    main()
