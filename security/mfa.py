"""
Multi-Factor Authentication (MFA) for AhmedETAP Platform
========================================================
Provides TOTP (Time-based One-Time Password, RFC 6238) and WebAuthn/FIDO2
support for second-factor authentication.

Features:
- TOTP secret generation, QR code URI creation, and code verification
- WebAuthn registration & authentication challenge generation / verification
- Graceful fallback when optional dependencies (``pyotp``, ``webauthn``) are
  absent — pure-Python TOTP implementation is used in that case
- In-memory credential store with pluggable persistence interface
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency: pyotp
# ---------------------------------------------------------------------------

try:
    import pyotp as _pyotp

    HAS_PYOTP = True
except ImportError:
    HAS_PYOTP = False
    _pyotp = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Optional dependency: webauthn
# ---------------------------------------------------------------------------

try:
    from webauthn import (
        generate_authentication_options as _webauthn_generate_authentication,
    )
    from webauthn import (
        generate_registration_options as _webauthn_generate_registration,
    )
    from webauthn import (
        verify_authentication_response as _webauthn_verify_authentication,
    )
    from webauthn import (
        verify_registration_response as _webauthn_verify_registration,
    )

    HAS_WEBAUTHN = True
except ImportError:
    HAS_WEBAUTHN = False


# ===========================================================================
# TOTP — pure-Python implementation (RFC 6238) used when pyotp is unavailable
# ===========================================================================


def _hotp(secret_bytes: bytes, counter: int, digits: int = 6) -> str:
    """Generate an HOTP code (RFC 4226).

    Parameters
    ----------
    secret_bytes : bytes
        Raw secret key bytes.
    counter : int
        Moving factor (counter value).
    digits : int
        Number of OTP digits (default 6).

    Returns
    -------
    str
        Zero-padded OTP string of length *digits*.
    """
    # HMAC-SHA1
    msg = struct.pack(">Q", counter)
    h = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    # Dynamic truncation
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def _totp_code(
    secret_b32: str,
    time_step: int = 30,
    t: float | None = None,
    digits: int = 6,
) -> str:
    """Compute a TOTP code from a Base32-encoded secret.

    Parameters
    ----------
    secret_b32 : str
        Base32-encoded secret.
    time_step : int
        Time step in seconds (default 30 per RFC 6238).
    t : float, optional
        Unix timestamp.  Defaults to ``time.time()``.
    digits : int
        Number of OTP digits.

    Returns
    -------
    str
        TOTP code string.
    """
    if t is None:
        t = time.time()
    # Pad Base32 if needed
    missing = len(secret_b32) % 8
    if missing:
        secret_b32 += "=" * (8 - missing)
    secret_bytes = base64.b32decode(secret_b32.upper())
    counter = int(t) // time_step
    return _hotp(secret_bytes, counter, digits=digits)


# ===========================================================================
# TOTP Provider
# ===========================================================================


@dataclass
class TOTPSecret:
    """Stored TOTP secret for a user."""

    user_id: str
    secret: str  # Base32-encoded
    verified: bool = False
    created_at: float = field(default_factory=time.time)
    backup_codes: List[str] = field(default_factory=list)


class TOTPProvider:
    """Time-based One-Time Password (RFC 6238) provider.

    Uses the ``pyotp`` library when available; otherwise falls back to the
    pure-Python implementation above.

    Example
    -------
    >>> provider = TOTPProvider(issuer="AhmedETAP")
    >>> secret = provider.generate_secret("user-123")
    >>> uri = provider.generate_qr_code("user-123", secret)
    >>> provider.verify_code(secret, "123456")
    """

    def __init__(
        self,
        issuer: str = "AhmedETAP",
        time_step: int = 30,
        digits: int = 6,
        window: int = 1,
    ) -> None:
        self.issuer = issuer
        self.time_step = time_step
        self.digits = digits
        self.window = window  # ±1 window for clock drift
        self._secrets: Dict[str, TOTPSecret] = {}

    # -- secret generation ---------------------------------------------------

    def generate_secret(self, user_id: str) -> str:
        """Generate a TOTP secret for a user.

        Parameters
        ----------
        user_id : str
            Unique user identifier.

        Returns
        -------
        str
            Base32-encoded TOTP secret.
        """
        if HAS_PYOTP:
            secret = _pyotp.random_base32()
        else:
            raw = os.urandom(20)
            secret = base64.b32encode(raw).decode("utf-8").rstrip("=")

        self._secrets[user_id] = TOTPSecret(user_id=user_id, secret=secret)
        logger.info("TOTP secret generated for user %s", user_id)
        return secret

    # -- QR code URI ---------------------------------------------------------

    def generate_qr_code(self, user_id: str, secret: str) -> str:
        """Generate ``otpauth://`` URI for QR code scanning.

        Parameters
        ----------
        user_id : str
            User identifier (used as account name).
        secret : str
            Base32-encoded TOTP secret.

        Returns
        -------
        str
            ``otpauth://totp/`` URI.
        """
        if HAS_PYOTP:
            totp = _pyotp.TOTP(secret)
            return totp.provisioning_uri(name=user_id, issuer_name=self.issuer)

        # Manual URI construction
        label = f"{self.issuer}:{user_id}"
        params = [
            f"secret={secret}",
            f"issuer={self.issuer}",
            "algorithm=SHA1",
            f"digits={self.digits}",
            f"period={self.time_step}",
        ]
        return f"otpauth://totp/{label}?{'&'.join(params)}"

    # -- code verification ---------------------------------------------------

    def verify_code(self, secret: str, code: str) -> bool:
        """Verify a TOTP code with a ±1 window for clock drift.

        Parameters
        ----------
        secret : str
            Base32-encoded TOTP secret.
        code : str
            User-supplied TOTP code.

        Returns
        -------
        bool
            ``True`` if the code is valid within the window.
        """
        if HAS_PYOTP:
            totp = _pyotp.TOTP(secret)
            return totp.verify(code, valid_window=self.window)

        # Pure-Python fallback
        now = time.time()
        for offset in range(-self.window, self.window + 1):
            expected = _totp_code(
                secret,
                time_step=self.time_step,
                t=now + offset * self.time_step,
                digits=self.digits,
            )
            if hmac.compare_digest(expected, code):
                return True
        return False

    # -- backup codes --------------------------------------------------------

    def generate_backup_codes(self, user_id: str, count: int = 10) -> List[str]:
        """Generate one-time backup codes for a user.

        Parameters
        ----------
        user_id : str
            User identifier.
        count : int
            Number of backup codes to generate (default 10).

        Returns
        -------
        list[str]
            List of backup code strings.
        """
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        entry = self._secrets.get(user_id)
        if entry:
            entry.backup_codes = codes
        else:
            self._secrets[user_id] = TOTPSecret(user_id=user_id, secret="", backup_codes=codes)
        logger.info("Generated %d backup codes for user %s", count, user_id)
        return codes

    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify and consume a backup code (one-time use).

        Parameters
        ----------
        user_id : str
            User identifier.
        code : str
            Backup code to verify.

        Returns
        -------
        bool
            ``True`` if the code was valid (and has been consumed).
        """
        entry = self._secrets.get(user_id)
        if entry and code in entry.backup_codes:
            entry.backup_codes.remove(code)
            logger.info(
                "Backup code used for user %s (%d remaining)", user_id, len(entry.backup_codes)
            )
            return True
        return False

    # -- user management helpers ---------------------------------------------

    def enable_totp(self, user_id: str) -> Dict[str, str]:
        """Enable TOTP for a user.  Returns secret and QR URI.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        dict
            ``{"secret": "...", "qr_uri": "..."}``
        """
        secret = self.generate_secret(user_id)
        qr_uri = self.generate_qr_code(user_id, secret)
        backup_codes = self.generate_backup_codes(user_id)
        return {
            "secret": secret,
            "qr_uri": qr_uri,
            "backup_codes": backup_codes,
        }

    def get_secret(self, user_id: str) -> str | None:
        """Return the stored Base32 secret for a user, or ``None``."""
        entry = self._secrets.get(user_id)
        return entry.secret if entry else None

    def remove_secret(self, user_id: str) -> bool:
        """Remove the TOTP secret for a user.

        Returns
        -------
        bool
            ``True`` if a secret was removed.
        """
        if user_id in self._secrets:
            del self._secrets[user_id]
            logger.info("TOTP secret removed for user %s", user_id)
            return True
        return False


