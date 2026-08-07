"""
api/copilot_config.py — Copilot Configuration API
===================================================

Retrieve and update AI model parameters for the ETAP-AI copilot system.

Endpoints under ``/api/v1/copilot/config``:

* ``GET  /``              — Retrieve current copilot configuration
* ``PUT  /``              — Update copilot configuration (partial update allowed)
* ``GET  /models``        — List available models in the cascade
* ``POST /models/reorder`` — Reorder the fallback chain

Configuration parameters
------------------------
* **AI_MODEL_FALLBACK_CHAIN** — ordered list of model names for fallback routing
* **LLM_TEMPERATURE** — sampling temperature (0.0–1.0, default 0.7)
* **MAX_TOKENS** — maximum response tokens (256–16384, default 4096)
* **FALLBACK_NOTIFICATION_ENABLED** — whether to notify on fallback events
* **PRIMARY_MODEL** — the first-choice model (default: "gpt-4o")

Author: ETAP Integration Team
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.dependencies import get_api_key

_SAFE_LOG_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_for_log(value: object, max_len: int = 200) -> str:
    """Sanitize user-controlled input before writing to logs.

    Strips control characters (prevents log injection / CRLF spoofing) and
    truncates to a sensible length so an attacker cannot flood log storage.
    """
    if value is None:
        return "None"
    s = _SAFE_LOG_RE.sub("_", str(value))
    if len(s) > max_len:
        s = s[:max_len] + "...[truncated]"
    return s
logger = logging.getLogger("etap.api.copilot_config")

router = APIRouter(
    prefix="/api/v1/copilot/config",
    tags=["copilot", "ai-config"],
    dependencies=[Depends(get_api_key)],
)


# ---------------------------------------------------------------------------
# In-memory configuration store
# ---------------------------------------------------------------------------

_MODEL_CATALOG: dict[str, dict] = {
    "gpt-4o": {"provider": "openai", "priority": 1},
    "gpt-4o-mini": {"provider": "openai", "priority": 2},
    "gpt-3.5-turbo": {"provider": "openai", "priority": 3},
    "claude-3.5-sonnet": {"provider": "anthropic", "priority": 4},
    "claude-3-haiku": {"provider": "anthropic", "priority": 5},
}

_copilot_config: dict = {
    "ai_model_fallback_chain": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    "llm_temperature": 0.7,
    "max_tokens": 4096,
    "fallback_notification_enabled": True,
    "primary_model": "gpt-4o",
}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ModelCascadeInfo(BaseModel):
    """Information about a single model in the fallback cascade.

    Attributes:
        name: The model identifier (e.g., "gpt-4o").
        provider: The model provider (e.g., "openai", "anthropic").
        priority: The priority in the fallback chain (1 = highest).
    """

    name: str = Field(..., description="Model identifier")
    provider: str = Field(..., description="Model provider")
    priority: int = Field(..., ge=1, description="Priority in the fallback chain (1 = highest)")

    model_config = {"from_attributes": True}


class CopilotConfigResponse(BaseModel):
    """Full copilot configuration returned by the GET endpoint.

    Attributes:
        ai_model_fallback_chain: Ordered list of model names for fallback.
        llm_temperature: Sampling temperature for LLM responses.
        max_tokens: Maximum number of tokens in the response.
        fallback_notification_enabled: Whether fallback notifications are sent.
        primary_model: The primary (first-choice) model name.
    """

    ai_model_fallback_chain: list[str] = Field(
        ..., description="Ordered list of model names for fallback routing"
    )
    llm_temperature: float = Field(
        ..., ge=0.0, le=1.0, description="Sampling temperature (0.0–1.0)"
    )
    max_tokens: int = Field(
        ..., ge=256, le=16384, description="Maximum response tokens (256–16384)"
    )
    fallback_notification_enabled: bool = Field(
        ..., description="Whether to notify on fallback events"
    )
    primary_model: str = Field(
        ..., description="The first-choice model name"
    )

    model_config = {"from_attributes": True}


class CopilotConfigUpdateRequest(BaseModel):
    """Partial update request for copilot configuration.

    All fields are optional; only provided fields will be updated.

    Attributes:
        ai_model_fallback_chain: New ordered list of model names.
        llm_temperature: New sampling temperature.
        max_tokens: New maximum token count.
        fallback_notification_enabled: Toggle fallback notifications.
        primary_model: New primary model name.
    """

    ai_model_fallback_chain: Optional[list[str]] = Field(
        default=None, description="Ordered list of model names for fallback routing"
    )
    llm_temperature: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Sampling temperature (0.0–1.0)"
    )
    max_tokens: Optional[int] = Field(
        default=None, ge=256, le=16384, description="Maximum response tokens (256–16384)"
    )
    fallback_notification_enabled: Optional[bool] = Field(
        default=None, description="Whether to notify on fallback events"
    )
    primary_model: Optional[str] = Field(
        default=None, description="The first-choice model name"
    )

    model_config = {"from_attributes": True}


class ReorderModelsRequest(BaseModel):
    """Request body for reordering the model fallback chain.

    Attributes:
        ordered_models: List of model names in the desired priority order.
            Must contain at least one model. All models must exist in the catalog.
    """

    ordered_models: list[str] = Field(
        ...,
        min_length=1,
        description="Model names in desired priority order (first = highest priority)",
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", summary="Retrieve current copilot configuration")
async def get_copilot_config() -> JSONResponse:
    """Return the current copilot AI model configuration.

    Returns all configuration fields including the fallback chain,
    temperature, token limits, and notification settings.
    """
    return JSONResponse(
        content={
            "success": True,
            "config": CopilotConfigResponse(**_copilot_config).model_dump(),
        }
    )


@router.put("/", summary="Update copilot configuration")
async def update_copilot_config(
    body: CopilotConfigUpdateRequest,
    request: Request,
) -> JSONResponse:
    """Partially update the copilot AI model configuration.

    Only fields present in the request body will be updated; omitted
    fields retain their current values.

    Validation rules:
    * ``llm_temperature`` must be between 0.0 and 1.0
    * ``max_tokens`` must be between 256 and 16384
    * ``primary_model`` must be a known model in the catalog
    * ``ai_model_fallback_chain`` entries must all exist in the catalog
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    updates = body.model_dump(exclude_none=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update. Supply at least one configuration field.",
        )

    # Validate primary_model if provided
    if body.primary_model is not None and body.primary_model not in _MODEL_CATALOG:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown model: '{body.primary_model}'. "
            f"Available models: {list(_MODEL_CATALOG.keys())}",
        )

    # Validate fallback chain entries if provided
    if body.ai_model_fallback_chain is not None:
        unknown = [m for m in body.ai_model_fallback_chain if m not in _MODEL_CATALOG]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown models in fallback chain: {unknown}. "
                f"Available models: {list(_MODEL_CATALOG.keys())}",
            )

    # Apply updates
    _copilot_config.update(updates)

    # If primary_model was updated, ensure it's at the front of the fallback chain
    if body.primary_model is not None:
        chain = _copilot_config["ai_model_fallback_chain"]
        if body.primary_model in chain:
            chain.remove(body.primary_model)
        chain.insert(0, body.primary_model)
        _copilot_config["ai_model_fallback_chain"] = chain

    # If fallback chain was updated, ensure primary_model is consistent
    if body.ai_model_fallback_chain is not None:
        _copilot_config["primary_model"] = body.ai_model_fallback_chain[0]

    logger.info(
        "copilot_config_updated fields=%s trace_id=%s",
        list(updates.keys()),
        trace_id,
    )

    return JSONResponse(
        content={
            "success": True,
            "config": CopilotConfigResponse(**_copilot_config).model_dump(),
            "updated_fields": list(updates.keys()),
            "trace_id": trace_id,
        }
    )


