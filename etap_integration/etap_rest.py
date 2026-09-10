"""Safe automatic ETAP drawing via the OFFICIAL DataHub etapAPI REST path.

Surgical addition: sends electrical components as DATA, asks ETAP to generate
the drawing server-side via Auto-Build, then re-reads for confirmation.
Any error => full reject, never a partial drawing.

Docs basis:
- https://www.etap.com/product/etap-rest-api (DataHub REST sections)
- https://www.etap.com/packages/data-exchange (Auto-Build + Excel mapping)

ENDPOINT TRUTH: every path below MUST exist in the customer's
``openapi.json`` (``https://<etap-host>/etapapi/swagger``). If DataHub/etapAPI
is not licensed, do NOT use this module — report BLOCKED instead of mocking
success. Endpoint constants are centralised in ``_ENDPOINTS`` so a version
drift fix touches one place.

Rules enforced here (fail-closed):
- No coordinates are ever invented: layout is ETAP Auto-Build server-side.
  ``x``/``y``/``coordinates`` keys are rejected locally before any HTTP.
- Max 50 elements/request; deletes require explicit IDs; mass delete denied.
- Secrets only via ``os.getenv``; tokens never logged (``_redact_secrets``).
- Partial server result => ETAPRestError + best-effort cleanup + audit log.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint table — MUST match the customer's openapi.json (see module doc).
# Expected: Project Data create/delete + Auto-Build trigger + Studies run.
# ---------------------------------------------------------------------------
_ENDPOINTS = {
    "health": "/health",
    "create_elements": "/api/v1/projects/{project_id}/elements",
    "trigger_autobuild": "/api/v1/projects/{project_id}/autobuild",
    "get_elements": "/api/v1/projects/{project_id}/elements",
    "delete_elements": "/api/v1/projects/{project_id}/elements",
}

MAX_ELEMENTS_PER_REQUEST = 50
RETRYABLE_STATUS = (502, 503, 504)
DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_RETRIES = 3


def _redact_secrets(text: str) -> str:
    """Redact tokens and API keys from URLs, query strings, headers, logs.

    NOTE: copied (not imported) from the archived
    ``gis_integration.providers.arcgis_provider`` so this module does not
    depend on a retired provider.
    """
    if not text or not isinstance(text, str):
        return text
    text = re.sub(
        r"((?:token|apiKey|api_key|key)=)[^&\s'\"]+",
        r"\1***",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(Bearer\s+)[^\s'\"]+",
        r"\1***",
        text,
        flags=re.IGNORECASE,
    )
    return text


class ETAPRestError(Exception):
    """Fail-closed error for the ETAP REST draw flow. Never partial success."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


ElementKind = Literal["bus", "transformer", "breaker"]

_REQUIRED_PROPS: dict[str, tuple[str, ...]] = {
    "bus": ("name", "base_kv"),
    "transformer": ("name", "from_bus", "to_bus"),
    "breaker": ("name", "from_bus", "to_bus"),
}

_FORBIDDEN_GEOM_KEYS = ("x", "y", "coordinates", "pos", "position")


class EtapElement(BaseModel):
    """One electrical component sent to ETAP as DATA (never geometry)."""

    model_config = ConfigDict(strict=False, extra="forbid")

    element_type: ElementKind
    name: str = Field(min_length=1, max_length=128)
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_element(self) -> EtapElement:
        props = self.properties or {}
        lowered = {str(k).lower() for k in props}
        geom = sorted(lowered.intersection(_FORBIDDEN_GEOM_KEYS))
        if geom:
            raise ValueError(
                f"Coordinates are forbidden (layout is ETAP Auto-Build server-side): {geom}"
            )
        missing = [p for p in _REQUIRED_PROPS[self.element_type] if p not in props and p != "name"]
        # 'name' lives on the model itself; the rest must be in properties.
        if missing:
            raise ValueError(f"Missing required properties for {self.element_type}: {missing}")
        return self

    def to_payload(self) -> dict[str, Any]:
        """Serialise as electrical data with server-side layout requested."""
        return {
            "element_type": self.element_type,
            "name": self.name,
            "properties": dict(self.properties),
            "coordinates": None,
            "auto_layout": True,
        }


