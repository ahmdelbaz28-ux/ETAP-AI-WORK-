"""
api/settings.py — Settings API for user-supplied API keys

Endpoints:
  GET  /api/v1/settings/keys           — list all keys (masked)
  GET  /api/v1/settings/keys/{provider} — get one key (masked)
  POST /api/v1/settings/keys/{provider} — save/update a key
  DELETE /api/v1/settings/keys/{provider} — delete a key
  POST /api/v1/settings/keys/{provider}/test — test a key
  POST /api/v1/settings/keys/{provider}/activate — enable/disable
  POST /api/v1/settings/rotate         — rotate a secret by NAME (no value)
  GET  /api/v1/settings/health         — storage health check

SECURITY:
    - Keys are NEVER returned in plaintext (always masked: sk-***...***)
    - Keys are encrypted with AES-256 before storage
    - Test endpoint makes a minimal API call to verify the key works
    - Rotate endpoint accepts ONLY the key NAME. It never accepts a value.
      For provider API keys, the stored entry is deleted and the user must
      save a new value via POST /keys/{provider}. For environment-backed
      secrets (FERNET_ENCRYPTION_KEY, JWT_SECRET_KEY, …), the server cannot
      rotate them at runtime; the endpoint logs the request and returns
      actionable instructions instead of silently 404'ing.

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

    # Rotate an env-backed secret (no value transmitted)
    POST /api/v1/settings/rotate
    → {"success": true, "rotated": false, "key": "FERNET_ENCRYPTION_KEY",
       "message": "'FERNET_ENCRYPTION_KEY' is managed by the deployment …"}
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import fastapi

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.dependencies import get_api_key
from services.api_key_store import APIKeyStore, api_key_store

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


class RotateKeyRequest(BaseModel):
    """Request body for rotating a secret by NAME only.

    SECURITY: this model intentionally does NOT have a `value` field. The
    server generates (or refuses to rotate) the new value — the client never
    sends one. This prevents secret leakage through the rotate API.
    """

    key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the secret to rotate (e.g. FERNET_ENCRYPTION_KEY). Value is NEVER sent.",
    )


# ─── Rotation allowlist ─────────────────────────────────────────────────────
# These are environment-variable-backed secrets that the UI's AllConfigurationTab
# marks as `isSecret: true`. The server CANNOT rotate them at runtime (they
# live in the OS environment / secret manager), but we accept the request so
# the UI gets a clear, actionable response instead of a silent 404.
# Audit note: keep this list in sync with the `isSecret: true` entries in
# `ui/src/components/AllConfigurationTab.tsx`.
ROTATABLE_ENV_SECRETS: frozenset[str] = frozenset(
    {
        "FERNET_ENCRYPTION_KEY",
        "ENCRYPTION_KEY",
        "CSRF_SECRET",
        "SESSION_SECRET",
        "POSTGRES_PASSWORD",
        "MASTRA_DB_URL",
        "AKAMAI_ORIGIN_SECRET",
        "CLOUDFLARE_ORIGIN_SECRET",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "VERCEL_TOKEN",
    }
)

# Provider API keys that CAN be rotated server-side via APIKeyStore.
# Deleting the stored entry forces the user to save a new value via
# POST /keys/{provider}. The new value never traverses this rotate endpoint.
ROTATABLE_PROVIDER_KEYS: frozenset[str] = frozenset(
    {"OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"}
)


# ─── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/keys")
async def list_keys(
    _: ApiKeyDep,
) -> (
    JSONResponse
):  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
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
    except Exception:  # noqa: BLE001
        logger.exception("Failed to list API keys")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "list_failed",
                "message": "Failed to list API keys",
            },
        )


@router.get("/keys/{provider}")
async def get_key(
    provider: str, _: ApiKeyDep
) -> (
    JSONResponse
):  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    """Get a single API key (masked — never returns plaintext)."""
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
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


@router.post("/keys/{provider}", responses={400: {"description": "Invalid API key configuration"}})
async def save_key(
    provider: str,
    request: SaveKeyRequest,
    _: ApiKeyDep,
) -> JSONResponse:
    """Save or update an API key (encrypted with AES-256)."""
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
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
        logger.warning(
            "api_key_save_validation_failed provider=%s error=%s",
            _sanitize_for_log(provider),
            _sanitize_for_log(str(exc)),
        )
        raise HTTPException(status_code=400, detail="Invalid API key configuration") from exc
    except Exception:  # noqa: BLE001
        logger.exception("Failed to save API key")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "save_failed", "message": "Failed to save API key"},
        )


@router.delete("/keys/{provider}")
async def delete_key(
    provider: str, _: ApiKeyDep
) -> (
    JSONResponse
):  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    """Delete an API key permanently."""
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
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
        raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
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


@router.post("/rotate", responses={400: {"description": "Key is not rotatable"}})
async def rotate_secret(
    request: RotateKeyRequest,
    _: ApiKeyDep,
) -> JSONResponse:
    """Rotate a secret by NAME.

    Accepts ONLY the key name — never the value. Two code paths:

    1. **Provider API keys** (OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY):
       The stored entry is deleted from APIKeyStore. The caller must save a
       new value via ``POST /api/v1/settings/keys/{provider}``. Returns
       ``rotated: true``.

    2. **Environment-backed secrets** (FERNET_ENCRYPTION_KEY, CSRF_SECRET,
       R2_SECRET_ACCESS_KEY, …): The server cannot rotate these at runtime
       because they live in the OS environment / secret manager. The request
       is logged for audit purposes and the response contains actionable
       instructions ("rotate via your secret manager and restart").
       Returns ``rotated: false``.

    Any key not in the union of the two allowlists is rejected with 400 to
    prevent probing of arbitrary environment variables.
    """
    # Normalize: env var names are uppercase, alphanumeric + underscore only.
    key = request.key.upper().strip()

    # ─── Provider-key path (server-side rotation via APIKeyStore) ────────
    if key in ROTATABLE_PROVIDER_KEYS:
        # OPENAI_API_KEY → provider "openai"
        provider = key.removesuffix("_API_KEY").lower()
        if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "rotated": False,
                    "key": key,
                    "error": "unsupported_provider",
                    "message": (
                        f"Provider '{provider}' is not in the supported list: "
                        f"{sorted(APIKeyStore.SUPPORTED_PROVIDERS)}"
                    ),
                },
            )
        deleted = api_key_store.delete_key(provider)
        logger.info(
            "provider_key_rotated key=%s provider=%s deleted=%s",
            key,
            provider,
            deleted,
        )
        return JSONResponse(
            content={
                "success": True,
                "rotated": deleted,
                "key": key,
                "message": (
                    f"Provider key '{key}' deleted. Save a new value via "
                    f"POST /api/v1/settings/keys/{provider}."
                ),
            }
        )

    # ─── Environment-backed path (manual rotation required) ─────────────
    if key in ROTATABLE_ENV_SECRETS:
        # Log the rotation request so audit trails capture who asked for what.
        # We do NOT touch os.environ here — env vars are owned by the
        # deployment environment (Vault, AWS Secrets Manager, GitHub Actions
        # secrets, etc.) and mutating them at runtime would not survive a
        # restart and could break running workers holding the old value.
        logger.info(
            "env_secret_rotation_requested key=%s — env-backed, manual rotation required",
            key,
        )
        return JSONResponse(
            content={
                "success": True,
                "rotated": False,
                "key": key,
                "message": (
                    f"'{key}' is managed by the deployment environment. "
                    "Rotate it via your secret manager (Vault, AWS Secrets Manager, "
                    "GitHub Actions secrets) and restart the service. "
                    "The new value never traverses this API."
                ),
            }
        )

    # ─── Reject unknown keys to prevent env-var probing ─────────────────
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "rotated": False,
            "key": key,
            "error": "not_rotatable",
            "message": (
                f"Key '{key}' is not in the rotatable secrets allowlist. "
                "If this is a real secret that should be rotatable, add it to "
                "ROTATABLE_ENV_SECRETS or ROTATABLE_PROVIDER_KEYS in api/settings.py."
            ),
        },
    )


@router.post("/keys/{provider}/test")
async def test_key(
    provider: str, request: fastapi.Request, _: ApiKeyDep
) -> (
    JSONResponse
):  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    """Test an API key by making a minimal API call.

    For OpenAI: lists models
    For Gemini: lists models
    For Anthropic: lists models
    """
    provider = provider.lower().strip()
    if provider not in APIKeyStore.SUPPORTED_PROVIDERS:
        raise HTTPException(  # NOSONAR HTTPException responses will be documented in API refactoring sprint
            status_code=400,
            detail=f"Unsupported provider '{provider}'. Must be one of: {APIKeyStore.SUPPORTED_PROVIDERS}",
        )

    inline_config = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            from services.api_key_store import APIKeyConfig

            inline_api_key = body.get("api_key")
            if isinstance(inline_api_key, str) and inline_api_key.strip():
                inline_config = APIKeyConfig(
                    provider=provider,
                    api_key=inline_api_key.strip(),
                    base_url=body.get("base_url"),
                    model_name=body.get("model_name"),
                    is_active=True,
                )
    except Exception:
        inline_config = None

    if inline_config is not None:
        config = inline_config
    else:
        config = api_key_store.get_key(provider)
        if not config:
            return JSONResponse(
                status_code=400,
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
    except Exception:  # noqa: BLE001
        logger.exception("Key test failed")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "test_failed", "message": "Failed to test API key"},
        )


@router.get("/health")
async def settings_health(
    _: ApiKeyDep,
) -> (
    JSONResponse
):  # NOSONAR Annotated[T, Depends(...)] migration will be done in API refactoring sprint
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
