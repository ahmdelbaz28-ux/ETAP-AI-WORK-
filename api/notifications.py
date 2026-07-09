"""
api/notifications.py — Real-time Notifications System.

Provides:
- Notification model with types (study_complete, system_alert, etc.)
- WebSocket endpoint for real-time delivery
- Email integration for critical notifications
- Push notification support (optional)
- CRUD endpoints for managing notifications

Exposes endpoints under the ``/api/v1/notifications`` prefix:
* ``GET  /``                — List notifications (paginated)
* ``GET  /unread``          — Get unread count
* ``PUT  /{id}/read``       — Mark as read
* ``PUT  /read-all``        — Mark all as read
* ``POST /test``            — Send test notification (for debugging)
* WebSocket ``/ws/notifications`` — Real-time notification stream
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, Optional

UTC = UTC

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    String,
    Text,
    and_,
    desc,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
from api.dependencies import (
    CurrentUser,
    PaginationParams,
    get_current_user_from_header,
    pagination_params,
)
from api.rbac import require_permission

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

DbDep = Any


# ---------------------------------------------------------------------------
# Notification Types
# ---------------------------------------------------------------------------


class NotificationType(str, Enum):
    """Supported notification types."""
    STUDY_COMPLETED = "study_completed"
    STUDY_FAILED = "study_failed"
    STUDY_STARTED = "study_started"
    SYSTEM_ALERT = "system_alert"
    SYSTEM_HEALTH = "system_health"
    USER_ACTION = "user_action"
    BATCH_COMPLETED = "batch_completed"
    IMPORT_COMPLETED = "import_completed"
    EXPORT_COMPLETED = "export_completed"
    EQUIPMENT_CHANGE = "equipment_change"
    ROLE_CHANGE = "role_change"
    PASSWORD_CHANGE = "password_change"
    LOGIN_ALERT = "login_alert"
    ERROR_ALERT = "error_alert"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------


class Notification(Base):
    """Persisted notification."""

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default=NotificationPriority.NORMAL.value)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Additional payload
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_email: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------


class NotificationResponse(BaseModel):
    """Public notification representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    notification_type: str
    title: str
    message: str
    priority: str = "normal"
    data: Optional[dict[str, Any]] = None
    is_read: bool = False
    is_archived: bool = False
    created_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    """Paginated notification list response."""

    model_config = ConfigDict(from_attributes=True)

    notifications: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    """Unread notification count response."""

    unread_count: int


class TestNotificationRequest(BaseModel):
    """Payload for sending a test notification."""

    model_config = ConfigDict(strict=False)

    title: str = Field(default="Test Notification", max_length=255)
    message: str = Field(default="This is a test notification", max_length=2000)
    notification_type: NotificationType = NotificationType.SYSTEM_ALERT
    priority: NotificationPriority = NotificationPriority.NORMAL


# ---------------------------------------------------------------------------
# WebSocket Manager
# ---------------------------------------------------------------------------