class EtapDrawPlan(BaseModel):
    """Validated draw request: bounded, explicit, reasoned."""

    model_config = ConfigDict(strict=False, extra="forbid")

    project_id: str = Field(min_length=1, max_length=128)
    items: list[EtapElement] = Field(min_length=1, max_length=MAX_ELEMENTS_PER_REQUEST)
    delete_ids: list[str] = Field(default_factory=list, max_length=MAX_ELEMENTS_PER_REQUEST)
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator("delete_ids")
    @classmethod
    def _forbid_mass_delete(cls, ids: list[str]) -> list[str]:
        for i in ids:
            if not i or not str(i).strip() or str(i).strip() == "*":
                raise ValueError("Deletes require explicit element IDs; mass delete is forbidden")
        return ids


class DrawResult(BaseModel):
    """Verified outcome: created IDs + server drawing ID + readback proof."""

    model_config = ConfigDict(strict=False)

    created_ids: list[str]
    drawing_id: str
    readback_verified: bool


def _tenant_allowed(tenant_id: str | None) -> bool:
    """Per-tenant allowlist gate. Empty allowlist => deny everyone (fail-closed)."""
    raw = os.getenv("ETAP_REST_ALLOWLIST", "")
    allowed = {t.strip() for t in raw.split(",") if t.strip()}
    return bool(tenant_id) and tenant_id in allowed


def get_rest_client_from_env(transport: httpx.AsyncBaseTransport | None = None) -> EtapRestClient:
    """Build a client from env. Missing URL/token => ETAPRestError (unavailable)."""
    base_url = os.getenv("ETAP_REST_URL", "").strip()
    token = os.getenv("ETAP_REST_TOKEN", "").strip()
    if not base_url or not token:
        raise ETAPRestError(
            "MISSING_CONFIG",
            "ETAP REST is not configured (ETAP_REST_URL / ETAP_REST_TOKEN required).",
        )
    return EtapRestClient(base_url=base_url, token=token, transport=transport)


