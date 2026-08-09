"""Scope validation — capability-based authorization.

A capability declares zero or more required scopes. A caller declares
the scopes they possess (typically via an auth token or session). The
router checks whether the caller is permitted to invoke the capability.

Rules:
    * No required scopes → always permitted (public capability)
    * Required scopes exist → caller must hold at least one
    * Scope strings are validated against the same regex as capability names
"""

from __future__ import annotations

from acp.schema.capability import is_valid_scope

__all__ = ["ScopeValidator", "check_scope"]


class ScopeValidator:
    """Holds the caller's scopes and answers permission queries.

    Parameters:
        scopes: set of scope strings the caller possesses. Empty set means
            the caller has no scopes.
    """

    def __init__(self, scopes: set[str] | None = None) -> None:
        self._scopes = set(scopes or ())
        for s in self._scopes:
            if not is_valid_scope(s):
                raise ValueError(f"Invalid scope in caller set: {s!r}")

    def is_permitted(self, required: tuple[str, ...]) -> bool:
        """Return True if the caller may invoke a capability with ``required`` scopes.

        * If ``required`` is empty, the capability is public → always True.
        * Otherwise, the caller must hold at least one required scope.
        """
        if not required:
            return True
        return bool(self._scopes & set(required))

    def __repr__(self) -> str:
        return f"ScopeValidator(scopes={sorted(self._scopes)!r})"


def check_scope(caller_scopes: set[str], required: tuple[str, ...]) -> bool:
    """Functional equivalent of ``ScopeValidator.is_permitted``.

    Validates every string in ``caller_scopes`` before checking.
    """
    for s in caller_scopes:
        if not is_valid_scope(s):
            raise ValueError(f"Invalid scope in caller set: {s!r}")
    if not required:
        return True
    return bool(caller_scopes & set(required))