class NotificationManager:
    """Manages WebSocket connections for real-time notifications."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}  # user_id -> [websockets]

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def send_notification(self, user_id: str, notification: dict[str, Any]) -> None:
        """Send a notification to all connections for a user."""
        if user_id not in self._connections:
            return
        dead_connections = []
        for websocket in self._connections[user_id]:
            try:
                await websocket.send_json(notification)
            except Exception:
                dead_connections.append(websocket)

        # Clean up dead connections
        for ws in dead_connections:
            await self.disconnect(user_id, ws)

    async def broadcast(self, notification: dict[str, Any]) -> None:
        """Broadcast a notification to all connected users."""
        for user_id in list(self._connections.keys()):
            await self.send_notification(user_id, notification)


# Global notification manager instance
notification_manager = NotificationManager()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


async def create_notification(
    db: AsyncSession,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    priority: str = NotificationPriority.NORMAL.value,
    data: Optional[dict[str, Any]] = None,
    requires_email: bool = False,
) -> Notification:
    """Create a notification and send it via WebSocket if connected."""
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        data=data,
        requires_email=requires_email,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)

    # Send via WebSocket if user is connected
    notification_data = {
        "type": "notification",
        "id": str(notification.id),
        "notification_type": notification.notification_type,
        "title": notification.title,
        "message": notification.message,
        "priority": notification.priority,
        "data": notification.data,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }
    await notification_manager.send_notification(user_id, notification_data)

    return notification


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=NotificationListResponse,
    summary="List notifications (paginated)",
)
async def list_notifications(
    db: DbDep,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
    pagination: PaginationParams = Depends(pagination_params),  # noqa: B008
    unread_only: bool = Query(False, description="Only show unread notifications"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
) -> Any:
    """Return a paginated list of notifications for the current user."""
    # Build filters
    filters = [Notification.user_id == user.user_id]

    if unread_only:
        filters.append(Notification.is_read == False)

    if notification_type:
        filters.append(Notification.notification_type == notification_type)

    where_clause = and_(*filters)

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(Notification).where(where_clause)
    )
    total = count_result.scalar_one()

    # Unread count
    unread_result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.user_id,
            Notification.is_read == False,
        )
    )
    unread_count = unread_result.scalar_one()

    # Paginated query
    result = await db.execute(
        select(Notification)
        .where(where_clause)
        .order_by(desc(Notification.created_at))
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    notifications = result.scalars().all()

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=str(n.id),
                user_id=str(n.user_id),
                notification_type=n.notification_type,
                title=n.title,
                message=n.message,
                priority=n.priority,
                data=n.data,
                is_read=n.is_read,
                is_archived=n.is_archived,
                created_at=n.created_at,
                read_at=n.read_at,
            )
            for n in notifications
        ],
        total=total,
        unread_count=unread_count,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/unread",
    response_model=UnreadCountResponse,
    summary="Get unread notification count",
)
async def get_unread_count(
    db: DbDep,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> Any:
    """Return the count of unread notifications."""
    result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.user_id,
            Notification.is_read == False,
        )
    )
    count = result.scalar_one()
    return UnreadCountResponse(unread_count=count)


@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark notification as read",
)
async def mark_as_read(
    notification_id: str,
    db: DbDep,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> Any:
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.user_id,
        )
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.is_read = True
    notification.read_at = datetime.now(UTC)
    db.add(notification)
    await db.flush()
    await db.refresh(notification)

    return NotificationResponse(
        id=str(notification.id),
        user_id=str(notification.user_id),
        notification_type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        priority=notification.priority,
        data=notification.data,
        is_read=notification.is_read,
        is_archived=notification.is_archived,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


@router.put(
    "/read-all",
    response_model=Dict[str, Any],
    summary="Mark all notifications as read",
)
async def mark_all_as_read(
    db: DbDep,
    user: CurrentUser = Depends(get_current_user_from_header),  # noqa: B008
) -> Any:
    """Mark all notifications as read for the current user."""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user.user_id,
            Notification.is_read == False,
        )
    )
    notifications = result.scalars().all()
    now = datetime.now(UTC)

    for notification in notifications:
        notification.is_read = True
        notification.read_at = now
        db.add(notification)

    await db.flush()

    return {
        "message": f"Marked {len(notifications)} notifications as read",
        "updated_count": len(notifications),
    }


@router.post(
    "/test",
    response_model=NotificationResponse,
    summary="Send a test notification",
)
async def send_test_notification(
    body: TestNotificationRequest,
    db: DbDep,
    user: CurrentUser = Depends(require_permission("notifications", "create")),  # noqa: B008
) -> Any:
    """Send a test notification to the current user."""
    notification = await create_notification(
        db=db,
        user_id=user.user_id,
        notification_type=body.notification_type.value,
        title=body.title,
        message=body.message,
        priority=body.priority.value,
    )

    return NotificationResponse(
        id=str(notification.id),
        user_id=str(notification.user_id),
        notification_type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        priority=notification.priority,
        data=notification.data,
        is_read=notification.is_read,
        is_archived=notification.is_archived,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


# ---------------------------------------------------------------------------
# WebSocket Endpoint (registered in routes.py)
# ---------------------------------------------------------------------------


async def notification_websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession,
    user: CurrentUser,
) -> None:
    """WebSocket endpoint for real-time notifications.

    Connected users receive notifications as JSON messages:
    {
        "type": "notification",
        "id": "...",
        "notification_type": "study_completed",
        "title": "...",
        "message": "...",
        "priority": "normal",
        "data": {...},
        "created_at": "..."
    }
    """
    await notification_manager.connect(user.user_id, websocket)
    try:
        while True:
            # Keep connection alive by waiting for messages
            # (client can send ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await notification_manager.disconnect(user.user_id, websocket)
    except Exception:
        await notification_manager.disconnect(user.user_id, websocket)
