"""Add MFA credentials table.

Revision ID: 003
Revises: 002
Create Date: 2025-01-03 00:00:00.000000

This migration creates the ``mfa_credentials`` table, which stores
multi-factor authentication credentials for users who have enabled MFA.

Supported MFA types:
* **totp** — Time-based One-Time Password (RFC 6238).  The
  ``credential_data`` JSON field stores the encrypted TOTP secret.
* **webauthn** — Web Authentication (FIDO2).  The ``credential_data``
  JSON field stores the WebAuthn credential (key handle, public key,
  sign count, etc.).

The ``credential_data`` column MUST be encrypted at the application
layer before storage.  This table only provides the schema — the
encryption / decryption logic lives in ``security/mfa.py``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the mfa_credentials table."""

    op.create_table(
        "mfa_credentials",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "mfa_type",
            sa.String(32),
            nullable=False,
            comment="MFA mechanism: 'totp' or 'webauthn'",
        ),
        sa.Column(
            "credential_data",
            sa.JSON(),
            nullable=False,
            comment="Encrypted TOTP secret or WebAuthn credential payload",
        ),
        sa.Column(
            "verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Whether the user has completed MFA setup verification",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Drop the mfa_credentials table."""

    op.drop_table("mfa_credentials")
