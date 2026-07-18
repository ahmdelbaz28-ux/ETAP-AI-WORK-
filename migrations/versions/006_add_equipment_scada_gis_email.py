"""Add equipment, scada_tags, gis_features, email_send_log tables.

Revision ID: 006_equipment_scada_gis_email
Revises: 005
Create Date: 2026-07-18 00:00:00.000000

Why this migration exists
--------------------------
The audit report (AhmedETAP_Audit_Report.pdf section 11) found that
several API endpoints reference tables that did NOT exist in the
database schema:

* ``api/equipment.py`` exposes 12 CRUD endpoints but there was no
  ``equipment`` table — endpoints would fail at runtime with undefined
  behavior (SQLAlchemy might auto-create a table, or the query would
  fail with NoSuchTableError).
* ``services/email_send_log.py`` writes to an ``email_send_log`` table
  that was never created via migration — it relied on
  ``Base.metadata.create_all`` which only runs at startup, missing
  any pre-existing data.
* ``api/scada.py`` references ``scada_tags`` for SCADA tag metadata.
* ``api/digital_twin.py`` references ``gis_features`` for GIS features
  linked to the digital twin.

This migration creates all four tables with proper foreign keys to
the ``projects`` table (CASCADE on project delete), indexes on the
most common query columns, and JSON columns for flexible properties.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "006_equipment_scada_gis_email"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- equipment ---
    # Stores engineering equipment (buses, lines, transformers, motors, etc.)
    # linked to a project. The `properties` JSON column holds type-specific
    # attributes (impedance, rating, voltage, etc.) — matching the
    # core_model/ spec but flexible enough for custom equipment.
    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "type",
            sa.String(64),
            nullable=False,
            comment="bus, line, transformer, motor, generator, load, etc.",
        ),
        sa.Column(
            "properties",
            sa.JSON(),
            nullable=True,
            comment="Type-specific attributes (impedance, rating, etc.)",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_equipment_project_id", "equipment", ["project_id"])
    op.create_index("ix_equipment_type", "equipment", ["type"])
    op.create_index("ix_equipment_name", "equipment", ["name"])

    # --- scada_tags ---
    # Stores SCADA tag metadata (tag name, source, data type, unit, etc.)
    # used by the digital twin and SCADA integration modules.
    op.create_table(
        "scada_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag_name", sa.String(255), nullable=False),
        sa.Column(
            "source",
            sa.String(128),
            nullable=False,
            comment="ETAP, OPC-UA, IEC 61850, Modbus, etc.",
        ),
        sa.Column(
            "data_type",
            sa.String(32),
            nullable=False,
            comment="analog, digital, string",
        ),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column("last_value", sa.Float(), nullable=True),
        sa.Column("last_timestamp", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index("ix_scada_tags_project_id", "scada_tags", ["project_id"])
    op.create_index(
        "ix_scada_tags_tag_name",
        "scada_tags",
        ["tag_name"],
        unique=False,
    )

    # --- gis_features ---
    # Stores GIS features (points, lines, polygons) linked to a project's
    # geographical context. Used by the digital twin's gis_bridge.
    op.create_table(
        "gis_features",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature_id",
            sa.String(128),
            nullable=False,
            comment="External ID from QGIS/ArcGIS source",
        ),
        sa.Column(
            "feature_type",
            sa.String(64),
            nullable=False,
            comment="point, line, polygon, substation, line, etc.",
        ),
        sa.Column(
            "geometry",
            sa.JSON(),
            nullable=False,
            comment="GeoJSON geometry or WKT",
        ),
        sa.Column("properties", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index("ix_gis_features_project_id", "gis_features", ["project_id"])
    op.create_index(
        "ix_gis_features_feature_id",
        "gis_features",
        ["feature_id"],
        unique=False,
    )

    # --- email_send_log ---
    # Stores a log of every email sent (used by the digest builder and
    # audit trail). Previously relied on Base.metadata.create_all which
    # only runs at app startup and cannot be queried before the first
    # app boot.
    op.create_table(
        "email_send_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column(
            "flow",
            sa.String(64),
            nullable=False,
            comment="notification, otp, magic_link, digest, etc.",
        ),
        sa.Column("success", sa.Boolean(), nullable=False, default=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "provider",
            sa.String(64),
            nullable=True,
            comment="resend, smtp, etc.",
        ),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=True,
            comment="Additional send metadata",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_email_send_log_recipient",
        "email_send_log",
        ["recipient"],
        unique=False,
    )
    op.create_index(
        "ix_email_send_log_created_at",
        "email_send_log",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_email_send_log_flow",
        "email_send_log",
        ["flow"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_send_log_flow", table_name="email_send_log")
    op.drop_index("ix_email_send_log_created_at", table_name="email_send_log")
    op.drop_index("ix_email_send_log_recipient", table_name="email_send_log")
    op.drop_table("email_send_log")

    op.drop_index("ix_gis_features_feature_id", table_name="gis_features")
    op.drop_index("ix_gis_features_project_id", table_name="gis_features")
    op.drop_table("gis_features")

    op.drop_index("ix_scada_tags_tag_name", table_name="scada_tags")
    op.drop_index("ix_scada_tags_project_id", table_name="scada_tags")
    op.drop_table("scada_tags")

    op.drop_index("ix_equipment_name", table_name="equipment")
    op.drop_index("ix_equipment_type", table_name="equipment")
    op.drop_index("ix_equipment_project_id", table_name="equipment")
    op.drop_table("equipment")