@router.get("/models", summary="List available models in the cascade")
async def list_models() -> JSONResponse:
    """List all models in the fallback cascade with their provider and priority.

    Models are returned in the current fallback order (highest priority first).
    Models in the catalog but not in the current chain are also listed
    with their catalog priority.
    """
    chain = _copilot_config["ai_model_fallback_chain"]

    # Build cascade info for models in the chain
    cascade: list[dict] = []
    for idx, model_name in enumerate(chain, start=1):
        catalog_entry = _MODEL_CATALOG.get(model_name, {"provider": "unknown"})
        cascade.append(
            ModelCascadeInfo(
                name=model_name,
                provider=catalog_entry["provider"],
                priority=idx,
            ).model_dump()
        )

    # Also list models in the catalog but not currently in the chain
    chain_set = set(chain)
    available_not_in_chain: list[dict] = []
    for model_name, info in _MODEL_CATALOG.items():
        if model_name not in chain_set:
            available_not_in_chain.append(
                ModelCascadeInfo(
                    name=model_name,
                    provider=info["provider"],
                    priority=info["priority"],
                ).model_dump()
            )

    return JSONResponse(
        content={
            "success": True,
            "cascade": cascade,
            "available_not_in_chain": available_not_in_chain,
            "total_catalog_models": len(_MODEL_CATALOG),
            "active_chain_length": len(chain),
        }
    )


@router.post("/models/reorder", summary="Reorder the fallback chain")
async def reorder_models(
    body: ReorderModelsRequest,
    request: Request,
) -> JSONResponse:
    """Reorder the model fallback chain.

    The first model in the list becomes the primary model and the
    highest-priority option. All models in the list must exist in the
    catalog. Duplicate entries are not allowed.

    Args:
        body: Contains ``ordered_models`` — the new priority order.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")

    # Validate all models exist in catalog
    unknown = [m for m in body.ordered_models if m not in _MODEL_CATALOG]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown models: {unknown}. "
            f"Available models: {list(_MODEL_CATALOG.keys())}",
        )

    # Check for duplicates
    if len(body.ordered_models) != len(set(body.ordered_models)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate model names are not allowed in the fallback chain.",
        )

    # Apply the new order
    _copilot_config["ai_model_fallback_chain"] = list(body.ordered_models)
    _copilot_config["primary_model"] = body.ordered_models[0]

    logger.info(
        "copilot_models_reordered new_chain=%s trace_id=%s",
        body.ordered_models,
        trace_id,
    )

    # Build the updated cascade info
    cascade: list[dict] = []
    for idx, model_name in enumerate(body.ordered_models, start=1):
        catalog_entry = _MODEL_CATALOG[model_name]
        cascade.append(
            ModelCascadeInfo(
                name=model_name,
                provider=catalog_entry["provider"],
                priority=idx,
            ).model_dump()
        )

    return JSONResponse(
        content={
            "success": True,
            "cascade": cascade,
            "primary_model": _copilot_config["primary_model"],
            "trace_id": trace_id,
        }
    )


__all__ = ["router"]
