"""
FastAPI Router for AI Context Engine (Code RAG).
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.dependencies import get_api_key
from api.shared_handlers import (
    SharedContextRetrieveRequest,
    SharedImpactAnalysisRequest,
    handle_context_retrieval,
    handle_impact_analysis,
)

router = APIRouter(prefix="/api/v1/context", tags=["Context Engine"])


@router.post("/retrieve", response_class=JSONResponse, dependencies=[Depends(get_api_key)])
async def retrieve_context(request: SharedContextRetrieveRequest):
    """
    Retrieve and compress matching code snippets for a given query.
    Uses ChromaDB for vector retrieval and Jaccard pruning for compression.
    """
    result = handle_context_retrieval(
        query=request.query, top_k=request.top_k, max_tokens=request.max_tokens,
    )
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return JSONResponse(content=result)


@router.post("/impact", response_class=JSONResponse, dependencies=[Depends(get_api_key)])
async def analyze_impact(request: SharedImpactAnalysisRequest):
    """
    Perform dependency impact analysis on a component using the Code Property Graph.
    """
    result = handle_impact_analysis(component=request.component, max_depth=request.max_depth)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return JSONResponse(content=result)
