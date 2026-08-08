---
name: rag-blueprint
description: NVIDIA RAG Blueprint specification for enterprise multimodal Retrieval-Augmented Generation (RAG), combining dense vector retrieval, sparse BM25 keyword search, NeMo Reranker, document parsing, and NeMo Guardrails.
---

# NVIDIA RAG Blueprint Skill

Use this skill when designing, building, or querying enterprise Retrieval-Augmented Generation (RAG) pipelines for complex technical documentation, electrical engineering standards (IEEE/IEC), SCADA user manuals, and CAD/BIM metadata.

## Core Blueprint Architecture

```
[User Query / Agent Request]
            │
            ▼
┌─────────────────────────┐
│ Hybrid Retriever Engine │
│ ├── Dense Vector Embeds │
│ └── Sparse BM25 Search  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Semantic Reranker     │
│   (NeMo / Cross-Enc)    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Context Pruning Budget  │
│  (Token Budget Guard)   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Zero-Hallucination Guard│
│  (NeMo Guardrails API)  │
└───────────┬─────────────┘
```

## Workflow Pipeline Steps

1. **Multimodal Document & Code Ingestion**
   - Parse PDF manuals, DXF/DWG electrical diagrams, Revit JSON, and Python engineering modules.
   - Apply AST / Tree-Sitter structural chunking to preserve code block definitions.
   - Maintain metadata tags: `standard_ref`, `voltage_class`, `equipment_type`, `filepath`.

2. **Hybrid Dense + Sparse Retrieval**
   - Perform vector cosine similarity search on high-dimensional embeddings.
   - Combine with lexical BM25 token matching for exact technical keyword matches (e.g. `IEC 60909`, `Zenon SCADA`, `IEEE 1584`).
   - Merge candidate scores using Reciprocal Rank Fusion (RRF).

3. **Semantic Reranking**
   - Pass top candidates (e.g. Top 20) through a Cross-Encoder / NeMo Reranker model.
   - Filter out low-relevance candidates prior to context window construction.

4. **Token Budget & Context Compression**
   - Estimate token consumption (4 chars/token heuristic or model tokenizer).
   - Crop or prune lower-ranked chunks to strictly fit within the target context budget (e.g. 2000-4000 tokens).

5. **Safety Guardrails & Compliance**
   - Verify retrieved facts against authoritative source documentation.
   - Return explicit "Not documented in reference manuals" if no candidate meets confidence threshold.
   - Prevent hallucination of critical engineering parameters (e.g., short-circuit trip thresholds).

## Integration Guidelines for AhmedETAP Agents

- Agents (Load Flow Agent, Short Circuit Agent, SCADA Agent) query `RAGBlueprintAdapter` before executing computational runs.
- Fallback Graceful Degradation: If remote GPU endpoints or NeMo NIM services are un-reachable, automatically degrade to local ChromaDB + Jaccard lexical ranking (`ai_context_engine/retriever.py`).
