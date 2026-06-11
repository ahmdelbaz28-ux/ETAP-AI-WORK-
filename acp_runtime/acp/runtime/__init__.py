"""acp.runtime — the async execution engine for ACP.

Public surface:
    AcpRuntime            — main engine
    capability            — decorator for marking methods as capabilities
    AcpHandler            — Protocol (runtime-checkable)
    discover_capabilities — walk an object, find all @capability methods
    list_capabilities     — same, in public manifest form
    enforce_deadline_ms   — wrap a coroutine with a hard timeout
    deadline_scope        — lower-level: yield a cancel scope with deadline
    cancellable           — async ctx mgr wrapping a cancel scope
    ProgressEmitter       — emit progress notifications during a handler
    ProgressEvent         — value type for progress events
"""
from __future__ import annotations

from acp.runtime.handler import (
    AcpHandler,
    capability,
    discover_capabilities,
    list_capabilities,
    CapabilityMeta,
)
from acp.runtime.deadline import enforce_deadline_ms, deadline_scope
from acp.runtime.cancel import cancellable, is_cancelled_exception
from acp.runtime.engine import AcpRuntime
from acp.runtime.progress import ProgressEmitter, ProgressEvent

__all__ = [
    "AcpRuntime",
    "capability",
    "AcpHandler",
    "discover_capabilities",
    "list_capabilities",
    "CapabilityMeta",
    "enforce_deadline_ms",
    "deadline_scope",
    "cancellable",
    "is_cancelled_exception",
    "ProgressEmitter",
    "ProgressEvent",
]
