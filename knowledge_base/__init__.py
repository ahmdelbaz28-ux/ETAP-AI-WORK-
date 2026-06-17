"""Knowledge Base - ETAP & Zenon Documentation Integration.

Provides document manifests, ingestion scripts, and RAG integration
for the official ETAP and Zenon (COPA-DATA) manuals used as the
PRIMARY authoritative reference for all AI agents.
"""

from knowledge_base.ingest_manuals import (
    ETAPManualIngestor,
    ZenonManualIngestor,
    ingest_all_manuals,
    get_manual_paths,
)

__all__ = [
    "ETAPManualIngestor",
    "ZenonManualIngestor",
    "ingest_all_manuals",
    "get_manual_paths",
]
