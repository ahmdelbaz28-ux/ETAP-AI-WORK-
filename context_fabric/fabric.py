"""
context_fabric/fabric.py — ContextFabric core types (M4.1).

Fail-closed invariants:
- ``query()`` refuses to run without a non-empty ``tenant_id``
  (``ContextIsolationError``) — tenant isolation is a precondition, not a
  best-effort filter.
- Every ``ContextEvidence`` must carry ``source_type`` + ``content_hash`` +
  ``tenant_id``; the constructor computes the hash and rejects empty
  identity fields (``ContextEvidenceError``).
- A missing/failing provider yields an explicit ``available=False`` result
  with a machine-readable reason — no synthetic content is ever produced.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger("context_fabric")


class ContextType(str, Enum):
    """The six canonical context types (M4.1)."""

    ENGINEERING_KNOWLEDGE = "engineering_knowledge"
    ENGINEERING_HISTORY = "engineering_history"
    PROJECT_STATE = "project_state"
    CODE_CONTEXT = "code_context"
    STANDARDS = "standards"
    USER_CONTEXT = "user_context"


class ContextEvidenceError(ValueError):
    """Raised when evidence items are missing mandatory provenance fields."""


class ContextIsolationError(ValueError):
    """Raised when a context query is attempted without a tenant scope."""


def _content_hash(value: Any) -> str:
    """Deterministic sha256 over a JSON-canonical form of ``value``."""
    canonical = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContextEvidence:
    """One evidence item with mandatory provenance (M4.1 gate).

    Attributes
    ----------
    source_type
        The ``ContextType`` this evidence originated from.
    content_hash
        sha256 of the canonicalised ``value`` — computed at construction.
    tenant_id
        Owning tenant; empty values are rejected.
    key
        Short machine key (e.g. ``code_chunk:42``).
    value
        The evidence payload (string, dict, ...).
    source_ref
        Human-readable origin descriptor (file path, store, provider id).
    """

    source_type: ContextType
    content_hash: str
    tenant_id: str
    key: str
    value: Any
    source_ref: str = ""

    @classmethod
    def build(
        cls,
        context_type: ContextType,
        key: str,
        value: Any,
        tenant_id: str,
        source_ref: str = "",
    ) -> ContextEvidence:
        """Construct evidence, computing the hash and enforcing identity fields."""
        if not tenant_id or not str(tenant_id).strip():
            raise ContextIsolationError(
                "ContextEvidence requires a non-empty tenant_id (fail-closed)."
            )
        if not key or not str(key).strip():
            raise ContextEvidenceError("ContextEvidence requires a non-empty key.")
        if value is None:
            raise ContextEvidenceError("ContextEvidence requires a non-None value.")
        return cls(
            source_type=context_type,
            content_hash=_content_hash(value),
            tenant_id=str(tenant_id),
            key=str(key),
            value=value,
            source_ref=source_ref,
        )


@runtime_checkable
class ContextProvider(Protocol):
    """Provider protocol for one context type."""

    provider_id: str

    def retrieve(self, query: str, tenant_id: str, limit: int) -> list[dict]:
        """Return raw items as ``{"key", "value", "source_ref"}`` dicts."""
        ...  # pragma: no cover - protocol definition



@dataclass
class ContextQueryResult:
    """Result envelope for a ContextFabric query."""

    context_type: ContextType
    available: bool
    evidence: list[ContextEvidence] = field(default_factory=list)
    reason: str = ""

    @property
    def hashes(self) -> list[str]:
        return [e.content_hash for e in self.evidence]


class ContextFabric:
    """Aggregates context providers behind one tenant-safe, evidence-first API."""

    def __init__(self, providers: dict[ContextType, ContextProvider] | None = None) -> None:
        self._providers: dict[ContextType, ContextProvider] = {}
        for ctype, provider in (providers or {}).items():
            self.register_provider(ctype, provider)

    def register_provider(self, context_type: ContextType, provider: ContextProvider) -> None:
        """Register (or replace) the provider for a context type."""
        self._providers[context_type] = provider
        logger.debug(
            "ContextFabric provider registered: %s -> %s",
            context_type.value,
            provider.provider_id,
        )

    def registered_types(self) -> list[str]:
        return sorted(ct.value for ct in self._providers)

    def query(
        self,
        context_type: ContextType,
        query: str,
        tenant_id: str,
        limit: int = 5,
    ) -> ContextQueryResult:
        """Query one context type; every returned item carries mandatory provenance."""
        if not tenant_id or not str(tenant_id).strip():
            raise ContextIsolationError(
                "ContextFabric.query requires a non-empty tenant_id (fail-closed)."
            )
        provider = self._providers.get(context_type)
        if provider is None:
            return ContextQueryResult(
                context_type=context_type,
                available=False,
                evidence=[],
                reason="no_provider_registered",
            )
        try:
            raw_items = provider.retrieve(str(query), str(tenant_id), int(limit))
        except Exception as exc:  # noqa: BLE001 - fail closed, never fabricate
            logger.warning("Context provider '%s' failed: %s", provider.provider_id, exc)
            return ContextQueryResult(
                context_type=context_type,
                available=False,
                evidence=[],
                reason=f"provider_error:{type(exc).__name__}",
            )

        evidence: list[ContextEvidence] = []
        for item in raw_items or []:
            if not isinstance(item, dict) or "value" not in item:
                continue  # malformed provider output is skipped, never guessed
            evidence.append(
                ContextEvidence.build(
                    context_type=context_type,
                    key=str(item.get("key", f"{provider.provider_id}:item")),
                    value=item["value"],
                    tenant_id=str(tenant_id),
                    source_ref=str(item.get("source_ref", provider.provider_id)),
                )
            )
        return ContextQueryResult(
            context_type=context_type,
            available=True,
            evidence=evidence,
            reason="ok" if evidence else "no_matches",
        )