class EtapRestClient:
    """Async httpx client for ETAP DataHub etapAPI (draw flow only)."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        retries: int = DEFAULT_RETRIES,
        retry_delays: tuple[float, ...] = (0.5, 1.0, 2.0),
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout = timeout
        self.retries = retries
        self.retry_delays = retry_delays
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self._transport,
            headers={"Authorization": f"Bearer {self._token}"},
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send with retry on 502/503/504 ONLY. 401 => unavailable (fail-closed)."""
        last_exc: Exception | None = None
        attempts = max(1, self.retries)
        async with self._client() as client:
            for attempt in range(attempts):
                try:
                    resp = await client.request(method, path, **kwargs)
                except httpx.HTTPError as exc:
                    last_exc = exc
                    logger.warning(
                        "ETAP REST transport error (attempt %d): %s",
                        attempt + 1,
                        type(exc).__name__,
                    )
                else:
                    if resp.status_code == 401:
                        raise ETAPRestError("AUTH_FAILED", "ETAP REST rejected credentials (401).")
                    if resp.status_code in RETRYABLE_STATUS and attempt < attempts - 1:
                        delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                        logger.warning(
                            "ETAP REST %s (attempt %d), retrying", resp.status_code, attempt + 1
                        )
                        if delay:
                            await asyncio.sleep(delay)
                        continue
                    if resp.status_code >= 400:
                        raise ETAPRestError(
                            "HTTP_ERROR",
                            f"ETAP REST {method} {_redact_secrets(path)} -> {resp.status_code}",
                            {"status_code": resp.status_code},
                        )
                    return resp
                if attempt < attempts - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    if delay:
                        await asyncio.sleep(delay)
        raise ETAPRestError(
            "UNAVAILABLE",
            f"ETAP REST unreachable after {attempts} attempts: {last_exc}",
        )

    async def health_check(self) -> bool:
        """Probe the DataHub host. Any failure => False (caller decides)."""
        try:
            await self._request("GET", _ENDPOINTS["health"])
            return True
        except ETAPRestError as exc:
            logger.warning("ETAP REST health check failed: %s", exc.code)
            return False

    async def create_elements(self, project_id: str, items: list[EtapElement]) -> list[str]:
        """POST electrical data. Returns server element IDs (OBJECTIDs)."""
        payload = {"items": [e.to_payload() for e in items]}
        path = _ENDPOINTS["create_elements"].format(project_id=project_id)
        resp = await self._request("POST", path, json=payload)
        try:
            data = resp.json()
        except ValueError as exc:
            raise ETAPRestError("HTTP_ERROR", "ETAP REST returned non-JSON on create.", {}) from exc
        ids = data.get("created_ids") or data.get("ids") or []
        if not ids or len(ids) != len(items):
            raise ETAPRestError(
                "PARTIAL_RESULT",
                f"ETAP created {len(ids)}/{len(items)} elements — refusing partial drawing.",
                {"created_ids": ids},
            )
        return [str(i) for i in ids]

    async def trigger_autobuild(self, project_id: str) -> str:
        """Ask ETAP to generate the drawing server-side. Returns drawing ID."""
        path = _ENDPOINTS["trigger_autobuild"].format(project_id=project_id)
        resp = await self._request("POST", path, json={"project_id": project_id})
        try:
            data = resp.json()
        except ValueError as exc:
            raise ETAPRestError(
                "HTTP_ERROR", "ETAP REST returned non-JSON on autobuild.", {}
            ) from exc
        drawing_id = data.get("drawing_id") or data.get("id")
        if not drawing_id:
            raise ETAPRestError("AUTOBUILD_FAILED", "ETAP Auto-Build returned no drawing ID.", {})
        return str(drawing_id)

    async def get_elements(self, project_id: str, ids: list[str]) -> list[dict[str, Any]]:
        """Re-read elements for readback verification."""
        path = _ENDPOINTS["get_elements"].format(project_id=project_id)
        resp = await self._request("GET", path, params={"ids": ",".join(ids)})
        try:
            data = resp.json()
        except ValueError as exc:
            raise ETAPRestError(
                "HTTP_ERROR", "ETAP REST returned non-JSON on readback.", {}
            ) from exc
        elements = data.get("elements") or data.get("items") or []
        return list(elements)

    async def delete_elements(self, project_id: str, ids: list[str]) -> None:
        """Best-effort cleanup of explicitly listed IDs (rollback path)."""
        if not ids:
            return
        path = _ENDPOINTS["delete_elements"].format(project_id=project_id)
        try:
            await self._request("DELETE", path, json={"ids": list(ids)})
        except ETAPRestError as exc:
            logger.warning("ETAP REST cleanup delete failed (best-effort): %s", exc.code)

    async def apply_draw(self, plan: EtapDrawPlan) -> DrawResult:
        """Full flow: validate -> POST data -> POST autobuild -> GET verify.

        Local validation happens BEFORE any HTTP (pydantic already validated
        on model construction). Any server-side gap => ETAPRestError, never a
        partial drawing.
        """
        created_ids = await self.create_elements(plan.project_id, plan.items)
        try:
            drawing_id = await self.trigger_autobuild(plan.project_id)
            readback = await self.get_elements(plan.project_id, created_ids)
        except ETAPRestError:
            logger.warning(
                "ETAP draw failed after create; attempting cleanup of %d elements", len(created_ids)
            )
            await self.delete_elements(plan.project_id, created_ids)
            raise

        seen = set()
        for el in readback:
            for key in ("id", "objectid", "OBJECTID", "element_id"):
                if el.get(key) is not None:
                    seen.add(str(el.get(key)))
        missing = [i for i in created_ids if i not in seen]
        if missing:
            logger.warning(
                "ETAP draw readback missed %d elements; attempting cleanup", len(missing)
            )
            await self.delete_elements(plan.project_id, created_ids)
            logger.warning("ETAP draw PARTIAL_RESULT audited: missing=%s", missing)
            raise ETAPRestError(
                "VERIFY_MISMATCH",
                f"Readback missed {len(missing)}/{len(created_ids)} elements — drawing rejected.",
                {"missing_ids": missing},
            )
        logger.info(
            "ETAP draw verified: project=%s drawing=%s elements=%d",
            plan.project_id,
            drawing_id,
            len(created_ids),
        )
        return DrawResult(created_ids=created_ids, drawing_id=drawing_id, readback_verified=True)
