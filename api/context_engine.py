"""
FastAPI Router for AI Context Engine (Code RAG).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from api.shared_handlers import SharedContextRetrieveRequest, handle_context_retrieval

router = APIRouter(prefix="/api/v1/context", tags=["Context Engine"])


@router.post("/retrieve", response_class=JSONResponse)
async def retrieve_context(request: SharedContextRetrieveRequest):
    """
    Retrieve and compress matching code snippets for a given query.
    Uses ChromaDB for vector retrieval and Jaccard pruning for compression.
    """
    result = handle_context_retrieval(
        query=request.query,
        top_k=request.top_k,
        max_tokens=request.max_tokens
    )
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return JSONResponse(content=result)
