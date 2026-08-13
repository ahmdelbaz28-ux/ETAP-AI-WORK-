# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
v2.py — API v2 Routers for ETAP-AI-WORK Cloud-Native Endpoints.
============================================================

MISSION TASK 3.1 — API Versioning with /api/v2/ structure
==========================================================

This module exposes the new ETAP capabilities (Generative Design,
BIM Provider abstraction, IFC 4.3 mapping, AR export, Webhooks,
Smoke Simulation state) under a versioned ``/api/v2/`` prefix.

Endpoints
---------
- ``POST /api/v2/generative/design`` — Generate 3 layout variants
- ``GET  /api/v2/bim/providers`` — List registered BIM providers
- ``POST /api/v2/bim/extract-rooms`` — Extract rooms via configured provider
- ``GET  /api/v2/bim/health`` — Health check for BIM provider
- ``POST /api/v2/ifc43/map-detector`` — Map detector to IFC 4.3
- ``POST /api/v2/ifc43/map-project`` — Map entire project to IFC 4.3
- ``POST /api/v2/ar/export`` — Export DigitalTwin to GLB/USDZ
- ``POST /api/v2/webhooks/subscribe`` — Subscribe to webhook events
- ``GET  /api/v2/webhooks/subscriptions`` — List subscriptions
- ``DELETE /api/v2/webhooks/subscriptions/{sub_id}`` — Unsubscribe
- ``POST /api/v2/webhooks/publish`` — Publish an event
- ``POST /api/v2/smoke-simulation/state`` — Create/update smoke state

Deprecation Headers
-------------------
Per HTTP standards (RFC 7234):
- v1 endpoints receive ``Deprecation: true`` header
- v1 endpoints receive ``Sunset: <date>`` header (1 year deprecation window)
- v1 endpoints receive ``Link: </api/v2/...>; rel="successor-version"``
  header pointing to the v2 equivalent

References
----------
- agent.md Rule 6/14: VERIFY BEFORE CHANGING
- RFC 7234: HTTP Caching — Deprecation and Sunset headers

Phase 3 cleanup (BAZSPARK contamination):
  The fireai package was deleted from the codebase. Every v2 endpoint
  that previously lazy-imported from fireai.* now returns HTTP 503 with
  a migration notice. The endpoint signatures are preserved so the
  routes still register and clients see a structured error rather than
  a 404. When the underlying services are migrated to new module paths,
  re-introduce the lazy imports inside each endpoint.

