"""
services/dspy_copilot/schemas.py — Pydantic v2 schemas for DSPy Copilot.

Enforces zero-hallucination, mandatory provenance citation, and strict validation
around power-system ingest and diagnostics. Reuses canonical specs from core_model.specs.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core_model.specs import BusSpec, LineSpec, LoadSpec, TransformerSpec

SourceKind = Literal["user_input", "project_data", "computed", "standard"]

_PATH_RE = re.compile(r"^(buses|lines|loads|transformers)\[(\d+)\]\.([a-zA-Z0-9_]+)$")


class DiagnosticFinding(BaseModel):
    """Deterministic or LLM-assisted finding from study analysis."""

    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warning", "violation"]
    code: str
    message: str
    bus_id: int | None = None
    standard_ref: str | None = None


class DiagnosticOutput(BaseModel):
    """Structured diagnostic copilot output schema."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    findings: list[DiagnosticFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def validate_summary_length(cls, v: str) -> str:
        """Ensure summary does not exceed 2000 characters."""
        if len(v) > 2000:
            raise ValueError(f"Summary exceeds 2000 characters (length: {len(v)})")
        return v


class SldIngestOutput(BaseModel):
    """Structured output for SLD ingestion into canonical system specs."""

    model_config = ConfigDict(extra="forbid")

    buses: list[BusSpec]
    lines: list[LineSpec] = Field(default_factory=list)
    loads: list[LoadSpec] = Field(default_factory=list)
    transformers: list[TransformerSpec] = Field(default_factory=list)
    provenance: dict[str, SourceKind]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_system_integrity(self) -> SldIngestOutput:
        """Validate topological integrity and provenance grounding."""
        # 1. Reject empty system (0 buses)
        if len(self.buses) == 0:
            raise ValueError("Empty system is invalid: at least one bus required")

        # 2. Reject if no bus is slack
        has_slack = any(b.bus_type == "slack" for b in self.buses)
        if not has_slack:
            raise ValueError("System has no slack bus: at least one slack bus is required")

        # 3. Reject line self-loops
        for line in self.lines:
            if line.from_bus_id == line.to_bus_id:
                raise ValueError(f"Line self-loop detected: line {line.line_id} from {line.from_bus_id} to {line.to_bus_id}")

        # 4. Provenance must not be empty
        if not self.provenance:
            raise ValueError("Missing provenance: every emitted numeric field must have provenance")

        # 5. Validate provenance paths against elements
        containers = {
            "buses": self.buses,
            "lines": self.lines,
            "loads": self.loads,
            "transformers": self.transformers,
        }

        for path, _kind in self.provenance.items():
            match = _PATH_RE.match(path)
            if not match:
                raise ValueError(f"Invalid provenance path format: '{path}' (expected e.g. 'buses[0].voltage_magnitude')")

            coll_name, idx_str, field_name = match.groups()
            idx = int(idx_str)
            target_list = containers.get(coll_name, [])

            if idx >= len(target_list):
                raise ValueError(f"Provenance path refers to nonexistent index: '{path}' (length of {coll_name} is {len(target_list)})")

            target_obj = target_list[idx]
            # Check if field exists on model
            if field_name not in target_obj.model_fields and not hasattr(target_obj, field_name):
                raise ValueError(f"Provenance path refers to unknown field '{field_name}' on {coll_name}[{idx}]: '{path}'")

        return self


def validate_ingest(data: Any) -> SldIngestOutput:
    """Validate a dictionary or object against the SldIngestOutput schema."""
    if isinstance(data, SldIngestOutput):
        return data
    return SldIngestOutput.model_validate(data)
