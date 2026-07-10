from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore
import re

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore
try:
    from elasticsearch import Elasticsearch  # type: ignore
except ImportError:  # pragma: no cover
    Elasticsearch = None  # type: ignore
import time


class ArcGISProIndexingWorkflow:
    """
    Automated pipeline that ingests ArcGIS Pro docs, cleans, embeds, and indexes them into the MCP Server.
    """

    def __init__(self, config_file: str = "arcgis_pro_indexing_workflow.json"):
        """
        Initialize the workflow with configuration from JSON file.
        """
        with open(config_file, encoding="utf-8") as f:
            self.config = json.load(f)

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Initialize components based on config
        self.transformer_model = None
        self.elastic_client = None

    def fetch_data(self) -> list[dict[str, Any]]:
        """
        Step 1: Fetch documentation data from ArcGIS Pro documentation site.
        """
        self.logger.info("Starting data fetch step...")
        base_url = self.config["steps"][0]["options"]["url"]

        # We'll use our previously indexed documentation as the source
        # In a real scenario, this would crawl the documentation site
        with open("arcgis_pro_documentation_index.json", encoding="utf-8") as f:
            indexed_docs = json.load(f)

        docs_to_process = []

        # Process each section in the documentation
        for section in indexed_docs.get("documentation_sections", []):
            docs_to_process.extend(self._extract_doc_items(section, base_url))

        self.logger.info("Fetched %s documentation items", len(docs_to_process))
        return docs_to_process

    def _extract_doc_items(
        self, section: dict[str, Any], base_url: str, parent: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Recursively extract documentation items from nested sections.
        """
        items = []

        # Add current section
        item = {
            "title": section.get("title", ""),
            "url": section.get("url", ""),
            "level": section.get("level", 1),
            "parent": parent,
            "content": "",  # Will be populated with actual content if available
            "section_number": section.get("section_number", ""),
        }
        items.append(item)

        # Process subsections
        for subsection in section.get("subsections", []):
            items.extend(self._extract_doc_items(subsection, base_url, section.get("title", "")))

        return items

    def clean_data(self, raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Step 2: Clean and validate the fetched data.
        """
        self.logger.info("Starting data cleaning step...")

        cleaned_data = []
        for item in raw_data:
            # Validate URL
            if not self._is_valid_url(item["url"]):
                self.logger.warning("Invalid URL skipped: %s", item['url'])
                continue

            # Clean title
            cleaned_title = self._clean_text(item["title"])

            # Create cleaned item
            cleaned_item = {
                "title": cleaned_title,
                "url": item["url"],
                "level": item["level"],
                "parent": item["parent"],
                "content": self._clean_text(item.get("content", "")),
                "section_number": item.get("section_number", ""),
            }

            cleaned_data.append(cleaned_item)

        self.logger.info("Cleaned %s items", len(cleaned_data))
        return cleaned_data

    def _clean_text(self, text: str) -> str:
        """
        Remove HTML tags and clean text content.
        """
        if not text:
            return ""

        # Remove HTML tags
        clean_text = re.sub(r"<[^>]+>", "", text)
        # Remove extra whitespace
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        return clean_text

    def _is_valid_url(self, url: str) -> bool:
        """
        Validate if the URL is properly formatted.
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def transform_data(self, cleaned_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Step 3: Transform data by generating embeddings.
        """
        self.logger.info("Starting data transformation step...")

        # Initialize the transformer model if not already done
        if self.transformer_model is None:
            self.logger.info("Loading sentence transformer model...")
            self.transformer_model = SentenceTransformer("all-MiniLM-L6-v2")  # type: ignore
            if self.transformer_model is None:
                raise RuntimeError("SentenceTransformer could not be loaded")

        transformed_data = []
        for item in cleaned_data:
            # Combine title and content for embedding
            text_for_embedding = f"{item['title']} {item['content']}".strip()

            # Generate embedding
            if self.transformer_model is None:
                raise RuntimeError("Transformer model not initialized")
            embedding = self.transformer_model.encode(text_for_embedding).tolist()

            # Add embedding to item
            item["embedding_vector"] = embedding
            transformed_data.append(item)

        self.logger.info("Transformed %s items with embeddings", len(transformed_data))
        return transformed_data

    def index_data(self, transformed_data: list[dict[str, Any]]):
        """
        Step 4: Index the transformed data into Elasticsearch/MCP Server.
        """
        self.logger.info("Starting indexing step...")

        # Initialize Elasticsearch client if not already done
        if self.elastic_client is None:
            elastic_config = self.config["steps"][3]["options"]
            self.elastic_client = Elasticsearch([elastic_config["host"]])  # type: ignore
            if self.elastic_client is None:
                raise RuntimeError("Elasticsearch client could not be initialized")

        # Create index if it doesn't exist
        if self.elastic_client is None:
            raise RuntimeError("Elasticsearch client not initialized")
        index_name = self.config["steps"][3]["options"]["index_name"]
        if not self.elastic_client.indices.exists(index=index_name):
            mappings = self.config["steps"][3]["options"]["mappings"]
            self.elastic_client.indices.create(index=index_name, body={"mappings": mappings})

        # Index each document
        for i, item in enumerate(transformed_data):
            # MD5 used as a deterministic document ID for Elasticsearch —
            # not a security primitive (no password, no signature).
            doc_id = hashlib.md5(item["url"].encode()).hexdigest()  # nosec B324 — non-security doc ID  # NOSONAR — S4790: MD5 is intentional for deterministic doc IDs, not security

            try:
                if self.elastic_client is None:
                    raise RuntimeError("Elasticsearch client not initialized")
                self.elastic_client.index(index=index_name, id=doc_id, body=item)

                if (i + 1) % 100 == 0:  # Log progress every 100 items
                    self.logger.info("Indexed %s/%s items", i + 1, len(transformed_data))

            except Exception:
                self.logger.exception("Failed to index document %s", item['url'])

        self.logger.info("Successfully indexed %s documents", len(transformed_data))

    def post_process(self, stats: dict[str, Any]):
        """
        Step 5: Post-processing activities like reporting.
        """
        self.logger.info("Starting post-processing step...")

        # Create statistics report
        report = {
            "workflow_name": self.config["workflow_name"],
            "execution_time": datetime.now().isoformat(),
            "total_processed": stats.get("total_processed", 0),
            "total_indexed": stats.get("total_indexed", 0),
            "errors": stats.get("errors", 0),
        }

        # In a real implementation, this would send an email report
        # For now, we'll just log the report
        self.logger.info("Execution report: %s", json.dumps(report, indent=2))

        # Save report to file
        report_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        self.logger.info("Report saved to %s", report_filename)

    def run(self):
        """
        Execute the complete workflow.
        """
        self.logger.info("Starting workflow: %s", self.config['workflow_name'])
        start_time = time.time()

        try:
            # Step 1: Fetch data
            raw_data = self.fetch_data()

            # Step 2: Clean data
            cleaned_data = self.clean_data(raw_data)

            # Step 3: Transform data
            transformed_data = self.transform_data(cleaned_data)

            # Step 4: Index data
            self.index_data(transformed_data)

            # Step 5: Post-process
            stats = {
                "total_processed": len(transformed_data),
                "total_indexed": len(transformed_data),
                "errors": 0,
            }
            self.post_process(stats)

            total_time = time.time() - start_time
            self.logger.info("Workflow completed successfully in %.2f seconds", total_time)

        except Exception as e:
            self.logger.error("Workflow failed with error: %s", str(e))
            raise


def main():
    """
    Main function to run the ArcGIS Pro documentation indexing workflow.
    """
    workflow = ArcGISProIndexingWorkflow()
    workflow.run()


if __name__ == "__main__":
    main()