"""

# V141 FIX: Removed __future__ annotations to fix Pydantic forward ref resolution.
# With __future__ annotations, Dict[str, Any] becomes ForwardRef('Dict[str, Any]')
# which Pydantic cannot resolve at runtime for FastAPI model parsing.
# Removing it forces actual type resolution at import time.

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.rbac import Permission

logger = logging.getLogger(__name__)

router = APIRouter()


def _fireai_unavailable_503(missing_module: str) -> HTTPException:
    """
    Build a 503 response describing a fireai dependency that was removed.

    Phase 3 cleanup: the fireai package was deleted (BAZSPARK contamination
    cleanup). All v2 endpoints that depended on fireai.* return this 503
    response until the underlying service is migrated to a new module path.
    """
    return HTTPException(
        status_code=503,
        detail={
            "error": "V2_SERVICE_UNAVAILABLE",
            "detail": (
                f"The v2 endpoint requires {missing_module} which was removed "
                "during the BAZSPARK cleanup and is being migrated to a new "
                "module path."
            ),
            "missing_module": missing_module,
            "action": "Wait for the service migration to complete.",
        },
    )


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class GenerativeDesignRequest(BaseModel):
    """
    Request body for /api/v2/generative/design.

    V138 F-13: Added upper bounds to prevent DoS via huge dimensions.
    """

    room_width: float = Field(..., gt=0, le=1000.0, description="Room width in metres (max 1000m)")
    room_length: float = Field(
        ..., gt=0, le=1000.0, description="Room length in metres (max 1000m)"
    )
    room_height: float = Field(3.0, gt=0, le=30.0, description="Ceiling height in metres (max 30m)")
    room_name: str = Field("API_Room", max_length=200, description="Room identifier")
    occupancy_type: str = Field("office", max_length=100, description="NFPA 101 occupancy")
    detector_type: str = Field("smoke", max_length=50, description="Detector type")
    use_multiprocessing: bool = Field(True, description="Use parallel variant generation")


class BIMExtractRoomsRequest(BaseModel):
    """Request body for /api/v2/bim/extract-rooms."""

    source: str | None = Field(None, description="File path or URL")
    provider: str | None = Field(None, description="Provider name (default: env var)")


class IFC43MapDetectorRequest(BaseModel):
    """Request body for /api/v2/ifc43/map-detector."""

    device_id: str
    type: str = "smoke"
    x: float
    y: float
    z: float = 0.0
    room_id: str = "UNASSIGNED"
    coverage_radius_m: float = 6.37
    spacing_m: float = 9.1
    ceiling_height_m: float = 3.0
    occupancy_type: str = "office"
    is_code_compliant: bool = False
    coverage_pct: float = 0.0
    run_id: str = ""
    evidence_hash: str = ""


class ARExportRequest(BaseModel):
    """Request body for /api/v2/ar/export."""

    building_id: str = "API_Building"
    format: str = Field("both", pattern="^(glb|usdz|both)$")
    nodes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="AR scene nodes (optional — empty uses DigitalTwin)",
    )


class WebhookSubscribeRequest(BaseModel):
    """Request body for /api/v2/webhooks/subscribe."""

    url: str
    secret: str = Field(..., min_length=32)  # V135 F-33: NIST SP 800-107
    event_types: list[str] = Field(default_factory=list)


class WebhookPublishRequest(BaseModel):
    """Request body for /api/v2/webhooks/publish."""

    event_type: str
    source: str
    data: dict[str, Any]
    trace_id: str | None = None


class SmokeDensityPointRequest(BaseModel):
    """V138 F-14: Pydantic model for smoke density point (was unvalidated Dict)."""

    x: float = Field(..., ge=-10000, le=10000)
    y: float = Field(..., ge=-10000, le=10000)
    z: float = Field(..., ge=-100, le=100)
    density_kg_m3: float = Field(..., ge=0, le=100)


class SmokeSimulationStateRequest(BaseModel):
    """
    Request body for /api/v2/smoke-simulation/state.

    V138 F-13: Added max_length to prevent DoS.
    V138 F-14: Use Pydantic model for smoke_density_points (was unvalidated Dict).
    """

    room_id: str = Field(..., max_length=200)
    smoke_density_points: list[SmokeDensityPointRequest] = Field(
        default_factory=list, max_length=10000
    )
    visibility_at_height: dict[float, float] = Field(default_factory=dict)
    fds_run_id: str | None = None


# ---------------------------------------------------------------------------
# Generative Design Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/generative/design", dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))]
)
async def generate_design_variants(req: GenerativeDesignRequest) -> dict[str, Any]:
    """
    Generate 3 layout variants (Cost-Min, Standard, Safety-Max).

    Returns scored variants with recommendation based on occupancy.
    """
    # Phase 3 cleanup: fireai.core.spatial_engine.* was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.density_optimizer import Room
    #   from <new_module>.generative_layout_agent import GenerativeLayoutAgent
    raise _fireai_unavailable_503("fireai.core.spatial_engine") from None


# ---------------------------------------------------------------------------
# BIM Provider Endpoints
# ---------------------------------------------------------------------------


@router.get("/bim/providers")
async def list_bim_providers() -> dict[str, Any]:
    """List all registered BIM providers."""
    # Phase 3 cleanup: fireai.bridges.bim_provider was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.bim_provider import BIMProviderRegistry
    raise _fireai_unavailable_503("fireai.bridges.bim_provider") from None


@router.post(
    "/bim/extract-rooms", dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))]
)
async def extract_rooms(
    req: BIMExtractRoomsRequest,
) -> dict[
    str, Any
]:  # NOSONAR — S3776: cognitive complexity is inherent to the safety-critical algorithm
    """
    Extract rooms via configured BIM provider.

    V137 F-5 FIX: Added source path validation to prevent SSRF/path traversal.
    The OLD code passed ``req.source`` directly to ``provider.extract_rooms()``
    which calls ``ifcopenshell.open(source)`` — allowing arbitrary file reads.
    """
    # Phase 3 cleanup: fireai.bridges.bim_provider was removed (BAZSPARK cleanup).
    # The previous path-traversal hardening (V137 F-5 / V138 F-7) is preserved
    # in the TODO comment for reference when the BIM provider is restored.
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.bim_provider import get_provider
    #   # V137 F-5 / V138 F-7: validate req.source path before passing to provider
    raise _fireai_unavailable_503("fireai.bridges.bim_provider") from None


@router.get("/bim/health")
async def bim_health() -> dict[str, Any]:
    """Health check for active BIM provider."""
    # Phase 3 cleanup: fireai.bridges.bim_provider was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.bim_provider import get_provider
    raise _fireai_unavailable_503("fireai.bridges.bim_provider") from None


# ---------------------------------------------------------------------------
# IFC 4.3 Mapping Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/ifc43/map-detector", dependencies=[Depends(require_permission(Permission.EXPORT_EXECUTE))]
)
async def map_detector_to_ifc43(req: IFC43MapDetectorRequest) -> dict[str, Any]:
    """Map an ETAP detector to IFC 4.3 ADD2 representation."""
    # Phase 3 cleanup: fireai.bridges.ifc43_mapper was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.ifc43_mapper import IFC43Mapper
    raise _fireai_unavailable_503("fireai.bridges.ifc43_mapper") from None


@router.post(
    "/ifc43/map-project", dependencies=[Depends(require_permission(Permission.EXPORT_EXECUTE))]
)
async def map_project_to_ifc43(req: dict[str, Any]) -> dict[str, Any]:
    """Map an entire ETAP project to IFC 4.3 ADD2."""
    # Phase 3 cleanup: fireai.bridges.ifc43_mapper was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.ifc43_mapper import IFC43Mapper
    raise _fireai_unavailable_503("fireai.bridges.ifc43_mapper") from None


# ---------------------------------------------------------------------------
# AR Export Endpoints
# ---------------------------------------------------------------------------


@router.post("/ar/export", dependencies=[Depends(require_permission(Permission.EXPORT_EXECUTE))])
async def export_ar_snapshot(req: ARExportRequest) -> dict[str, Any]:
    """
    Export DigitalTwin snapshot to GLB/USDZ for AR visualization.

    Returns base64-encoded file content for each requested format.
    """
    # Phase 3 cleanup: fireai.integration.ar_metadata_exporter was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.ar_metadata_exporter import (
    #       ARExportFormat, ARMetadataExporter, ARSceneNode, ARSnapshot,
    #   )
    raise _fireai_unavailable_503("fireai.integration.ar_metadata_exporter") from None


# ---------------------------------------------------------------------------
# Webhook Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/webhooks/subscribe", dependencies=[Depends(require_permission(Permission.SYSTEM_CONFIG))]
)
async def subscribe_webhook(req: WebhookSubscribeRequest) -> dict[str, Any]:
    """Subscribe to webhook events."""
    # Phase 3 cleanup: fireai.infrastructure.webhook_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.webhook_service import WebhookSubscription, get_webhook_service
    raise _fireai_unavailable_503("fireai.infrastructure.webhook_service") from None


@router.get("/webhooks/subscriptions")
async def list_webhook_subscriptions() -> dict[str, Any]:
    """List all webhook subscriptions."""
    # Phase 3 cleanup: fireai.infrastructure.webhook_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.webhook_service import get_webhook_service
    raise _fireai_unavailable_503("fireai.infrastructure.webhook_service") from None


@router.delete(
    "/webhooks/subscriptions/{sub_id}",
    dependencies=[Depends(require_permission(Permission.SYSTEM_CONFIG))],
)
async def unsubscribe_webhook(sub_id: str) -> dict[str, Any]:
    """Remove a webhook subscription."""
    # Phase 3 cleanup: fireai.infrastructure.webhook_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.webhook_service import get_webhook_service
    raise _fireai_unavailable_503("fireai.infrastructure.webhook_service") from None


@router.post(
    "/webhooks/publish", dependencies=[Depends(require_permission(Permission.SYSTEM_CONFIG))]
)
async def publish_webhook_event(req: WebhookPublishRequest) -> dict[str, Any]:
    """Publish an event to all matching webhook subscribers."""
    # Phase 3 cleanup: fireai.infrastructure.webhook_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.webhook_service import get_webhook_service
    raise _fireai_unavailable_503("fireai.infrastructure.webhook_service") from None


# ---------------------------------------------------------------------------
# Smoke Simulation Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/smoke-simulation/state",
    dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))],
)
async def create_smoke_state(req: SmokeSimulationStateRequest) -> dict[str, Any]:
    """
    Create or update smoke simulation state for a room.

    If FDS data is provided (fds_run_id), creates a validated state.
    Otherwise, creates a placeholder state with safety warnings.
    """
    # Phase 3 cleanup: fireai.core.smoke_simulation_state was removed (BAZSPARK cleanup).
    # The V137 F-6 FDS run ID format validation is preserved in the TODO
    # comment for reference when the smoke-simulation state module is restored.
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.smoke_simulation_state import (
    #       SmokeDensityPoint, SmokeSimulationState,
    #   )
    #   # V137 F-6: validate fds_run_id format (^fds-\d{4}-\d{3,}$) before use
    raise _fireai_unavailable_503("fireai.core.smoke_simulation_state") from None


# ---------------------------------------------------------------------------
# V141: Vector Memory & Topology Endpoints
# ---------------------------------------------------------------------------


class VectorMemoryStoreRequest(BaseModel):
    """Request body for /api/v2/memory/store."""

    content: str = Field(..., min_length=1, max_length=10000)
    memory_type: str = Field(
        "conversation", description="conversation|study_result|document|etap_knowledge"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VectorMemorySearchRequest(BaseModel):
    """Request body for /api/v2/memory/search."""

    query: str = Field(..., min_length=1, max_length=1000)
    memory_type: str = Field("conversation")
    limit: int = Field(5, ge=1, le=50)
    score_threshold: float = Field(0.0, ge=0.0, le=1.0)


class TopologyAddElementRequest(BaseModel):
    """Request body for /api/v2/topology/element."""

    element_id: str = Field(..., max_length=200)
    element_type: str = Field(..., description="Bus|Line|Transformer|Load|Breaker|Generator")
    name: str = Field("", max_length=200)
    properties: Dict[str, Any] = Field(default_factory=dict)


class TopologyAddConnectionRequest(BaseModel):
    """Request body for /api/v2/topology/connection."""

    from_element: str = Field(..., max_length=200)
    to_element: str = Field(..., max_length=200)
    relationship_type: str = Field("CONNECTED_TO")
    properties: Dict[str, Any] = Field(default_factory=dict)


class TopologyImpactRequest(BaseModel):
    """Request body for /api/v2/topology/impact."""

    breaker_id: str = Field(..., max_length=200)


@router.post("/memory/store", dependencies=[Depends(require_permission(Permission.SYSTEM_CONFIG))])
async def store_memory(req: VectorMemoryStoreRequest) -> Dict[str, Any]:
    """Store a memory entry in Qdrant vector database."""
    # Phase 3 cleanup: fireai.infrastructure.vector_memory_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.vector_memory_service import MemoryType, get_vector_memory
    raise _fireai_unavailable_503("fireai.infrastructure.vector_memory_service") from None


@router.post("/memory/search")
async def search_memory(req: VectorMemorySearchRequest) -> Dict[str, Any]:
    """Search for similar memories in Qdrant."""
    # Phase 3 cleanup: fireai.infrastructure.vector_memory_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.vector_memory_service import MemoryType, get_vector_memory
    raise _fireai_unavailable_503("fireai.infrastructure.vector_memory_service") from None


@router.get("/memory/health")
async def memory_health() -> Dict[str, Any]:
    """Check Qdrant vector database health."""
    # Phase 3 cleanup: fireai.infrastructure.vector_memory_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.vector_memory_service import get_vector_memory
    raise _fireai_unavailable_503("fireai.infrastructure.vector_memory_service") from None


@router.post(
    "/topology/element", dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))]
)
async def add_topology_element(req: TopologyAddElementRequest) -> Dict[str, Any]:
    """Add a network element to the Neo4j topology graph."""
    # Phase 3 cleanup: fireai.infrastructure.topology_graph_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.topology_graph_service import (
    #       ElementType, NetworkElement, get_topology_service,
    #   )
    raise _fireai_unavailable_503("fireai.infrastructure.topology_graph_service") from None


@router.post(
    "/topology/connection",
    dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))],
)
async def add_topology_connection(req: TopologyAddConnectionRequest) -> Dict[str, Any]:
    """Add a connection between two network elements."""
    # Phase 3 cleanup: fireai.infrastructure.topology_graph_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.topology_graph_service import (
    #       NetworkConnection, RelationshipType, get_topology_service,
    #   )
    raise _fireai_unavailable_503("fireai.infrastructure.topology_graph_service") from None


@router.post(
    "/topology/impact", dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))]
)
async def analyze_impact(req: TopologyImpactRequest) -> Dict[str, Any]:
    """
    Analyze the impact of tripping a breaker.

    Answers: "If I trip this breaker, which loads and buses are affected?"
    """
    # Phase 3 cleanup: fireai.infrastructure.topology_graph_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.topology_graph_service import get_topology_service
    raise _fireai_unavailable_503("fireai.infrastructure.topology_graph_service") from None


@router.get("/topology/health")
async def topology_health() -> Dict[str, Any]:
    """Check Neo4j topology graph health."""
    # Phase 3 cleanup: fireai.infrastructure.topology_graph_service was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.topology_graph_service import get_topology_service
    raise _fireai_unavailable_503("fireai.infrastructure.topology_graph_service") from None


# ---------------------------------------------------------------------------
# V142: GraphRAG Endpoints
# ---------------------------------------------------------------------------


class GraphRAGAddKnowledgeRequest(BaseModel):
    """Request body for /api/v2/graphrag/knowledge."""

    text: str = Field(..., min_length=1, max_length=50000)
    extract_entities: bool = Field(True, description="Extract entities/relationships via LLM")


class GraphRAGAskRequest(BaseModel):
    """Request body for /api/v2/graphrag/ask."""

    question: str = Field(..., min_length=1, max_length=2000)


class GraphRAGSearchRequest(BaseModel):
    """Request body for /api/v2/graphrag/search."""

    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(5, ge=1, le=50)


@router.post(
    "/graphrag/knowledge",
    dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))],
)
async def add_graphrag_knowledge(req: GraphRAGAddKnowledgeRequest) -> Dict[str, Any]:
    """
    Add knowledge to GraphRAG (vector + entity/relationship graph).

    V142: Uses LLMGraphTransformer to extract entities and relationships
    from text, stores them in Neo4j as a knowledge graph. Also stores
    the original text as a vector for semantic search.
    """
    # Phase 3 cleanup: fireai.infrastructure.graphrag_engine was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.graphrag_engine import get_graphrag_engine
    raise _fireai_unavailable_503("fireai.infrastructure.graphrag_engine") from None


@router.post(
    "/graphrag/ask", dependencies=[Depends(require_permission(Permission.CALCULATION_EXECUTE))]
)
async def ask_graphrag(req: GraphRAGAskRequest) -> Dict[str, Any]:
    """
    Ask a question using GraphRAG hybrid retrieval (vector + graph).

    V142: The GraphCypherQAChain will:
    1. Generate a Cypher query from the natural language question
    2. Execute on Neo4j (graph traversal)
    3. Formulate a natural language answer
    """
    # Phase 3 cleanup: fireai.infrastructure.graphrag_engine was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.graphrag_engine import get_graphrag_engine
    raise _fireai_unavailable_503("fireai.infrastructure.graphrag_engine") from None


@router.post(
    "/graphrag/search", dependencies=[Depends(require_permission(Permission.CALCULATION_READ))]
)
async def search_graphrag(req: GraphRAGSearchRequest) -> Dict[str, Any]:
    """Semantic search in GraphRAG vector store (no LLM, fast)."""
    # Phase 3 cleanup: fireai.infrastructure.graphrag_engine was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.graphrag_engine import get_graphrag_engine
    raise _fireai_unavailable_503("fireai.infrastructure.graphrag_engine") from None


@router.get("/graphrag/health")
async def graphrag_health() -> Dict[str, Any]:
    """Check GraphRAG engine health."""
    # Phase 3 cleanup: fireai.infrastructure.graphrag_engine was removed (BAZSPARK cleanup).
    # TODO(phase-3-migration): restore via:
    #   from <new_module>.graphrag_engine import get_graphrag_engine
    raise _fireai_unavailable_503("fireai.infrastructure.graphrag_engine") from None


# ---------------------------------------------------------------------------
# Health Endpoint for v2
# ---------------------------------------------------------------------------


@router.get("/health")
async def v2_health() -> dict[str, Any]:
    """Health check for v2 API endpoints."""
    return {
        "status": "ok",
        "version": "v2",
        "endpoints": [
            "/api/v2/generative/design",
            "/api/v2/bim/providers",
            "/api/v2/bim/extract-rooms",
            "/api/v2/bim/health",
            "/api/v2/ifc43/map-detector",
            "/api/v2/ifc43/map-project",
            "/api/v2/ar/export",
            "/api/v2/webhooks/subscribe",
            "/api/v2/webhooks/subscriptions",
            "/api/v2/webhooks/publish",
            "/api/v2/smoke-simulation/state",
            "/api/v2/auth/csrf-token",
            "/api/v2/health",
        ],
        "capabilities": [
            "generative_design",
            "bim_provider_abstraction",
            "ifc43_mapping",
            "ar_metadata_export",
            "webhook_delivery",
            "smoke_simulation_state",
            "csrf_protection",
        ],
    }


# ---------------------------------------------------------------------------
# CSRF Token Endpoint (PHASE 1.1)
# ---------------------------------------------------------------------------


@router.get("/auth/csrf-token")
async def get_csrf_token(request: Request) -> dict[str, Any]:
    """
    Issue a CSRF token via Double Submit Cookie pattern.

    Sets the CSRF token in:
    1. A cookie (__Host-fireai_csrf_token, SameSite=Strict)  # Phase 3: cookie name retained for backward compat — Phase 4/8.1 will rename to etap_csrf_token
    2. The response body (for the frontend to extract and send in X-CSRF-Token header)

    The frontend MUST call this endpoint once per session, then include the
    token in the X-CSRF-Token header for all subsequent POST/PUT/DELETE/PATCH requests.

    Per OWASP CSRF Prevention Cheat Sheet — Double Submit Cookie pattern.
    """
    from fastapi.responses import JSONResponse

    from backend.security_csrf import (
        CSRF_COOKIE_NAME,
        build_csrf_cookie_header,
        generate_csrf_token,
    )

    token = generate_csrf_token()

    # Detect HTTPS from X-Forwarded-Proto (common behind reverse proxy)
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    is_https = forwarded_proto == "https" or request.url.scheme == "https"

    cookie_header = build_csrf_cookie_header(token, is_https=is_https)  # NOSONAR - python:S930

    response = JSONResponse(
        content={
            "csrf_token": token,
            "cookie_name": CSRF_COOKIE_NAME,
            "header_name": "X-CSRF-Token",
            "instructions": (
                "Include this token in the X-CSRF-Token header for all "
                "POST/PUT/DELETE/PATCH requests. The cookie is set automatically."
            ),
        }
    )
    response.headers["Set-Cookie"] = cookie_header
    return response


__all__ = ["router"]
