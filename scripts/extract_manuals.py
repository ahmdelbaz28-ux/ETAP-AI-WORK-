import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from PyPDF2 import PdfReader


class ManualExtractor:
    """Extracts and processes text from PDF manuals for ETAP and Zenon RAG."""

    def __init__(self, source_dir: str, target_dir: str, name: str):
        """
        Args:
            source_dir: Directory containing PDFs
            target_dir: Directory to save extracted text and chunks
            name: Name of the system (e.g., 'ETAP', 'Zenon')
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.name = name

        self.extracted_dir = self.target_dir / "extracted"
        self.chunks_dir = self.target_dir / "chunks"
        self.index_dir = self.target_dir / "index"

        # Create directories
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.summary = {
            "system_name": name,
            "total_files": 0,
            "successful": 0,
            "failed": 0,
            "total_pages": 0,
            "total_characters": 0,
            "files": []
        }

    def extract_pdf_text(self, pdf_path: Path) -> Tuple[str | None, int]:
        """Extract text using PyPDF2 (fast and memory-efficient)."""
        try:
            reader = PdfReader(pdf_path)
            page_count = len(reader.pages)
            text_parts = []

            # Print extraction progress for large files
            print_interval = max(1, page_count // 5)
            for idx, page in enumerate(reader.pages):
                if idx % print_interval == 0 or idx == page_count - 1:
                    print(f"    Processing page {idx + 1}/{page_count}...")
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            return "\n\n".join(text_parts), page_count
        except Exception as e:
            print(f"  Error extracting {pdf_path.name}: {e}")
            return None, 0

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")
                continue
            if line.isdigit() and len(line) <= 4:
                continue  # Skip page numbers
            cleaned_lines.append(line)

        text = "\n".join(cleaned_lines)
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text.strip()

    def create_chunks(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        if not text:
            return []
        chunks = []
        start = 0
        text_length = len(text)
        while start < text_length:
            end = start + chunk_size
            if end < text_length:
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + chunk_size // 2:
                    end = para_break
                else:
                    sent_break = text.rfind(". ", start, end)
                    if sent_break > start + chunk_size // 2:
                        end = sent_break + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap
        return chunks

    def process_all(self):
        print("=" * 70)
        print(f"Extracting {self.name} Manuals from: {self.source_dir}")
        print("=" * 70)

        if not self.source_dir.exists():
            print(f"Source directory {self.source_dir} does not exist. Skipping.")
            return

        pdf_files = sorted(self.source_dir.glob("*.pdf"))
        self.summary["total_files"] = len(pdf_files)
        print(f"Found {len(pdf_files)} PDF files.")

        for idx, pdf_path in enumerate(pdf_files, 1):
            print(f"\n[{idx}/{len(pdf_files)}] Extracting: {pdf_path.name} ({pdf_path.stat().st_size / 1024 / 1024:.2f} MB)")

            # Extract text
            text, page_count = self.extract_pdf_text(pdf_path)

            if text and len(text) > 100:
                cleaned = self.clean_text(text)

                # Save full text
                txt_filename = f"{pdf_path.stem}.txt"
                with open(self.extracted_dir / txt_filename, "w", encoding="utf-8") as f:
                    f.write(cleaned)

                # Create chunks
                chunks = self.create_chunks(cleaned)

                # Save chunks
                chunks_filename = f"{pdf_path.stem}_chunks.json"
                with open(self.chunks_dir / chunks_filename, "w", encoding="utf-8") as f:
                    json.dump({
                        "source": str(pdf_path),
                        "filename": pdf_path.name,
                        "chunks": chunks,
                        "chunk_count": len(chunks),
                        "metadata": {
                            "pages": page_count,
                            "characters": len(cleaned),
                            "extracted_at": datetime.now().isoformat()
                        }
                    }, f, indent=2, ensure_ascii=False)

                self.summary["successful"] += 1
                self.summary["total_pages"] += page_count
                self.summary["total_characters"] += len(cleaned)
                self.summary["files"].append({
                    "filename": pdf_path.name,
                    "pages": page_count,
                    "chunks": len(chunks),
                    "status": "success"
                })
                print(f"  [OK] Success: {page_count} pages, {len(chunks)} chunks, {len(cleaned)} chars")
            else:
                self.summary["failed"] += 1
                self.summary["files"].append({
                    "filename": pdf_path.name,
                    "status": "failed",
                    "error": "Failed to extract text or content too short"
                })
                print("  [FAIL] Failed: No text extracted")

        # Save summary
        with open(self.target_dir / "extraction_summary.json", "w", encoding="utf-8") as f:
            json.dump(self.summary, f, indent=2, ensure_ascii=False)

        # Create master index
        self.create_master_index()

    def create_master_index(self):
        print(f"Building master index for {self.name}...")
        master_index = {
            "created_at": datetime.now().isoformat(),
            "total_documents": 0,
            "total_chunks": 0,
            "total_characters": 0,
            "documents": []
        }

        chunk_files = list(self.chunks_dir.glob("*_chunks.json"))
        for chunk_file in chunk_files:
            with open(chunk_file, encoding="utf-8") as f:
                data = json.load(f)
                master_index["documents"].append({
                    "filename": data["filename"],
                    "source": data["source"],
                    "chunk_count": data["chunk_count"],
                    "pages": data["metadata"]["pages"],
                    "characters": data["metadata"]["characters"],
                    "chunks": data["chunks"]
                })
                master_index["total_documents"] += 1
                master_index["total_chunks"] += data["chunk_count"]
                master_index["total_characters"] += data["metadata"]["characters"]

        with open(self.index_dir / "master_index.json", "w", encoding="utf-8") as f:
            json.dump(master_index, f, indent=2, ensure_ascii=False)
        print(f"  [OK] Master index saved. Total documents: {master_index['total_documents']}, Total chunks: {master_index['total_chunks']}")

def main():
    # ETAP Manuals
    etap_extractor = ManualExtractor(
        source_dir=r"C:\Users\Repair SC\Desktop\New folder\etap",
        target_dir="etap_user_guide",
        name="ETAP"
    )
    etap_extractor.process_all()

    # Zenon Manuals
    zenon_extractor = ManualExtractor(
        source_dir=r"C:\Users\Repair SC\Desktop\New folder\zenon",
        target_dir="zenon_user_guide",
        name="Zenon"
    )
    zenon_extractor.process_all()

if __name__ == "__main__":
    main()
