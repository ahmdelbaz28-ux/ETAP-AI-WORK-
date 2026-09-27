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
    is_executable: bool = True

    @model_validator(mode="after")
    def validate_system_integrity(self) -> SldIngestOutput:
        """Validate topological integrity, required electrical grounding, and missing-value safety."""
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
                raise ValueError(
                    f"Line self-loop detected: line {line.line_id} from {line.from_bus_id} to {line.to_bus_id}"
                )

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
                raise ValueError(
                    f"Invalid provenance path format: '{path}' (expected e.g. 'buses[0].voltage_magnitude')"
                )

            coll_name, idx_str, field_name = match.groups()
            idx = int(idx_str)
            target_list = containers.get(coll_name, [])

            if idx >= len(target_list):
                raise ValueError(
                    f"Provenance path refers to nonexistent index: '{path}' (length of {coll_name} is {len(target_list)})"
                )

            target_obj = target_list[idx]
            # Check if field exists on model
            if field_name not in target_obj.model_fields and not hasattr(target_obj, field_name):
                raise ValueError(
                    f"Provenance path refers to unknown field '{field_name}' on {coll_name}[{idx}]: '{path}'"
                )

        # 6. Safety-Critical Electrical Field Grounding & Missing-Value Safety (STEP 2)
        # Extract missing paths from warnings
        missing_paths = set()
        for w in self.warnings:
            if w.startswith("MISSING:"):
                missing_path = w[len("MISSING:"):].strip()
                missing_paths.add(missing_path)

        # Rule 6a: A missing electrical value must NEVER be marked in provenance (especially not SourceKind.standard)
        for m_path in missing_paths:
            if m_path in self.provenance:
                raise ValueError(
                    f"Missing electrical value '{m_path}' cannot be marked in provenance or assigned standard default"
                )

        # Rule 6b: Any MISSING warning makes the proposal non-executable
        if missing_paths:
            self.is_executable = False

        # Rule 6c: Required safety-critical electrical parameters per collection
        # IDs (bus_id, line_id, from_bus_id, to_bus_id) are EXEMPT.
        # Electrical fields MUST be grounded in provenance or explicitly recorded as MISSING.
        required_electrical_fields = {
            "buses": ["voltage_magnitude"],
            "lines": ["r1", "x1"],
        }

        for coll_name, req_fields in required_electrical_fields.items():
            elements = containers.get(coll_name, [])
            for idx, elem in enumerate(elements):
                for req_f in req_fields:
                    path = f"{coll_name}[{idx}].{req_f}"
                    if path not in self.provenance:
                        if path in missing_paths or f"MISSING:{path}" in self.warnings:
                            self.is_executable = False
                        else:
                            raise ValueError(
                                f"Missing provenance for safety-critical electrical parameter '{path}'. "
                                "Values populated only by Pydantic defaults or guesses are rejected."
                            )
                    else:
                        # Line impedance (R1/X1) cannot use 'standard' to invent unknown parameters
                        if coll_name == "lines" and req_f in ("r1", "x1") and self.provenance[path] == "standard":
                            raise ValueError(
                                f"Cannot mark line impedance '{path}' as 'standard'. "
                                "Never invent R/X parameters: missing values must be requested from user, not guessed."
                            )

        return self


def validate_ingest(data: Any) -> SldIngestOutput:
    """Validate a dictionary or object against the SldIngestOutput schema."""
    if isinstance(data, SldIngestOutput):
        return data
    return SldIngestOutput.model_validate(data)

