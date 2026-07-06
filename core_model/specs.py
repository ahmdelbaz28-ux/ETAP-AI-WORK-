"""
Shared Pydantic spec models for power-system studies.

These are the canonical request/response schemas for study execution.
Both `api/studies.py` (HTTP API layer) and `services/study_service.py`
(service layer) import from here to avoid duplicating model definitions
(SonarCloud duplicated_lines_density / S4144).

Note: `StudyRequest.validate_study_type` differs between the API and the
service layer (the API allows more study types incl. ETAP GUI agent).
To keep one canonical definition here, we accept the SUPERSET of allowed
study types (the API's larger set). The service layer can apply tighter
runtime filtering if needed.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class _BaseSpecModel(BaseModel):
    """Base for all Spec classes — disables extra fields by default."""

    model_config = ConfigDict(extra="ignore")


# ─── BusSpec ─────────────────────────────────────────────────────────────────


class BusSpec(_BaseSpecModel):
    """Bus specification for power-system studies."""

    bus_id: int
    voltage_magnitude: float = Field(
        default=1.0, validation_alias=AliasChoices("voltage_magnitude", "vm"),
    )
    voltage_angle: float = Field(default=0.0, validation_alias=AliasChoices("voltage_angle", "va"))
    load_power_real: float = Field(
        default=0.0, validation_alias=AliasChoices("load_power_real", "p_load", "pd"),
    )
    load_power_imag: float = Field(
        default=0.0,
        validation_alias=AliasChoices("load_power_imag", "load_power_reactive", "q_load", "qd"),
    )
    generation_power_real: float = Field(
        default=0.0, validation_alias=AliasChoices("generation_power_real", "power_real", "pg"),
    )
    generation_power_imag: float = Field(
        default=0.0, validation_alias=AliasChoices("generation_power_imag", "power_reactive", "qg"),
    )
    bus_type: str = "pq"
    base_kv: float | None = None
    q_min: float = Field(
        default=-999.0, validation_alias=AliasChoices("q_min", "min_power_reactive", "min_q"),
    )
    q_max: float = Field(
        default=999.0, validation_alias=AliasChoices("q_max", "max_power_reactive", "max_q"),
    )
    area: int | None = None
    zone: int | None = None
    voltage_setpoint: float | None = Field(
        default=None,
        validation_alias=AliasChoices("voltage_setpoint", "voltage_magnitude_setpoint"),
    )

    @field_validator("bus_type")
    @classmethod
    def validate_bus_type(cls, v: str) -> str:
        """Normalize and validate a bus type string (slack/pv/pq)."""
        v = v.lower().strip()
        if v not in ("slack", "pv", "pq"):
            raise ValueError("bus_type must be slack, pv, or pq")
        return v

    @field_validator("voltage_magnitude")
    @classmethod
    def validate_voltage_magnitude(cls, v: float) -> float:
        """Voltage magnitude must be reasonable (0.5–2.0 pu)."""
        if v < 0.5 or v > 2.0:
            raise ValueError(f"voltage_magnitude must be between 0.5 and 2.0 pu, got {v}")
        return v

    @field_validator("voltage_angle")
    @classmethod
    def validate_voltage_angle(cls, v: float) -> float:
        """Voltage angle must be within -360 to +360 degrees."""
        if v < -360.0 or v > 360.0:
            raise ValueError(f"voltage_angle must be between -360 and 360 degrees, got {v}")
        return v

    @field_validator("q_min", "q_max")
    @classmethod
    def validate_reactive_limits(cls, v: float, info: Any) -> float:
        """Reactive power limits must be within a reasonable range."""
        if v < -9999.0 or v > 9999.0:
            raise ValueError(
                f"Reactive power limit out of reasonable range (-9999 to 9999), got {v}",
            )
        return v


# ─── LineSpec ────────────────────────────────────────────────────────────────


class LineSpec(_BaseSpecModel):
    """Transmission line specification."""

    line_id: int
    from_bus_id: int = Field(validation_alias=AliasChoices("from_bus_id", "from"))
    to_bus_id: int = Field(validation_alias=AliasChoices("to_bus_id", "to"))
    r1: float = Field(default=0.01, validation_alias=AliasChoices("r1", "resistance"))
    x1: float = Field(default=0.05, validation_alias=AliasChoices("x1", "reactance"))
    r0: float | None = None
    x0: float | None = None
    bshunt1: float = Field(
        default=0.02, validation_alias=AliasChoices("bshunt1", "b1", "bshunt", "susceptance"),
    )
    bshunt0: float | None = Field(default=None, validation_alias=AliasChoices("bshunt0", "b0"))
    rating_mva: float | None = None

    @field_validator("r1", "x1", "r0", "x0")
    @classmethod
    def validate_impedance_values(cls, v: float | None, info: Any) -> float | None:
        """Impedance values must be non-negative."""
        if v is not None and v < 0:
            raise ValueError(f"{info.field_name} must be non-negative, got {v}")
        return v

    @field_validator("rating_mva")
    @classmethod
    def validate_rating(cls, v: float | None) -> float | None:
        """Line rating must be positive if provided."""
        if v is not None and v <= 0:
            raise ValueError(f"rating_mva must be positive, got {v}")
        return v


# ─── TransformerSpec ─────────────────────────────────────────────────────────


class TransformerSpec(_BaseSpecModel):
    """Transformer specification."""

    transformer_id: int
    from_bus_id: int
    to_bus_id: int
    r1: float = 0.0
    x1: float = 0.05
    tap_ratio: float = Field(default=1.0, validation_alias=AliasChoices("tap_ratio", "tap"))
    phase_shift_deg: float = Field(
        default=0.0, validation_alias=AliasChoices("phase_shift_deg", "phase_shift"),
    )

    @field_validator("tap_ratio")
    @classmethod
    def validate_tap_ratio(cls, v: float) -> float:
        """Transformer tap ratio must be reasonable (0.5–2.0 pu)."""
        if v < 0.5 or v > 2.0:
            raise ValueError(f"tap_ratio must be between 0.5 and 2.0 pu, got {v}")
        return v

    @field_validator("phase_shift_deg")
    @classmethod
    def validate_phase_shift(cls, v: float) -> float:
        """Phase shift must be within -180 to +180 degrees."""
        if v < -180.0 or v > 180.0:
            raise ValueError(f"phase_shift_deg must be between -180 and 180, got {v}")
        return v


# ─── GeneratorSpec ───────────────────────────────────────────────────────────


class GeneratorSpec(_BaseSpecModel):
    """Generator specification."""

    generator_id: int
    bus_id: int
    r1: float = 0.0
    x1: float = Field(default=0.2, validation_alias=AliasChoices("x1", "xd_pu", "xdash"))
    r2: float | None = None
    x2: float | None = None
    r0: float | None = None
    x0: float | None = None
    internal_voltage_mag: float = Field(
        default=1.05,
        validation_alias=AliasChoices("internal_voltage_mag", "voltage_setpoint", "v_setpoint"),
    )
    internal_voltage_ang_deg: float = Field(
        default=0.0, validation_alias=AliasChoices("internal_voltage_ang_deg", "voltage_angle"),
    )
    power_real: float | None = Field(
        default=None, validation_alias=AliasChoices("power_real", "pg"),
    )
    power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("power_reactive", "qg"),
    )
    max_power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("max_power_reactive", "q_max"),
    )
    min_power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("min_power_reactive", "q_min"),
    )


# ─── LoadSpec ────────────────────────────────────────────────────────────────


class LoadSpec(_BaseSpecModel):
    """Load specification."""

    load_id: int
    bus_id: int
    p_mw: float = Field(
        default=0.0, validation_alias=AliasChoices("p_mw", "power_real", "load_power_real"),
    )
    q_mvar: float = Field(
        default=0.0,
        validation_alias=AliasChoices("q_mvar", "power_reactive", "load_power_reactive"),
    )
    constant_impedance: bool = False


# ─── SystemSpec ──────────────────────────────────────────────────────────────


class SystemSpec(_BaseSpecModel):
    """Complete power-system specification for a study."""

    base_mva: float = Field(
        default=100.0, validation_alias=AliasChoices("base_mva", "sbase", "base_mva"),
    )
    buses: list[BusSpec] = Field(default_factory=list)
    lines: list[LineSpec] = Field(
        default_factory=list, validation_alias=AliasChoices("lines", "branches"),
    )
    transformers: list[TransformerSpec] = Field(default_factory=list)
    generators: list[GeneratorSpec] = Field(default_factory=list)
    loads: list[LoadSpec] = Field(default_factory=list)

    @field_validator("base_mva")
    @classmethod
    def validate_base_mva(cls, v: float) -> float:
        """Base MVA must be positive and within a reasonable range (1–10000)."""
        if v <= 0:
            raise ValueError(f"base_mva must be positive, got {v}")
        if v > 10000:
            raise ValueError(f"base_mva is unreasonably large ({v}), max is 10000")
        return v


# ─── StudyRequest ────────────────────────────────────────────────────────────


# Full superset of allowed study types (API layer accepts all of these; the
# service layer may narrow the set at runtime based on USE_ETAP).
_ALLOWED_STUDY_TYPES: frozenset[str] = frozenset({
    "load_flow",
    "short_circuit",
    "fault",
    "arc_flash",
    "protection_coordination",
    "coordination",
    "motor_starting",
    "harmonic_analysis",
    "optimal_power_flow",
    "etap_load_flow",
    "etap_short_circuit",
    "etap_arc_flash",
    "etap_harmonic_analysis",
    "etap_optimal_power_flow",
    "etap_motor_starting",
    "etap_protection_coordination",
    # ETAP Expert skill — 6-step workflow with Format A/B/C/D responses
    "etap_expert",
    # ETAP GUI Agent — Computer Use Agent for desktop apps (ETAP, Revit, AutoCAD, etc.)
    "etap_gui",
})


class StudyRequest(_BaseSpecModel):
    """Request to run a power-system study."""

    study_type: str = Field(..., description="Type of study to run")
    system: SystemSpec | None = Field(
        default=None, validation_alias=AliasChoices("system", "system_spec"),
    )
    parameters: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    use_etap: bool = Field(
        default=False, description="If True, route to ETAP provider instead of native engine",
    )
    etap_project_path: str | None = None

    @field_validator("study_type")
    @classmethod
    def validate_study_type(cls, v: str) -> str:
        """Normalize and validate a study type string (load_flow/short_circuit/etc).

        Accepts the full superset of allowed types. If USE_ETAP=false at
        runtime, callers that want to reject ETAP-prefixed types should
        do so explicitly after validation.
        """
        v = v.lower().strip()
        if v not in _ALLOWED_STUDY_TYPES:
            raise ValueError(f"study_type must be one of {sorted(_ALLOWED_STUDY_TYPES)}")
        return v


# ─── StudyResult ─────────────────────────────────────────────────────────────


class StudyResult(_BaseSpecModel):
    """Result of a power-system study execution."""

    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_time_sec: float = 0.0
    trace_id: str = ""
    task_id: str | None = None
    study_type: str = ""
    provider: str = "native"

    @model_validator(mode="before")
    @classmethod
    def sync_data_and_results(cls, data: Any) -> Any:
        """Pydantic validator: coerce arbitrary data into JSON-safe form for storage."""
        if isinstance(data, dict):
            if "data" in data and "results" not in data:
                data["results"] = data["data"]
            elif "results" in data and "data" not in data:
                data["data"] = data["results"]
        return data


__all__ = [
    "BusSpec",
    "LineSpec",
    "TransformerSpec",
    "GeneratorSpec",
    "LoadSpec",
    "SystemSpec",
    "StudyRequest",
    "StudyResult",
]


# Silence flake8/ruff "imported but unused" for `os` if it's only used inside
# a docstring reference above. Currently unused; kept for future ETAP-gating.
_ = os
