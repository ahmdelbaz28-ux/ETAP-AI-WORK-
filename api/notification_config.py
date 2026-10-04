"""
api/notification_config.py — Notification & Digest Configuration API
=====================================================================

Manage notification preferences, digest schedules, and webhook integrations
for the ETAP-AI-WORK platform.

Endpoints under ``/api/v1/notifications/digest/config``:

* ``GET  /``                     — Retrieve current notification configuration
* ``PUT  /``                     — Update notification configuration (partial)
* ``GET  /digest``               — Get digest schedule configuration
* ``PUT  /digest``               — Update digest schedule
* ``GET  /alerts``               — List all alert type configurations
* ``PUT  /alerts/{alert_type}``  — Toggle / update a specific alert type
* ``GET  /webhooks``             — List registered webhooks
* ``POST /webhooks``             — Register a new webhook
* ``DELETE /webhooks/{webhook_id}`` — Remove a webhook

Alert types supported
---------------------
arc_flash, short_circuit, scada_fault, load_flow,
protection_coordination, harmonic_analysis, motor_starting, system_alert

Storage
-------
In-memory module-level dict with sensible defaults.  Suitable for
single-process deployments; for multi-process / persistent storage,
replace the ``_store`` dict with a database-backed DAO.

Author: ETAP Integration Team
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    String,
    Text,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
from api.dependencies import (
    CurrentUser,
    get_api_key,
    get_current_user_from_header,
    get_optional_current_user_from_header,
)

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


logger = logging.getLogger("etap.api.notification_config")
audit_logger = logging.getLogger("audit")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ALERT_TYPES: set[str] = {
    "arc_flash",
    "short_circuit",
    "scada_fault",
    "load_flow",
    "protection_coordination",
    "harmonic_analysis",
    "motor_starting",
    "system_alert",
}

VALID_SEVERITY_THRESHOLDS: set[str] = {"info", "low", "medium", "high", "critical"}

VALID_PERIODS: set[str] = {"daily", "weekly"}

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/notifications/digest/config",
    tags=["notifications", "digest", "webhooks"],
    dependencies=[Depends(get_api_key)],
)

# ---------------------------------------------------------------------------
# In-memory store with defaults
# ---------------------------------------------------------------------------


def _default_alert_configs() -> Dict[str, Dict[str, Any]]:
    """Return default alert type configurations for every supported alert type."""
    return {
        "arc_flash": {"alert_type": "arc_flash", "enabled": True, "severity_threshold": "high"},
        "short_circuit": {
            "alert_type": "short_circuit",
            "enabled": True,
            "severity_threshold": "high",
        },
        "scada_fault": {
            "alert_type": "scada_fault",
            "enabled": True,
            "severity_threshold": "medium",
        },
        "load_flow": {"alert_type": "load_flow", "enabled": True, "severity_threshold": "medium"},
        "protection_coordination": {
            "alert_type": "protection_coordination",
            "enabled": True,
            "severity_threshold": "high",
        },
        "harmonic_analysis": {
            "alert_type": "harmonic_analysis",
            "enabled": False,
            "severity_threshold": "medium",
        },
        "motor_starting": {
            "alert_type": "motor_starting",
            "enabled": False,
            "severity_threshold": "medium",
        },
        "system_alert": {
            "alert_type": "system_alert",
            "enabled": True,
            "severity_threshold": "low",
        },
    }


def _default_store() -> Dict[str, Any]:
    """Return the initial in-memory configuration store."""
    return {
        "digest": {
            "period": "daily",
            "schedule_time": "08:00",
            "timezone": "UTC",
            "enabled": True,
        },
        "alerts": _default_alert_configs(),
        "webhooks": {},  # webhook_id -> webhook dict
    }


_store: Dict[str, Any] = _default_store()


# ---------------------------------------------------------------------------
# SQLAlchemy ORM Models (Fix 14: Persist to DB)
# ---------------------------------------------------------------------------


class NotificationConfig(Base):
    """Persisted notification configuration (digest schedule + alert preferences)."""

    __tablename__ = "notification_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default="default")
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    digest: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: _default_store()["digest"])
    alerts: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: _default_alert_configs())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class WebhookConfig(Base):
    """Persisted outbound webhook configuration with secret encrypted at rest."""

    __tablename__ = "webhook_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    owner_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    events: Mapped[list] = mapped_column(JSON, nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Fernet encrypted at rest
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Encryption and Audit Logging Helpers (Fix 14)
# ---------------------------------------------------------------------------


def _get_fernet_cipher() -> Any:
    """Retrieve Fernet cipher instance from LocalSecretsManager."""
    try:
        from security.secrets_manager import LocalSecretsManager

        return LocalSecretsManager()._cipher
    except Exception as exc:
        logger.warning("Could not initialize LocalSecretsManager cipher: %s", exc)
        return None


def _encrypt_secret(secret: str) -> str:
    """Encrypt secret at rest using Fernet."""
    if not secret:
        return ""
    cipher = _get_fernet_cipher()
    if cipher:
        try:
            return cipher.encrypt(secret.encode("utf-8")).decode("utf-8")
        except Exception as exc:
            logger.warning("Secret encryption failed: %s", exc)
    return secret


def _decrypt_secret(encrypted: str) -> str:
    """Decrypt stored secret with graceful fallback if plaintext."""
    if not encrypted:
        return ""
    cipher = _get_fernet_cipher()
    if cipher:
        try:
            return cipher.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except Exception:
            return encrypted
    return encrypted


def _log_config_change(
    action: str,
    target_id: Optional[str] = None,
    user: Optional[CurrentUser] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Emit audit logs for configuration and webhook modifications."""
    user_id = getattr(user, "user_id", None) or "system"
    tenant_id = getattr(user, "tenant_id", None)
    safe_action = _sanitize_for_log(action)
    safe_target = _sanitize_for_log(target_id)
    safe_user = _sanitize_for_log(user_id)

    audit_logger.info(
        "notification_config_changed action=%s target=%s user_id=%s details=%s",
        safe_action,
        safe_target,
        safe_user,
        _sanitize_for_log(details or {}),
    )

    try:
        from core.security_logging import SecurityAuditLogger

        sec_logger = SecurityAuditLogger()
        sec_logger.log_event(
            event_type="notification_config_change",
            action=action,
            target_id=target_id,
            user_id=user_id,
            tenant_id=tenant_id,
            details=details or {},
        )
    except Exception as exc:
        logger.debug("SecurityAuditLogger dispatch failed: %s", exc)


