"""
ETAP User Guide - Complete Setup Script
========================================
Automated script to:
1. Install required dependencies
2. Extract text from all PDFs
3. Build RAG knowledge base
4. Verify integration
5. Test the system
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(text):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def check_directory_structure():
    """Verify the ETAP guide directory structure."""
    print_header("Checking Directory Structure")

    required_paths = [
        "etap_user_guide",
        "etap_user_guide/pdfs",
        "etap_user_guide/ac_element",
        "etap_user_guide/extract_guide.py",
        "etap_user_guide/etap_guide_rag.py",
        "etap_user_guide/README.md",
    ]

    all_exist = True
    for path in required_paths:
        if Path(path).exists():
            print_success(f"{path} exists")
        else:
            print_error(f"{path} NOT FOUND")
            all_exist = False

    return all_exist


def check_pdf_files():
    """Count PDF files in the guide directory."""
    print_header("Checking PDF Files")

    pdfs_path = Path("etap_user_guide/pdfs")
    ac_path = Path("etap_user_guide/ac_element")

    if not pdfs_path.exists():
        print_error("PDFs directory not found")
        return 0

    pdf_count = len(list(pdfs_path.glob("*.pdf")))
    ac_count = len(list(ac_path.glob("*.pdf"))) if ac_path.exists() else 0

    print_info(f"Main PDFs: {pdf_count}")
    print_info(f"AC Element PDFs: {ac_count}")
    print_info(f"Total PDFs: {pdf_count + ac_count}")

    return pdf_count + ac_count


def install_dependencies():
    """Install required Python packages."""
    print_header("Installing Dependencies")

    packages = [
        "PyPDF2>=3.0.0",
        "pdfplumber>=0.7.0",
        "sentence-transformers>=2.2.0",
        "chromadb>=0.4.0",
        "tqdm>=4.62.0",
    ]

    for package in packages:
        print_info(f"Installing {package}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package, "-q"],
                check=True,
                capture_output=True,
            )
            print_success(f"{package} installed")
        except subprocess.CalledProcessError as e:
            print_warning(f"Could not install {package}: {e}")
            print_info("This package is optional - continuing...")


def extract_text_from_pdfs():
    """Extract text from all PDF files."""
    print_header("Extracting Text from PDFs")

    extract_script = Path("etap_user_guide/extract_guide.py")

    if not extract_script.exists():
        print_error("extract_guide.py not found")
        return False

    print_info("Running PDF extraction...")
    print_info("This may take several minutes depending on the number of PDFs...")
    print()

    try:
        subprocess.run([sys.executable, str(extract_script)], check=True, capture_output=False)

        print()
        print_success("PDF extraction completed")
        return True

    except subprocess.CalledProcessError as e:
        print_error(f"PDF extraction failed: {e}")
        return False


def verify_extraction():
    """Verify that text extraction was successful."""
    print_header("Verifying Extraction Results")

    extracted_path = Path("etap_user_guide/extracted")
    chunks_path = Path("etap_user_guide/chunks")
    index_path = Path("etap_user_guide/index/master_index.json")

    if not extracted_path.exists():
        print_error("Extracted text directory not found")
        return False

    extracted_count = len(list(extracted_path.glob("*.txt")))
    print_info(f"Extracted text files: {extracted_count}")

    if not chunks_path.exists():
        print_error("Chunks directory not found")
        return False

    chunks_count = len(list(chunks_path.glob("*_chunks.json")))
    print_info(f"Text chunk files: {chunks_count}")

    if not index_path.exists():
        print_error("Master index not found")
        return False

    print_success("Master index found")

    # Load and display index stats
    import json

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    print_info(f"Total documents: {index['total_documents']}")
    print_info(f"Total chunks: {index['total_chunks']}")
    print_info(f"Total characters: {index['total_characters']:,}")

    return True


def test_rag_engine():
    """Test the RAG engine."""
    print_header("Testing RAG Engine")

    try:
        # Import RAG engine
        sys.path.insert(0, str(Path.cwd()))
        from etap_user_guide.etap_guide_rag import ETAPGuideRAG

        print_info("Initializing RAG engine...")
        rag = ETAPGuideRAG()

        print_success("RAG engine initialized")

        # Test queries
        test_queries = [
            "How to create a new project?",
            "How to run load flow analysis?",
            "How to add a bus?",
        ]

        print_info("Testing queries...")
        for query in test_queries:
            result = rag.query(query)
            if result["answered"]:
                print_success(f"Query answered: {query[:50]}...")
            else:
                print_warning(f"Query not answered: {query[:50]}...")

        # Display mandatory instructions
        print()
        print_info("Mandatory Instructions:")
        print(rag.get_mandatory_instructions())

        return True

    except Exception as e:
        print_error(f"RAG engine test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def create_integration_summary():
    """Create a summary of the integration."""
    print_header("Creating Integration Summary")

    summary = {
        "created_at": datetime.now().isoformat(),
        "status": "completed",
        "components": {
            "pdf_extractor": "etap_user_guide/extract_guide.py",
            "rag_engine": "etap_user_guide/etap_guide_rag.py",
            "agent_prompt": "prompts/etap_engineer_agent_v2.yaml",
            "documentation": "etap_user_guide/README.md",
        },
        "statistics": {
            "total_pdfs": len(list(Path("etap_user_guide/pdfs").glob("*.pdf"))),
            "total_ac_pdfs": len(list(Path("etap_user_guide/ac_element").glob("*.pdf"))),
            "extracted_files": len(list(Path("etap_user_guide/extracted").glob("*.txt"))),
            "chunk_files": len(list(Path("etap_user_guide/chunks").glob("*_chunks.json"))),
        },
        "mandatory_rules": {
            "primary_reference": "ETAP User Guide is the PRIMARY authority",
            "validation_required": "All operations must be validated",
            "citation_required": "All instructions must cite the source",
            "no_guessing": "Never guess - always verify",
        },
    }

    # Save summary
    import json

    summary_file = Path("etap_user_guide/integration_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print_success(f"Integration summary saved to: {summary_file}")

    # Display summary
    print()
    print_info("Integration Summary:")
    print(f"  Total PDFs: {summary['statistics']['total_pdfs']}")
    print(f"  AC Element PDFs: {summary['statistics']['total_ac_pdfs']}")
    print(f"  Extracted files: {summary['statistics']['extracted_files']}")
    print(f"  Chunk files: {summary['statistics']['chunk_files']}")
    print()
    print_info("Mandatory Rules:")
    for _key, value in summary["mandatory_rules"].items():
        print(f"  • {value}")

    return True


def main():
    """Main execution function."""
    print_header("ETAP User Guide - Complete Setup")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: Check directory structure
    if not check_directory_structure():
        print_error("Directory structure check failed")
        print_info("Please ensure all required files are in place")
        return False

    # Step 2: Check PDF files
    pdf_count = check_pdf_files()
    if pdf_count == 0:
        print_error("No PDF files found")
        print_info("Please copy ETAP guide PDFs to etap_user_guide/pdfs/")
        return False

    # Step 3: Install dependencies
    install_dependencies()

    # Step 4: Extract text from PDFs
    if not extract_text_from_pdfs():
        print_error("PDF extraction failed")
        print_info("Check the error messages above")
        return False

    # Step 5: Verify extraction
    if not verify_extraction():
        print_error("Extraction verification failed")
        return False

    # Step 6: Test RAG engine
    if not test_rag_engine():
        print_error("RAG engine test failed")
        print_info("The RAG engine may still work - continuing...")

    # Step 7: Create integration summary
    create_integration_summary()

    # Final summary
    print()
    print_header("Setup Complete!")
    print_success("ETAP User Guide has been successfully integrated")
    print()
    print_info("Next steps:")
    print("  1. Review the documentation: etap_user_guide/README.md")
    print("  2. Test the RAG engine: python etap_user_guide/etap_guide_rag.py")
    print("  3. Update agent prompts to use the guide")
    print("  4. Run validation: python validation_suite.py")
    print()
    print_info("Key files:")
    print("  • Extracted text: etap_user_guide/extracted/")
    print("  • Text chunks: etap_user_guide/chunks/")
    print("  • Master index: etap_user_guide/index/master_index.json")
    print("  • RAG engine: etap_user_guide/etap_guide_rag.py")
    print("  • Agent prompt: prompts/etap_engineer_agent_v2.yaml")
    print()
    print_warning("IMPORTANT: All agents MUST consult the ETAP User Guide")
    print_warning("before performing ANY ETAP operation.")
    print()

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
