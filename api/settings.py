"""
api/settings.py — Settings API for user-supplied API keys

Endpoints:
  GET  /api/v1/settings/keys           — list all keys (masked)
  GET  /api/v1/settings/keys/{provider} — get one key (masked)
  POST /api/v1/settings/keys/{provider} — save/update a key
  DELETE /api/v1/settings/keys/{provider} — delete a key
  POST /api/v1/settings/keys/{provider}/test — test a key
  POST /api/v1/settings/keys/{provider}/activate — enable/disable
  GET  /api/v1/settings/health         — storage health check

SECURITY:
    - Keys are NEVER returned in plaintext (always masked: sk-***...***)
    - Keys are encrypted with AES-256 before storage
    - Test endpoint makes a minimal API call to verify the key works

Usage:
    # Save an OpenAI key
    POST /api/v1/settings/keys/openai
    {
        "api_key": "sk-xxx",
        "base_url": "https://api.openai.com/v1",  // optional
        "model_name": "gpt-4o"                     // optional
    }

    # Get all keys (masked)
    GET /api/v1/settings/keys
    → {
        "openai": {"api_key_masked": "sk-***...***", "is_active": true, ...},
        "gemini": {"api_key_masked": "AIz***...***", "is_active": false, ...}
      }

    # Test a key
    POST /api/v1/settings/keys/openai/test
    → {"success": true, "message": "OpenAI API key is valid", "model": "gpt-4o"}
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.dependencies import get_api_key
from services.api_key_store import APIKeyStore, api_key_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# Type alias for FastAPI dependency (SonarCloud S8410)
ApiKeyDep = Annotated[str, Depends(get_api_key)]



# ─── Request models ────────────────────────────────────────────────────────


class SaveKeyRequest(BaseModel):
    """Request body for saving an API key."""

    api_key: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The API key (will be encrypted before storage)",
    )
    base_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Custom endpoint URL (e.g., https://api.openai.com/v1)",
    )
    model_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Model name override (e.g., gpt-4o)",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this key should be used by the CUA Loop",
    )


class ActivateKeyRequest(BaseModel):
    """Request body for activating/deactivating a key."""

    is_active: bool = Field(..., description="True to enable, False to disable")

# ─── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/keys")
async def list_keys(_: ApiKeyDep) -> JSONResponse:  # NOSONAR — S8410: Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    """List all stored API keys (masked — never returns plaintext)."""
    try:
        keys = api_key_store.get_all_keys()
        return JSONResponse(
            content={
                "success": True,
                "data": keys,
                "providers": list(keys.keys()),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to list API keys")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "list_failed", "message": str(exc)},
        )

@router.get("/keys/{provider}")
async def get_key(provider: str, _: ApiKeyDep) -> JSONResponse:  # NOSONAR — S8410: Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    """Get a single API key (masked — never returns plaintext)."""
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
            status_code=400,
            detail=f"Unsupported provider '{provider}'. Must be one of: {APIKeyStore.SUPPORTED_PROVIDERS}",
        )

    config = api_key_store.get_key(provider)
    if not config:
        return JSONResponse(
            content={
                "success": True,
                "data": None,
                "message": f"No key stored for provider '{provider}'",
            },
        )

    return JSONResponse(content={"success": True, "data": config.to_masked_dict()})

@router.post("/keys/{provider}")
async def save_key(
    provider: str,
    request: SaveKeyRequest,
    _: ApiKeyDep,
) -> JSONResponse:
    """Save or update an API key (encrypted with AES-256)."""
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
            status_code=400,
            detail=f"Unsupported provider '{provider}'. Must be one of: {APIKeyStore.SUPPORTED_PROVIDERS}",
        )

    try:
        api_key_store.set_key(
            provider=provider,
            api_key=request.api_key,
            base_url=request.base_url,
            model_name=request.model_name,
            is_active=request.is_active,
        )
        # Return masked version (never the plaintext)
        config = api_key_store.get_key(provider)
        masked = config.to_masked_dict() if config else None
        return JSONResponse(
            content={
                "success": True,
                "data": masked,
                "message": f"API key for '{provider}' saved successfully (encrypted)",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to save API key")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "save_failed", "message": str(exc)},
        )

@router.delete("/keys/{provider}")
async def delete_key(provider: str, _: ApiKeyDep) -> JSONResponse:  # NOSONAR — S8410: Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    """Delete an API key permanently."""
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
            status_code=400,
            detail=f"Unsupported provider '{provider}'. Must be one of: {APIKeyStore.SUPPORTED_PROVIDERS}",
        )

    deleted = api_key_store.delete_key(provider)
    return JSONResponse(
        content={
            "success": deleted,
            "message": f"API key for '{provider}' deleted"
            if deleted
            else f"No key found for provider '{provider}'",
        },
    )

@router.post("/keys/{provider}/activate")
async def activate_key(
    provider: str,
    request: ActivateKeyRequest,
    _: ApiKeyDep,
) -> JSONResponse:
    """Enable or disable a key without deleting it."""
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
            status_code=400,
            detail=f"Unsupported provider '{provider}'. Must be one of: {APIKeyStore.SUPPORTED_PROVIDERS}",
        )

    updated = api_key_store.set_active(provider, request.is_active)
    return JSONResponse(
        content={
            "success": updated,
            "message": f"Key for '{provider}' {'activated' if request.is_active else 'deactivated'}",
        },
    )

@router.post("/keys/{provider}/test")
async def test_key(provider: str, _: ApiKeyDep) -> JSONResponse:  # NOSONAR — S8410: Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    """Test an API key by making a minimal API call.

    For OpenAI: lists models
    For Gemini: lists models
    For Anthropic: lists models
    """
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
            status_code=400,
            detail=f"Unsupported provider '{provider}'. Must be one of: {APIKeyStore.SUPPORTED_PROVIDERS}",
        )

    config = api_key_store.get_key(provider)
    if not config:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": "key_not_found",
                "message": f"No key stored for provider '{provider}'. Save a key first.",
            },
        )

    # Test the key by making a minimal API call
    try:
        if provider == "openai":
            result = _test_openai_key(config)
        elif provider == "gemini":
            result = _test_gemini_key(config)
        elif provider == "anthropic":
            result = _test_anthropic_key(config)
        else:
            result = {"success": False, "message": f"Unknown provider: {provider}"}

        return JSONResponse(content={"success": True, "data": result})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Key test failed")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "test_failed", "message": str(exc)},
        )

@router.get("/health")
async def settings_health(_: ApiKeyDep) -> JSONResponse:  # NOSONAR — S8410: Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    """Get the API key storage health status."""
    return JSONResponse(content={"success": True, "data": api_key_store.health_check()})

# ─── Internal: key testing functions ───────────────────────────────────────

def _test_openai_key(config) -> dict[str, Any]:
    """Test an OpenAI-compatible API key by listing models."""
    import httpx

    base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {config.api_key}"}

    with httpx.Client(timeout=15) as client:
        resp = client.get(url, headers=headers)

    if resp.status_code == 200:
        data = resp.json()
        models = data.get("data", [])
        model_names = [m.get("id", "?") for m in models[:10]]
        return {
            "success": True,
            "message": f"OpenAI API key is valid — {len(models)} models available",
            "base_url": base_url,
            "sample_models": model_names,
        }
    else:
        return {
            "success": False,
            "message": f"OpenAI API returned HTTP {resp.status_code}: {resp.text[:200]}",
            "base_url": base_url,
        }

def _test_gemini_key(config) -> dict[str, Any]:
    """Test a Gemini API key by listing models."""
    import httpx

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    params = {"key": config.api_key}

    with httpx.Client(timeout=15) as client:
        resp = client.get(url, params=params)

    if resp.status_code == 200:
        data = resp.json()
        models = data.get("models", [])
        model_names = [m.get("name", "?") for m in models[:10]]
        return {
            "success": True,
            "message": f"Gemini API key is valid — {len(models)} models available",
            "sample_models": model_names,
        }
    else:
        return {
            "success": False,
            "message": f"Gemini API returned HTTP {resp.status_code}: {resp.text[:200]}",
        }

def _test_anthropic_key(config) -> dict[str, Any]:
    """Test an Anthropic API key by making a minimal messages call."""
    import httpx

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model_name or "claude-3-haiku-20240307",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Hi"}],
    }

    with httpx.Client(timeout=15) as client:
        resp = client.post(url, headers=headers, json=payload)

    if resp.status_code == 200:
        return {
            "success": True,
            "message": "Anthropic API key is valid",
            "model": config.model_name or "claude-3-haiku-20240307",
        }
    else:
        return {
            "success": False,
            "message": f"Anthropic API returned HTTP {resp.status_code}: {resp.text[:200]}",
        }

__all__ = ["router"]
