"""
api/session_redis.py — Redis-backed Distributed Session Management (FIX-22).

Provides:
- RedisSessionStore: Distributed session CRUD backed by Redis hashes with TTL.
- SessionMiddleware: ASGI middleware for session cookie / header management.
- Multi-replica state preservation across restarts and horizontal scaling.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from api.redis_client import get_redis

logger = logging.getLogger("api.session_redis")

_SESSION_PREFIX = "etap:session:"
_DEFAULT_SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "86400"))  # 24 hours
_SESSION_COOKIE_NAME = "etap_session_id"
_SESSION_HEADER_NAME = "X-Session-ID"


class RedisSessionStore:
    """Distributed session store leveraging Redis hashes with explicit TTLs.

    Ensures that sessions survive replica restarts and are accessible across
    all horizontally scaled instances.
    """

    def __init__(self, ttl_seconds: int = _DEFAULT_SESSION_TTL) -> None:
        self.default_ttl = ttl_seconds

    async def create_session(
        self,
        user_id: str,
        initial_data: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Create a new session in Redis and return the unique session ID."""
        session_id = secrets.token_urlsafe(32)
        key = f"{_SESSION_PREFIX}{session_id}"
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        session_payload = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "data": json.dumps(initial_data or {}),
        }

        client = await get_redis()
        if client is not None:
            try:
                await client.hset(key, mapping=session_payload)
                await client.expire(key, ttl)
                logger.debug("Created Redis session: %s (user: %s)", session_id[:8], user_id)
                return session_id
            except Exception as exc:
                logger.error("Failed to persist session to Redis: %s", exc)
                raise RuntimeError(f"Session creation failed: {exc}") from exc

        # Fail closed in production if Redis is unavailable
        raise RuntimeError("Redis is required for shared distributed sessions (FIX-22)")

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve active session data by ID. Returns None if expired or not found."""
        if not session_id:
            return None

        key = f"{_SESSION_PREFIX}{session_id}"
        client = await get_redis()
        if client is None:
            return None

        try:
            raw = await client.hgetall(key)
            if not raw:
                return None

            data_str = raw.get("data", "{}")
            try:
                parsed_data = json.loads(data_str)
            except Exception:
                parsed_data = {}

            return {
                "session_id": raw.get("session_id", session_id),
                "user_id": raw.get("user_id", ""),
                "created_at": float(raw.get("created_at", 0)),
                "updated_at": float(raw.get("updated_at", 0)),
                "data": parsed_data,
            }
        except Exception as exc:
            logger.debug("Failed to fetch session from Redis: %s", exc)
            return None

    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Update session data payload and reset TTL."""
        if not session_id:
            return False

        key = f"{_SESSION_PREFIX}{session_id}"
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        client = await get_redis()
        if client is None:
            return False

        try:
            exists = await client.exists(key)
            if not exists:
                return False

            updates = {
                "data": json.dumps(data),
                "updated_at": time.time(),
            }
            await client.hset(key, mapping=updates)
            await client.expire(key, ttl)
            return True
        except Exception as exc:
            logger.error("Failed to update session in Redis: %s", exc)
            return False

    async def delete_session(self, session_id: str) -> bool:
        """Explicitly invalidate and delete a session."""
        if not session_id:
            return False

        key = f"{_SESSION_PREFIX}{session_id}"
        client = await get_redis()
        if client is None:
            return False

        try:
            deleted = await client.delete(key)
            return bool(deleted)
        except Exception as exc:
            logger.error("Failed to delete session from Redis: %s", exc)
            return False

    async def refresh_session(self, session_id: str, ttl_seconds: Optional[int] = None) -> bool:
        """Extend expiration TTL for active session."""
        if not session_id:
            return False

        key = f"{_SESSION_PREFIX}{session_id}"
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        client = await get_redis()
        if client is None:
            return False

        try:
            return bool(await client.expire(key, ttl))
        except Exception as exc:
            logger.debug("Failed to refresh session TTL: %s", exc)
            return False


class SessionMiddleware:
    """Pure ASGI middleware that attaches active Redis-backed session to request.state."""

    def __init__(self, app: ASGIApp, store: Optional[RedisSessionStore] = None) -> None:
        self.app = app
        self.store = store or RedisSessionStore()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        session_id = request.cookies.get(_SESSION_COOKIE_NAME) or request.headers.get(
            _SESSION_HEADER_NAME
        )

        session_obj: Optional[Dict[str, Any]] = None
        if session_id:
            session_obj = await self.store.get_session(session_id)

        scope["state"] = scope.get("state", {})
        scope["state"]["session"] = session_obj
        scope["state"]["session_id"] = session_id if session_obj else None

        await self.app(scope, receive, send)
