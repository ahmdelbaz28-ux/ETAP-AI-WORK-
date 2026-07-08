"""Authentication — token validation and caller identity.

The ACP security layer is intentionally lightweight and pluggable. It
ships with a simple HMAC-based bearer-token validator, but any callable
that conforms to ``AuthValidator`` can be plugged in.

Design decisions:
    * No external crypto libraries required (uses stdlib ``hmac``, ``hashlib``).
    * Tokens are URL-safe base64-encoded strings: ``<payload>.<sig>``.
    * Payload is JSON-encoded, base64url-encoded.
    * Signature is HMAC-SHA256 over the payload.
    * Expiry is checked via an ``exp`` timestamp (Unix epoch seconds).
    * The validated token yields a ``CallerIdentity`` with caller_id and scopes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Callable, Coroutine, Optional, Union
from typing import Any, Optional, Union

from acp.errors import AuthenticationRequired
from acp.schema.capability import is_valid_scope

__all__ = [
    "CallerIdentity",
    "AuthConfig",
    "AuthValidator",
    "HmacTokenValidator",
    "validate_bearer_token",
    "extract_token_from_header",
]

# ------------------------------------------------------------------ CallerIdentity


class CallerIdentity:
    """Represents an authenticated caller.

    Attributes:
        caller_id: opaque string identifier (e.g. user-id, service-name).
        scopes: set of scope strings the caller is authorized for.
        metadata: free-form dict for extra claims (e.g. ``aud``, ``iss``).
    """

    def __init__(
        self,
        caller_id: str,
        scopes: set[str] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.caller_id = caller_id
        self.scopes = set(scopes or ())
        self.metadata = dict(metadata or {})
        for s in self.scopes:
            if not is_valid_scope(s):
                raise ValueError(f"Invalid scope in identity: {s!r}")

    def __repr__(self) -> str:
        return f"CallerIdentity(caller_id={self.caller_id!r}, scopes={sorted(self.scopes)!r})"


# ------------------------------------------------------------------ AuthConfig


class AuthConfig:
    """Configuration for the built-in HMAC token validator.

    Parameters:
        secret_key: the HMAC secret (bytes or string). Must be kept
            confidential — treat it like a password.
        token_ttl_seconds: how long a token is valid after issuance.
            Default 3600 (1 hour). Set to 0 to disable expiry checks.
        issuer: optional token issuer claim (``iss``). If set, tokens
            without a matching issuer are rejected.
        audience: optional token audience claim (``aud``). If set, tokens
            without a matching audience are rejected.
    """

    def __init__(
        self,
        secret_key: Union[str, bytes,]
        *,
        token_ttl_seconds: int = 3_600,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
    ) -> None:
        self.secret_key = secret_key if isinstance(secret_key, bytes) else secret_key.encode()
        self.token_ttl_seconds = token_ttl_seconds
        self.issuer = issuer
        self.audience = audience


# ------------------------------------------------------------------ AuthValidator

from typing import Optional, Union
AuthValidator = Callable[[str], Any]
"""Type alias for an authentication validator callable.