async def _sync_from_db(tenant_id: Optional[str] = None) -> None:
    """Load config and webhooks from DB into _store cache."""
    try:
        from api.database import async_session

        async with async_session() as db:
            cfg_id = tenant_id or "default"
            stmt = select(NotificationConfig).where(NotificationConfig.id == cfg_id)
            res = await db.execute(stmt)
            cfg = res.scalar_one_or_none()
            if cfg is not None:
                if cfg.digest:
                    _store["digest"].update(cfg.digest)
                if cfg.alerts:
                    _store["alerts"].update(cfg.alerts)

            wh_stmt = select(WebhookConfig)
            wh_res = await db.execute(wh_stmt)
            for wh in wh_res.scalars().all():
                _store["webhooks"][wh.id] = {
                    "id": wh.id,
                    "url": wh.url,
                    "events": wh.events,
                    "secret": _decrypt_secret(wh.secret or ""),
                    "enabled": wh.enabled,
                    "owner_id": wh.owner_id,
                    "created_at": wh.created_at.isoformat() if wh.created_at else datetime.now(UTC).isoformat(),
                }
    except Exception as exc:
        logger.debug("Database sync failed, continuing with in-memory store: %s", exc)


async def _save_config_to_db(tenant_id: Optional[str] = None) -> None:
    """Save current _store config to DB."""
    try:
        from api.database import async_session

        async with async_session() as db:
            cfg_id = tenant_id or "default"
            stmt = select(NotificationConfig).where(NotificationConfig.id == cfg_id)
            res = await db.execute(stmt)
            cfg = res.scalar_one_or_none()
            if cfg is None:
                cfg = NotificationConfig(
                    id=cfg_id,
                    tenant_id=tenant_id,
                    digest=_store["digest"].copy(),
                    alerts=_store["alerts"].copy(),
                )
                db.add(cfg)
            else:
                cfg.digest = _store["digest"].copy()
                cfg.alerts = _store["alerts"].copy()
                cfg.updated_at = datetime.now(UTC)
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist notification config to DB: %s", exc)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AlertTypeConfig(BaseModel):
    """Configuration for a single alert type.

    Attributes:
        alert_type: Identifier of the alert type (e.g. ``arc_flash``).
        enabled: Whether notifications are active for this alert type.
        severity_threshold: Minimum severity that triggers a notification.
    """

    alert_type: str = Field(..., description="Alert type identifier")
    enabled: bool = Field(default=True, description="Whether this alert type is enabled")
    severity_threshold: str = Field(
        default="medium",
        description="Minimum severity threshold (info|low|medium|high|critical)",
    )

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v: str) -> str:
        """Ensure the alert type is one of the supported values."""
        if v not in VALID_ALERT_TYPES:
            raise ValueError(
                f"Invalid alert_type '{v}'. Must be one of: {sorted(VALID_ALERT_TYPES)}"
            )
        return v

    @field_validator("severity_threshold")
    @classmethod
    def validate_severity_threshold(cls, v: str) -> str:
        """Ensure the severity threshold is valid."""
        if v not in VALID_SEVERITY_THRESHOLDS:
            raise ValueError(
                f"Invalid severity_threshold '{v}'. Must be one of: {sorted(VALID_SEVERITY_THRESHOLDS)}"
            )
        return v


