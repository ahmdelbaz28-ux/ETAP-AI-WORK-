from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_optional_current_user_from_header,
)
from api.shared_handlers import (
    SharedContextRetrieveRequest,
    SharedImpactAnalysisRequest,
    handle_context_retrieval,
    handle_impact_analysis,
)

router = APIRouter(prefix="/api/v1/context", tags=["Context Engine"])


@router.post("/retrieve", dependencies=[Depends(get_api_key)], responses={
    400: {"description": "Bad request"},
    403: {"description": "Forbidden — missing or invalid API key"},
    404: {"description": "No matching context found"},
    422: {"description": "Validation error"},
})
async def retrieve_context(
    request: SharedContextRetrieveRequest,
    user: Optional[CurrentUser] = Depends(get_optional_current_user_from_header),
):
    """
    Retrieve and compress matching code snippets for a given query with tenant isolation.
    Uses ChromaDB for vector retrieval and Jaccard pruning for compression.
    """
    tenant_id = user.tenant_id if user else None
    result = handle_context_retrieval(
        query=request.query,
        top_k=request.top_k,
        max_tokens=request.max_tokens,
        tenant_id=tenant_id,
    )
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return JSONResponse(content=result)


@router.post("/impact", dependencies=[Depends(get_api_key)], responses={
    400: {"description": "Bad request"},
    403: {"description": "Forbidden — missing or invalid API key"},
    404: {"description": "Component not found"},
    422: {"description": "Validation error"},
})
async def analyze_impact(request: SharedImpactAnalysisRequest):
    """
    Perform dependency impact analysis on a component using the Code Property Graph.
    """
    result = handle_impact_analysis(component=request.component, max_depth=request.max_depth)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return JSONResponse(content=result)