The callable receives a raw token string and must return a
``CallerIdentity`` (or raise ``AuthenticationRequired``).
"""


# ------------------------------------------------------------------ HmacTokenValidator


class HmacTokenValidator:
    """Built-in HMAC-SHA256 bearer token validator.

    Token format (URL-safe base64, no padding):
        ``<payload_base64url>.<sig_base64url>``

    Payload is a JSON dict with at least:
        * ``sub``  — subject / caller_id
        * ``scp``  — list of scope strings
        * ``iat``  — issued-at (Unix epoch seconds)
        * ``exp``  — expiration (Unix epoch seconds)

    Usage::

        config = AuthConfig(secret_key="super-secret")
        validator = HmacTokenValidator(config)
        identity = validator.validate("eyJzdWI...<sig>")
    """

    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    # ----------------------------------------------------------- public API

    def validate(self, token: str) -> CallerIdentity:
        """Validate a token string and return a ``CallerIdentity``.

        Raises:
            AuthenticationRequired: token is malformed, expired, or
                signature mismatch.
        """
        try:
            payload_b64, sig_b64 = token.split(".", 1)
        except ValueError:
            raise AuthenticationRequired("Token must be <payload>.<sig>") from None

        payload_bytes = self._b64url_decode(payload_b64)
        sig_bytes = self._b64url_decode(sig_b64)

        expected_sig = hmac.new(
            self._config.secret_key,
            payload_bytes,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(sig_bytes, expected_sig):
            raise AuthenticationRequired("Token signature mismatch")

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise AuthenticationRequired(f"Invalid token payload: {e}") from e

        self._check_claims(payload)

        caller_id = payload.get("sub", "")
        scopes = set(payload.get("scp", []))
        metadata = {k: v for k, v in payload.items() if k not in ("sub", "scp", "iat", "exp")}
        return CallerIdentity(caller_id, scopes, metadata=metadata)

    def issue(self, caller_id: str, scopes: set[str], **claims: Any) -> str:
        """Issue a new signed token for the given caller.

        Parameters:
            caller_id: the ``sub`` claim.
            scopes: list of scope strings for the ``scp`` claim.
            **claims: extra claims to embed in the payload.

        Returns:
            A URL-safe base64 token string.
        """
        now = int(time.time())
        payload = {
            "sub": caller_id,
            "scp": sorted(scopes),
            "iat": now,
            "exp": now + self._config.token_ttl_seconds,
            **claims,
        }
        if self._config.issuer:
            payload["iss"] = self._config.issuer
        if self._config.audience:
            payload["aud"] = self._config.audience

        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        payload_b64 = self._b64url_encode(payload_bytes)
        sig = hmac.new(
            self._config.secret_key,
            payload_bytes,
            hashlib.sha256,
        ).digest()
        sig_b64 = self._b64url_encode(sig)
        return f"{payload_b64}.{sig_b64}"

    # ---------------------------------------------------------- internals

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        pad = 4 - (len(data) % 4)
        if pad != 4:
            data += "=" * pad
        return base64.urlsafe_b64decode(data)

    def _check_claims(self, payload: dict) -> None:
        """Validate time-based and issuer/audience claims."""
        if self._config.token_ttl_seconds > 0:
            exp = payload.get("exp")
            if exp is None:
                raise AuthenticationRequired("Token missing 'exp' claim")
            if time.time() > exp:
                raise AuthenticationRequired("Token expired")

        if self._config.issuer is not None and payload.get("iss") != self._config.issuer:
            raise AuthenticationRequired("Token issuer mismatch")

        if self._config.audience is not None:
            aud = payload.get("aud")
            if isinstance(aud, list):
                if self._config.audience not in aud:
                    raise AuthenticationRequired("Token audience mismatch")
            elif aud != self._config.audience:
                raise AuthenticationRequired("Token audience mismatch")


# ------------------------------------------------------------------ helpers


def validate_bearer_token(
    header_value: Optional[str],
    validator: Optional[AuthValidator],
) -> Optional[CallerIdentity]:
    """Extract a Bearer token from an HTTP-style header and validate it.

    Parameters:
        header_value: the raw header value, e.g.
            ``"Bearer eyJzdWI..."``. May be ``None``.
        validator: an auth validator callable. If ``None``, no
            authentication is enforced and ``None`` is returned.

    Returns:
        ``CallerIdentity`` if validation succeeds, ``None`` if no
        validator is configured.

    Raises:
        AuthenticationRequired: header is missing, malformed, or
            validation fails.
    """
    if validator is None:
        return None
    if not header_value:
        raise AuthenticationRequired("Missing Authorization header")
    parts = header_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationRequired("Authorization header must be 'Bearer <token>'")
    token = parts[1]
    result = validator(token)
    if isinstance(result, Coroutine):
        raise AuthenticationRequired(
            "Async validators are not supported by validate_bearer_token; await the validator directly",
        )
    return result


def extract_token_from_header(header_value: Optional[str]) -> Optional[str]:
    """Extract the raw token string from a ``Bearer <token>`` header.

    Returns ``None`` if the header is missing or not a Bearer token.
    """
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]