class DigestScheduleConfig(BaseModel):
    """Digest schedule configuration.

    Attributes:
        period: Digest frequency — ``daily`` or ``weekly``.
        schedule_time: Time of day to send the digest (HH:MM, 24-hour format).
        timezone: IANA timezone string (e.g. ``UTC``, ``America/New_York``).
        enabled: Whether the digest schedule is active.
    """

    period: str = Field(default="daily", description="Digest period: daily or weekly")
    schedule_time: str = Field(
        default="08:00",
        pattern=r"^\d{2}:\d{2}$",
        description="Schedule time in HH:MM (24-hour) format",
    )
    timezone: str = Field(default="UTC", description="IANA timezone identifier")
    enabled: bool = Field(default=True, description="Whether the digest schedule is active")

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        """Ensure the period is one of the allowed values."""
        if v not in VALID_PERIODS:
            raise ValueError(f"Invalid period '{v}'. Must be one of: {sorted(VALID_PERIODS)}")
        return v


class WebhookConfigSchema(BaseModel):
    """Configuration schema for an outbound webhook.

    Attributes:
        url: The HTTPS endpoint that receives webhook payloads.
        events: List of event types that trigger this webhook.
        secret: Shared secret for HMAC signature verification.
        enabled: Whether the webhook is active.
    """

    url: str = Field(..., description="Webhook callback URL (HTTPS)")
    events: List[str] = Field(
        default_factory=list,
        description="List of event types that trigger this webhook",
    )
    secret: str = Field(default="", description="Shared secret for HMAC signature verification")
    enabled: bool = Field(default=True, description="Whether the webhook is active")


