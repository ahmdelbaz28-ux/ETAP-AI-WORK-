"""services/task_ownership.py — Authoritative Async Task Ownership and Access Enforcement (P0-3).

Enforces:
1. Cryptographic/trusted binding between Celery task_id, caller user_id, tenant_id, and user_role.
2. Tenant isolation: cross-tenant task inspection fails with non-disclosing 404 Not Found.
3. Role enforcement: only task owner or admin can inspect task status/results.
4. Fail-closed: missing task ownership metadata rejects access immediately.
5. Durable storage: Redis with thread-safe in-memory fallback.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("engineering_service.task_ownership")

_OWNERSHIP_LOCK = threading.Lock()
_IN_MEMORY_TASK_OWNERSHIP: Dict[str, Dict[str, Any]] = {}
_REDIS_CLIENT = None
_REDIS_INITIALIZED = False


def _get_redis():
    global _REDIS_CLIENT, _REDIS_INITIALIZED
    if not _REDIS_INITIALIZED:
        _REDIS_INITIALIZED = True
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis

                _REDIS_CLIENT = redis.Redis.from_url(redis_url, decode_responses=True)
                _REDIS_CLIENT.ping()
                logger.info("Task ownership connected to Redis at %s", redis_url)
            except Exception as e:
                logger.warning("Redis unavailable for task ownership; using in-memory store: %s", e)
                _REDIS_CLIENT = None
    return _REDIS_CLIENT


class TaskOwnershipError(Exception):
    """Base exception for task ownership errors."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TaskTenantMismatchError(TaskOwnershipError):
    """Raised when caller tenant does not match task owner tenant (non-disclosing 404)."""
    pass


class TaskAccessForbiddenError(TaskOwnershipError):
    """Raised when caller is not the owner or an admin within the same tenant (403 Forbidden)."""
    pass


def record_task_ownership(
    task_id: str,
    user_id: str,
    tenant_id: str,
    user_role: str = "engineer",
    study_type: str = "unknown",
    metadata: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = 604800,  # 7 days
) -> Dict[str, Any]:
    """Durably record task ownership at the time of async enqueue."""
    record = {
        "task_id": str(task_id).strip(),
        "user_id": str(user_id).strip(),
        "tenant_id": str(tenant_id).strip(),
        "user_role": str(user_role).strip(),
        "study_type": str(study_type).strip(),
        "created_at": time.time(),
        "metadata": metadata or {},
    }

    # 1. Thread-safe in-memory store
    with _OWNERSHIP_LOCK:
        _IN_MEMORY_TASK_OWNERSHIP[task_id] = record

    # 2. Redis store if configured
    r = _get_redis()
    if r is not None:
        try:
            r.setex(f"etap:task_owner:{task_id}", ttl_seconds, json.dumps(record))
        except Exception as e:
            logger.error("Failed to write task ownership to Redis: %s", e)

    return record


def get_task_ownership(task_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve task ownership record durably."""
    # Check in-memory store first
    with _OWNERSHIP_LOCK:
        if task_id in _IN_MEMORY_TASK_OWNERSHIP:
            return dict(_IN_MEMORY_TASK_OWNERSHIP[task_id])

    # Check Redis
    r = _get_redis()
    if r is not None:
        try:
            data = r.get(f"etap:task_owner:{task_id}")
            if data:
                parsed = json.loads(data)
                with _OWNERSHIP_LOCK:
                    _IN_MEMORY_TASK_OWNERSHIP[task_id] = parsed
                return parsed
        except Exception as e:
            logger.error("Failed to read task ownership from Redis: %s", e)

    return None


def verify_task_access(
    task_id: str,
    caller_user_id: str,
    caller_tenant_id: str,
    caller_role: str = "engineer",
) -> Dict[str, Any]:
    """Verify caller is authorized to view or access this task.

    Rules:
    1. If no ownership record exists -> fail closed (TaskOwnershipError).
    2. If caller tenant != task owner tenant -> TaskTenantMismatchError (caller sees 404).
    3. If caller user != task owner user and caller role != 'admin' -> TaskAccessForbiddenError (403).
    4. Otherwise authorized -> returns ownership record.
    """
    ownership = get_task_ownership(task_id)
    if not ownership:
        raise TaskOwnershipError("TASK_OWNERSHIP_MISSING", f"Ownership record missing for task '{task_id}'")

    task_tenant = str(ownership.get("tenant_id", "")).strip()
    task_user = str(ownership.get("user_id", "")).strip()

    # Cross-tenant isolation: non-disclosing rejection
    if str(caller_tenant_id).strip() != task_tenant:
        raise TaskTenantMismatchError("TASK_NOT_FOUND", f"Task '{task_id}' not found")

    # Same tenant: enforce owner or admin
    c_role = str(caller_role).lower().strip()
    c_user = str(caller_user_id).strip()
    if c_role != "admin" and c_user != task_user:
        raise TaskAccessForbiddenError(
            "FORBIDDEN",
            f"User '{caller_user_id}' does not have permission to view task '{task_id}' owned by '{task_user}'",
        )

    return ownership
