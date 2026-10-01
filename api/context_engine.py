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


@router.post(
    "/retrieve",
    dependencies=[Depends(get_api_key)],
    responses={
        400: {"description": "Bad request"},
        403: {"description": "Forbidden — missing or invalid API key"},
        404: {"description": "No matching context found"},
        422: {"description": "Validation error"},
    },
)
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


@router.post(
    "/impact",
    dependencies=[Depends(get_api_key)],
    responses={
        400: {"description": "Bad request"},
        403: {"description": "Forbidden — missing or invalid API key"},
        404: {"description": "Component not found"},
        422: {"description": "Validation error"},
    },
)
async def analyze_impact(request: SharedImpactAnalysisRequest):
    """
    Perform dependency impact analysis on a component using the Code Property Graph.
    """
    result = handle_impact_analysis(component=request.component, max_depth=request.max_depth)
    status = result.pop("_status", None)
    if status:
        return JSONResponse(status_code=status, content=result)
    return JSONResponse(content=result)


from pydantic import BaseModel, Field


class FabricQueryRequest(BaseModel):
    context_type: str = Field(..., description="Canonical context type e.g. engineering_knowledge, standards, project_state")
    query: str = Field(..., description="Semantic search query or topic identifier")
    limit: int = Field(5, ge=1, le=50, description="Maximum number of evidence items to return")


@router.post(
    "/fabric/query",
    dependencies=[Depends(get_api_key)],
    responses={
        400: {"description": "Missing tenant scope"},
        403: {"description": "Forbidden — missing or invalid API key"},
        422: {"description": "Invalid context type or payload"},
    },
)
async def query_context_fabric(
    request: FabricQueryRequest,
    user: Optional[CurrentUser] = Depends(get_optional_current_user_from_header),
):
    """
    Query multi-tenant ContextFabric with fail-closed provenance verification (R-4).
    """
    from context_fabric.fabric import ContextType
    from context_fabric.providers import build_default_fabric

    tenant_id = user.tenant_id if user and user.tenant_id else None
    if not tenant_id:
        return JSONResponse(
            status_code=400,
            content={"error": "ContextIsolationError: Tenant scope is required for ContextFabric queries (fail-closed)."},
        )

    try:
        ctype = ContextType(request.context_type)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content={"error": f"Invalid context_type '{request.context_type}'. Allowed: {[c.value for c in ContextType]}"},
        )

    fabric = build_default_fabric()
    result = fabric.query(ctype, query=request.query, tenant_id=tenant_id, limit=request.limit)

    return JSONResponse(
        content={
            "context_type": result.context_type.value,
            "available": result.available,
            "reason": result.reason,
            "evidence_count": len(result.evidence),
            "evidence": [
                {
                    "source_type": e.source_type.value,
                    "content_hash": e.content_hash,
                    "tenant_id": e.tenant_id,
                    "key": e.key,
                    "value": e.value,
                    "source_ref": e.source_ref,
                }
                for e in result.evidence
            ],
        }
    )