class WebhookCreateRequest(BaseModel):
    """Request body for creating a new webhook.

    Attributes:
        url: The HTTPS endpoint that receives webhook payloads.
        events: List of event types that trigger this webhook.
        secret: Optional shared secret for HMAC signature verification.
    """

    url: str = Field(..., description="Webhook callback URL (HTTPS)")
    events: List[str] = Field(
        ...,
        min_length=1,
        description="List of event types that trigger this webhook (at least one)",
    )
    secret: str = Field(default="", description="Shared secret for HMAC signature verification")


class WebhookResponse(BaseModel):
    """Response representation of a registered webhook.

    Attributes:
        id: Unique identifier for the webhook.
        url: The callback URL.
        events: Event types that trigger this webhook.
        enabled: Whether the webhook is active.
        created_at: ISO-8601 timestamp of when the webhook was created.
    """

    id: str
    url: str
    events: List[str]
    enabled: bool
    created_at: str


class NotificationConfigResponse(BaseModel):
    """Full notification configuration response.

    Attributes:
        digest: Current digest schedule configuration.
        alerts: List of all alert type configurations.
        webhooks: List of all registered webhooks.
    """

    digest: DigestScheduleConfig
    alerts: List[AlertTypeConfig]
    webhooks: List[WebhookResponse]


class NotificationConfigUpdateRequest(BaseModel):
    """Partial update request for notification configuration.

    All fields are optional — only provided fields will be updated.

    Attributes:
        digest: Updated digest schedule configuration.
        alerts: Updated list of alert type configurations.
    """

    digest: Optional[DigestScheduleConfig] = Field(
        default=None, description="Updated digest schedule configuration"
    )
    alerts: Optional[List[AlertTypeConfig]] = Field(
        default=None, description="Updated alert type configurations"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _webhook_to_response(wh: Dict[str, Any]) -> WebhookResponse:
    """Convert an internal webhook dict to a :class:`WebhookResponse`."""
    return WebhookResponse(
        id=wh["id"],
        url=wh["url"],
        events=wh["events"],
        enabled=wh["enabled"],
        created_at=wh["created_at"],
    )


def _current_config_response() -> NotificationConfigResponse:
    """Build the full notification configuration response from the in-memory store."""
    digest_cfg = DigestScheduleConfig(**_store["digest"])
    alert_cfgs = [AlertTypeConfig(**a) for a in _store["alerts"].values()]
    webhook_resps = [_webhook_to_response(wh) for wh in _store["webhooks"].values()]
    return NotificationConfigResponse(
        digest=digest_cfg,
        alerts=alert_cfgs,
        webhooks=webhook_resps,
    )


# ---------------------------------------------------------------------------
# Endpoints — Root configuration
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=NotificationConfigResponse,
    summary="Retrieve current notification configuration",
)
async def get_notification_config() -> NotificationConfigResponse:
    """Return the full notification configuration including digest schedule,
    alert type settings, and registered webhooks."""
    await _sync_from_db()
    return _current_config_response()


@router.put(
    "/",
    response_model=NotificationConfigResponse,
    summary="Update notification configuration (partial update)",
)
async def update_notification_config(
    body: NotificationConfigUpdateRequest,
    user: Optional[CurrentUser] = Depends(get_optional_current_user_from_header),
) -> NotificationConfigResponse:
    """Partially update the notification configuration.

    Only fields that are provided in the request body will be updated;
    omitted fields remain unchanged.
    """
    await _sync_from_db()
    if body.digest is not None:
        _store["digest"].update(body.digest.model_dump())
        logger.info("digest_config_updated new_config=%s", body.digest.model_dump())
        logger.info(
            "digest_config_updated new_config=%s", _sanitize_for_log(body.digest.model_dump())
        )

    if body.alerts is not None:
        for alert_cfg in body.alerts:
            _store["alerts"][alert_cfg.alert_type] = alert_cfg.model_dump()
        logger.info("alerts_config_updated count=%d", len(body.alerts))

    await _save_config_to_db()
    _log_config_change(
        action="update_notification_config",
        user=user,
        details={
            "has_digest": body.digest is not None,
            "alerts_count": len(body.alerts) if body.alerts else 0,
        },
    )

    return _current_config_response()