# ===========================================================================
# WebAuthn / FIDO2 Provider
# ===========================================================================


@dataclass
class WebAuthnCredential:
    """Stored WebAuthn credential for a user."""

    credential_id: str  # Base64url-encoded
    user_id: str
    public_key: bytes
    sign_count: int = 0
    transports: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class WebAuthnProvider:
    """WebAuthn / FIDO2 support for passwordless and second-factor auth.

    When the ``webauthn`` PyPI package is available, it delegates to the
    library's proven implementation.  When absent, it falls back to a
    simplified challenge-response flow suitable for development and testing.

    .. note::
       The fallback implementation is **not** suitable for production
       without a proper WebAuthn library performing cryptographic
       verification of the authenticator assertion.

    Parameters
    ----------
    rp_id : str
        Relying Party ID (typically the domain, e.g. ``"etap.ai"``).
    rp_name : str
        Human-readable RP name.
    origin : str
        Expected origin (e.g. ``"https://etap.ai"``).
    """

    def __init__(
        self,
        rp_id: str = "localhost",
        rp_name: str = "AhmedETAP",
        origin: str = "http://localhost:3000",
    ) -> None:
        self.rp_id = rp_id
        self.rp_name = rp_name
        self.origin = origin
        self._credentials: Dict[str, List[WebAuthnCredential]] = {}
        self._challenges: Dict[str, str] = {}  # user_id -> challenge

    # -- registration --------------------------------------------------------

    def generate_registration_options(self, user_id: str) -> Dict[str, Any]:
        """Generate WebAuthn registration challenge.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        dict
            Registration options suitable for passing to
            ``navigator.credentials.create()`` on the client.
        """
        challenge = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")
        self._challenges[user_id] = challenge

        if HAS_WEBAUTHN:
            try:
                options = _webauthn_generate_registration(
                    rp_id=self.rp_id,
                    rp_name=self.rp_name,
                    user_id=user_id,
                    user_name=user_id,
                    challenge=challenge,
                )
                return options
            except Exception as exc:
                logger.warning("webauthn library generate_registration_options failed: %s", exc)

        # Fallback: return a dict matching the WebAuthn API structure
        return {
            "challenge": challenge,
            "rp": {
                "id": self.rp_id,
                "name": self.rp_name,
            },
            "user": {
                "id": base64.urlsafe_b64encode(user_id.encode()).decode("utf-8").rstrip("="),
                "name": user_id,
                "displayName": user_id,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},  # ES256
                {"type": "public-key", "alg": -257},  # RS256
            ],
            "timeout": 60000,
            "attestation": "none",
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "userVerification": "preferred",
                "residentKey": "preferred",
            },
        }

    def verify_registration(self, user_id: str, response: dict) -> Dict[str, Any]:
        """Verify WebAuthn registration response from the client.

        Parameters
        ----------
        user_id : str
            User identifier.
        response : dict
            The registration response from the authenticator.

        Returns
        -------
        dict
            ``{"credential_id": "...", "success": True}`` on success,
            ``{"success": False, "error": "..."}`` on failure.
        """
        challenge = self._challenges.pop(user_id, None)
        if not challenge:
            return {"success": False, "error": "No pending registration challenge"}

        if HAS_WEBAUTHN:
            try:
                verification = _webauthn_verify_registration(
                    credential=response,
                    expected_challenge=challenge,
                    expected_origin=self.origin,
                    expected_rp_id=self.rp_id,
                )
                cred_id = verification.credential_id
                public_key = verification.credential_public_key
                sign_count = verification.sign_count

                credential = WebAuthnCredential(
                    credential_id=cred_id,
                    user_id=user_id,
                    public_key=public_key,
                    sign_count=sign_count,
                    transports=response.get("transports", []),
                )
                self._credentials.setdefault(user_id, []).append(credential)
                logger.info("WebAuthn credential registered for user %s", user_id)
                return {"credential_id": cred_id, "success": True}
            except Exception as exc:
                logger.warning("WebAuthn registration verification failed: %s", exc)
                return {"success": False, "error": str(exc)}

        # Fallback: store credential without full crypto verification
        cred_id = response.get("id", secrets.token_hex(16))
        public_key_b64 = response.get("response", {}).get("publicKey", "")
        try:
            public_key = base64.urlsafe_b64decode(public_key_b64 + "==")
        except Exception:
            public_key = b""

        credential = WebAuthnCredential(
            credential_id=cred_id,
            user_id=user_id,
            public_key=public_key,
            sign_count=0,
            transports=response.get("transports", []),
        )
        self._credentials.setdefault(user_id, []).append(credential)
        logger.info("WebAuthn credential registered (fallback) for user %s", user_id)
        return {"credential_id": cred_id, "success": True}

    # -- authentication ------------------------------------------------------

    def generate_authentication_options(self, user_id: str) -> Dict[str, Any]:
        """Generate WebAuthn authentication challenge.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        dict
            Authentication options suitable for
            ``navigator.credentials.get()`` on the client.
        """
        challenge = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")
        self._challenges[user_id] = challenge

        user_creds = self._credentials.get(user_id, [])
        allow_credentials = [
            {
                "type": "public-key",
                "id": c.credential_id,
                "transports": c.transports or ["internal"],
            }
            for c in user_creds
        ]

        if HAS_WEBAUTHN:
            try:
                options = _webauthn_generate_authentication(
                    rp_id=self.rp_id,
                    challenge=challenge,
                    allow_credentials=allow_credentials,
                )
                return options
            except Exception as exc:
                logger.warning("webauthn library generate_authentication_options failed: %s", exc)

        # Fallback
        return {
            "challenge": challenge,
            "rpId": self.rp_id,
            "allowCredentials": allow_credentials
            if allow_credentials
            else [{"type": "public-key", "id": "_"}],
            "timeout": 60000,
            "userVerification": "preferred",
        }

    def verify_authentication(self, credential_id: str, response: dict) -> bool:
        """Verify WebAuthn authentication assertion.

        Parameters
        ----------
        credential_id : str
            The credential ID from the authenticator response.
        response : dict
            The authentication response from the authenticator.

        Returns
        -------
        bool
            ``True`` if authentication succeeded.
        """
        # Find the credential
        stored_cred: WebAuthnCredential | None = None
        owner_id: str | None = None
        for uid, creds in self._credentials.items():
            for c in creds:
                if c.credential_id == credential_id:
                    stored_cred = c
                    owner_id = uid
                    break
            if stored_cred:
                break

        if stored_cred is None or owner_id is None:
            logger.warning("WebAuthn authentication: unknown credential %s", credential_id)
            return False

        challenge = self._challenges.pop(owner_id, None)
        if not challenge:
            logger.warning("WebAuthn authentication: no pending challenge for user %s", owner_id)
            return False

        if HAS_WEBAUTHN:
            try:
                _webauthn_verify_authentication(
                    credential=response,
                    expected_challenge=challenge,
                    expected_origin=self.origin,
                    expected_rp_id=self.rp_id,
                    credential_public_key=stored_cred.public_key,
                    credential_current_sign_count=stored_cred.sign_count,
                )
                # Update sign count
                stored_cred.sign_count = response.get("response", {}).get(
                    "signCount", stored_cred.sign_count + 1
                )
                logger.info("WebAuthn authentication succeeded for user %s", owner_id)
                return True
            except Exception as exc:
                logger.warning("WebAuthn authentication verification failed: %s", exc)
                return False

        # Fallback: reject without webauthn library
        # SECURITY: The fallback cannot perform cryptographic verification of the
        # authenticator assertion.  In production, always install the 'webauthn'
        # package.  This rejection prevents bypass of the second factor.
        logger.warning(
            "WebAuthn authentication REJECTED (no webauthn library): "
            "credential_id=%s user=%s.  Install 'webauthn' for production.",
            credential_id,
            owner_id,
        )
        return False

    # -- credential management -----------------------------------------------

    def get_credentials(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all registered credentials for a user.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        list[dict]
            List of credential metadata dicts.
        """
        creds = self._credentials.get(user_id, [])
        return [
            {
                "credential_id": c.credential_id,
                "transports": c.transports,
                "sign_count": c.sign_count,
                "created_at": c.created_at,
            }
            for c in creds
        ]

    def remove_credential(self, user_id: str, credential_id: str) -> bool:
        """Remove a specific credential for a user.

        Parameters
        ----------
        user_id : str
            User identifier.
        credential_id : str
            The credential ID to remove.

        Returns
        -------
        bool
            ``True`` if the credential was found and removed.
        """
        creds = self._credentials.get(user_id, [])
        before = len(creds)
        self._credentials[user_id] = [c for c in creds if c.credential_id != credential_id]
        removed = len(self._credentials[user_id]) < before
        if removed:
            logger.info("WebAuthn credential %s removed for user %s", credential_id, user_id)
        return removed

    def has_credentials(self, user_id: str) -> bool:
        """Check whether a user has any registered WebAuthn credentials."""
        return bool(self._credentials.get(user_id))


# ===========================================================================
# MFA Orchestrator
# ===========================================================================


class MFAOrchestrator:
    """Unified MFA orchestrator combining TOTP and WebAuthn.

    Parameters
    ----------
    totp_provider : TOTPProvider, optional
        TOTP provider instance (created with defaults if not given).
    webauthn_provider : WebAuthnProvider, optional
        WebAuthn provider instance (created with defaults if not given).
    require_mfa_for_roles : list[str], optional
        Roles that require MFA (default ``["admin", "engineer"]``).
    """

    def __init__(
        self,
        totp_provider: TOTPProvider | None = None,
        webauthn_provider: WebAuthnProvider | None = None,
        require_mfa_for_roles: List[str] | None = None,
    ) -> None:
        self.totp = totp_provider or TOTPProvider()
        self.webauthn = webauthn_provider or WebAuthnProvider()
        self.require_mfa_for_roles = require_mfa_for_roles or ["admin", "engineer"]
        self._mfa_verified_sessions: Dict[str, float] = {}  # session_id -> expiry

    def is_mfa_required(self, role: str) -> bool:
        """Check whether a given role requires MFA.

        Parameters
        ----------
        role : str
            User role (e.g. ``"admin"``).

        Returns
        -------
        bool
        """
        return role in self.require_mfa_for_roles

    def verify_totp(self, user_id: str, code: str) -> bool:
        """Verify a TOTP code for a user.

        Parameters
        ----------
        user_id : str
            User identifier.
        code : str
            TOTP code from authenticator app.

        Returns
        -------
        bool
        """
        secret = self.totp.get_secret(user_id)
        if not secret:
            logger.warning("No TOTP secret found for user %s", user_id)
            return False
        return self.totp.verify_code(secret, code)

    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify a backup code for a user.

        Parameters
        ----------
        user_id : str
            User identifier.
        code : str
            Backup code string.

        Returns
        -------
        bool
        """
        return self.totp.verify_backup_code(user_id, code)

    def verify_webauthn(self, credential_id: str, response: dict) -> bool:
        """Verify a WebAuthn authentication response.

        Parameters
        ----------
        credential_id : str
            Credential ID from the authenticator.
        response : dict
            Authentication response from the authenticator.

        Returns
        -------
        bool
        """
        return self.webauthn.verify_authentication(credential_id, response)

    def mark_session_verified(self, session_id: str, ttl_seconds: int = 3600) -> None:
        """Mark a session as MFA-verified.

        Parameters
        ----------
        session_id : str
            Session identifier.
        ttl_seconds : int
            How long the MFA verification lasts (default 1 hour).
        """
        self._mfa_verified_sessions[session_id] = time.time() + ttl_seconds
        logger.info("Session %s marked as MFA-verified for %d seconds", session_id, ttl_seconds)

    def is_session_verified(self, session_id: str) -> bool:
        """Check whether a session has a valid MFA verification.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        bool
        """
        expiry = self._mfa_verified_sessions.get(session_id)
        if expiry is None:
            return False
        if time.time() > expiry:
            del self._mfa_verified_sessions[session_id]
            return False
        return True

    def revoke_session(self, session_id: str) -> None:
        """Revoke MFA verification for a session.

        Parameters
        ----------
        session_id : str
            Session identifier.
        """
        self._mfa_verified_sessions.pop(session_id, None)
        logger.info("MFA verification revoked for session %s", session_id)

    def get_status(self, user_id: str) -> Dict[str, Any]:
        """Get MFA enrollment status for a user.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        dict
            ``{"totp_enabled": bool, "webauthn_enabled": bool,
            "webauthn_credentials": int}``
        """
        return {
            "totp_enabled": self.totp.get_secret(user_id) is not None,
            "webauthn_enabled": self.webauthn.has_credentials(user_id),
            "webauthn_credentials": len(self.webauthn.get_credentials(user_id)),
        }
