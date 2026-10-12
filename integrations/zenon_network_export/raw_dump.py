"""Zenon Raw Dump v1 Schema.

Strict Pydantic contract for raw telemetry and project variable dumps
extracted from ABB / COPA-DATA zenon Runtime via COM Automation or Zenon API.

Rule: Missing attributes are explicitly None / empty. No defaults or synthetic
values are fabricated.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ZenonRawProject(BaseModel):
    """Metadata describing the zenon project at time of dump."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1, max_length=256)
    version: Optional[str] = Field(default=None)
    path: Optional[str] = Field(default=None)
    substation_name: Optional[str] = Field(default=None)
    base_mva: Optional[float] = Field(default=None)
    system_frequency_hz: Optional[float] = Field(default=None)


class ZenonRawVariable(BaseModel):
    """Raw zenon variable / tag exported from zenOn.Project.Variables."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    identification: Optional[str] = Field(
        default=None, description="Tag description or IEC 61850 LN"
    )
    data_type: Optional[str] = Field(default=None)
    unit: Optional[str] = Field(default=None)
    value: Optional[Any] = Field(default=None)
    driver: Optional[str] = Field(default=None)


class ZenonRawScreenElement(BaseModel):
    """Graphic element on a zenon mimic / screen."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    linked_variables: list[str] = Field(default_factory=list)


class ZenonRawScreen(BaseModel):
    """Mimic / single-line diagram screen exported from zenon."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1)
    elements: list[ZenonRawScreenElement] = Field(default_factory=list)


class ZenonRawDump(BaseModel):
    """Root container for zenon raw dump v1."""

    model_config = ConfigDict(extra="ignore")

    dump_version: str = Field(default="1.0.0")
    project: ZenonRawProject
    variables: list[ZenonRawVariable] = Field(default_factory=list)
    screens: list[ZenonRawScreen] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