# ---------------------------------------------------------------------------
# Endpoints — Digest schedule
# ---------------------------------------------------------------------------


@router.get(
    "/digest",
    response_model=DigestScheduleConfig,
    summary="Get digest schedule configuration",
)
async def get_digest_config() -> DigestScheduleConfig:
    """Return the current digest schedule configuration."""
    await _sync_from_db()
    return DigestScheduleConfig(**_store["digest"])


@router.put(
    "/digest",
    response_model=DigestScheduleConfig,
    summary="Update digest schedule",
)
async def update_digest_config(
    body: DigestScheduleConfig,
    user: Optional[CurrentUser] = Depends(get_optional_current_user_from_header),
) -> DigestScheduleConfig:
    """Update the digest schedule configuration.

    All fields of the digest schedule are replaced with the provided values.
    """
    await _sync_from_db()
    _store["digest"].update(body.model_dump())
    logger.info("digest_schedule_updated config=%s", body.model_dump())
    await _save_config_to_db()
    _log_config_change(
        action="update_digest_config",
        user=user,
        details={"config": body.model_dump()},
    )
    return DigestScheduleConfig(**_store["digest"])


# ---------------------------------------------------------------------------
# Endpoints — Alert types
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=List[AlertTypeConfig],
    summary="List all alert type configurations",
)
async def list_alert_configs() -> List[AlertTypeConfig]:
    """Return the configuration for every supported alert type."""
    await _sync_from_db()
    return [AlertTypeConfig(**a) for a in _store["alerts"].values()]


@router.put(
    "/alerts/{alert_type}",
    response_model=AlertTypeConfig,
    summary="Toggle / update a specific alert type",
)
async def update_alert_config(
    alert_type: str,
    body: AlertTypeConfig,
    user: Optional[CurrentUser] = Depends(get_optional_current_user_from_header),
) -> AlertTypeConfig:
    """Update the configuration for a specific alert type.

    The ``alert_type`` path parameter must match the ``alert_type`` field
    in the request body and must be one of the supported alert types.
    """
    if alert_type not in VALID_ALERT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown alert type '{alert_type}'. Valid types: {sorted(VALID_ALERT_TYPES)}",
        )

    if body.alert_type != alert_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path alert_type '{alert_type}' does not match body alert_type '{body.alert_type}'",
        )

    await _sync_from_db()
    _store["alerts"][alert_type] = body.model_dump()
    logger.info("alert_config_updated alert_type=%s config=%s", alert_type, body.model_dump())
    logger.info(
        "alert_config_updated alert_type=%s config=%s",
        _sanitize_for_log(alert_type),
        _sanitize_for_log(body.model_dump()),
    )
    await _save_config_to_db()
    _log_config_change(
        action="update_alert_config",
        target_id=alert_type,
        user=user,
        details={"alert_type": alert_type, "config": body.model_dump()},
    )
    return AlertTypeConfig(**_store["alerts"][alert_type])


# ---------------------------------------------------------------------------
# Endpoints — Webhooks
# ---------------------------------------------------------------------------


@router.get(
    "/webhooks",
    response_model=List[WebhookResponse],
    summary="List registered webhooks",
)
async def list_webhooks(
    user: Optional[CurrentUser] = Depends(get_optional_current_user_from_header),
) -> List[WebhookResponse]:
    """Return all registered webhooks scoped to the current user (or all if admin)."""
    await _sync_from_db()
    user_id = str(getattr(user, "user_id", "")).strip() if user else None
    role = getattr(user, "role", "") if user else ""

    if role == "admin":
        return [_webhook_to_response(wh) for wh in _store["webhooks"].values()]
    if user_id:
        return [
            _webhook_to_response(wh)
            for wh in _store["webhooks"].values()
            if wh.get("owner_id") == user_id or wh.get("owner_id") is None
        ]
    return [
        _webhook_to_response(wh) for wh in _store["webhooks"].values() if not wh.get("owner_id")
    ]


@router.post(
    "/webhooks",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new webhook",
)
async def create_webhook(
    body: WebhookCreateRequest,
    user: Optional[CurrentUser] = Depends(get_optional_current_user_from_header),
) -> WebhookResponse:
    """Register a new webhook endpoint.

    The webhook will receive POST requests for the specified event types
    whenever they occur in the system.  The optional ``secret`` is encrypted
    at rest and used to compute an ``X-Webhook-Signature`` header (HMAC-SHA256)
    on each delivery so the receiver can verify authenticity.
    """
    # SSRF protection: validate URL against private / internal targets
    from api.email_webhooks import _SSRFBlockedError, _validate_webhook_url

    try:
        _validate_webhook_url(str(body.url))
    except _SSRFBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook URL: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook URL validation failed: {exc}",
        ) from exc

    webhook_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    user_id = str(getattr(user, "user_id", "")).strip() if user else None
    tenant_id = getattr(user, "tenant_id", None) if user else None

    # Encrypt secret at rest (Fix 14)
    encrypted_secret = _encrypt_secret(body.secret) if body.secret else ""

    webhook_data = {
        "id": webhook_id,
        "url": body.url,
        "events": body.events,
        "secret": body.secret,
        "enabled": True,
        "owner_id": user_id,
        "created_at": now,
    }

    # Persist to database (Fix 14)
    try:
        from api.database import async_session

        async with async_session() as db:
            wh_obj = WebhookConfig(
                id=webhook_id,
                tenant_id=tenant_id,
                owner_id=user_id,
                url=body.url,
                events=body.events,
                secret=encrypted_secret,
                enabled=True,
                created_at=datetime.now(UTC),
            )
            db.add(wh_obj)
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist webhook to DB: %s", exc)

    _store["webhooks"][webhook_id] = webhook_data
    logger.info(
        "webhook_created id=%s url=%s events=%s owner_id=%s",
        webhook_id,
        body.url,
        body.events,
        user_id,
    )
    _log_config_change(
        action="create_webhook",
        target_id=webhook_id,
        user=user,
        details={"url": body.url, "events": body.events, "owner_id": user_id},
    )
    return _webhook_to_response(webhook_data)


@router.delete(
    "/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    summary="Remove a webhook",
)
async def delete_webhook(
    webhook_id: str,
    user: CurrentUser = Depends(get_current_user_from_header),
) -> None:
    """Remove a registered webhook by its ID.

    Returns 204 on success, 404 if the webhook does not exist, 403 if unauthorized.
    Requires an authenticated user JWT (API-key-only callers are rejected with 401).
    """
    await _sync_from_db()
    if webhook_id not in _store["webhooks"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook '{webhook_id}' not found",
        )

    wh = _store["webhooks"][webhook_id]
    user_id = str(user.user_id).strip()
    role = getattr(user, "role", "")

    if role != "admin":
        owner_id = wh.get("owner_id")
        if not owner_id or owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete another user's webhook",
            )

    # Delete from database (Fix 14)
    try:
        from api.database import async_session

        async with async_session() as db:
            stmt = select(WebhookConfig).where(WebhookConfig.id == webhook_id)
            res = await db.execute(stmt)
            wh_obj = res.scalar_one_or_none()
            if wh_obj is not None:
                await db.delete(wh_obj)
                await db.commit()
    except Exception as exc:
        logger.warning("Failed to delete webhook from DB: %s", exc)

    del _store["webhooks"][webhook_id]
    logger.info("webhook_deleted id=%s", webhook_id)
    _log_config_change(
        action="delete_webhook",
        target_id=webhook_id,
        user=user,
        details={"webhook_id": webhook_id},
    )


__all__ = ["NotificationConfig", "WebhookConfig", "router"]

