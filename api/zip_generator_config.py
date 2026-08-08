"""
api/zip_generator_config.py — ZIP Load & Generator Capability Configuration API.

Provides CRUD endpoints for:
- ZIP load coefficients (aZ, aI, aP, bZ, bI, bP) and preset management
- Generator P-Q capability limits (max/min real & reactive power)

Exposes endpoints under the ``/api/v1/equipment/zip-generators`` prefix:

* ``GET    /zip-presets``                  — List available ZIP presets
* ``GET    /zip-loads``                   — List all configured ZIP loads
* ``POST   /zip-loads``                   — Create a new ZIP load config
* ``PUT    /zip-loads/{load_id}``         — Update a ZIP load config
* ``DELETE /zip-loads/{load_id}``         — Delete a ZIP load config
* ``POST   /zip-loads/{load_id}/preview`` — Calculate power at given voltage
* ``GET    /generators``                  — List all generator capability configs
* ``POST   /generators``                  — Create a new generator capability config
* ``PUT    /generators/{gen_id}``         — Update a generator capability config
* ``DELETE /generators/{gen_id}``         — Delete a generator capability config
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.dependencies import get_api_key
from core_model.zip_load import ZIP_PRESETS, ZIPCoefficients, ZIPLoadModel

import re as _re_for_log
_SAFE_LOG_RE = _re_for_log.compile(r"[\x00-\x1f\x7f]")


def _sanitize_for_log(value: object, max_len: int = 200) -> str:
    """Sanitize user-controlled input before writing to logs."""
    if value is None:
        return "None"
    s = _SAFE_LOG_RE.sub("_", str(value))
    if len(s) > max_len:
        s = s[:max_len] + "...[truncated]"
    return s
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_zip_loads: dict[str, dict[str, Any]] = {}
_generator_caps: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic models — ZIP Coefficients
# ---------------------------------------------------------------------------


class ZIPCoefficientsModel(BaseModel):
    """ZIP load model coefficients with validation that each group sums to 1.0.

    Attributes:
        aZ: Constant impedance fraction (active power).
        aI: Constant current fraction (active power).
        aP: Constant power fraction (active power).
        bZ: Constant impedance fraction (reactive power).
        bI: Constant current fraction (reactive power).
        bP: Constant power fraction (reactive power).
    """

    model_config = ConfigDict(strict=False)

    aZ: float = Field(default=0.0, ge=0.0, le=1.0, description="Constant impedance fraction (active power)")
    aI: float = Field(default=0.0, ge=0.0, le=1.0, description="Constant current fraction (active power)")
    aP: float = Field(default=1.0, ge=0.0, le=1.0, description="Constant power fraction (active power)")
    bZ: float = Field(default=0.0, ge=0.0, le=1.0, description="Constant impedance fraction (reactive power)")
    bI: float = Field(default=0.0, ge=0.0, le=1.0, description="Constant current fraction (reactive power)")
    bP: float = Field(default=1.0, ge=0.0, le=1.0, description="Constant power fraction (reactive power)")

    @model_validator(mode="after")
    def _validate_coefficient_sums(self) -> "ZIPCoefficientsModel":
        """Ensure active and reactive coefficient groups each sum to 1.0."""
        a_sum = self.aZ + self.aI + self.aP
        b_sum = self.bZ + self.bI + self.bP
        if abs(a_sum - 1.0) > 0.01:
            raise ValueError(f"Active power ZIP coefficients must sum to 1.0, got {a_sum:.4f}")
        if abs(b_sum - 1.0) > 0.01:
            raise ValueError(f"Reactive power ZIP coefficients must sum to 1.0, got {b_sum:.4f}")
        return self


# ---------------------------------------------------------------------------
# Pydantic models — ZIP Load Config
# ---------------------------------------------------------------------------


class ZIPLoadConfigCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/equipment/zip-generators/zip-loads``."""

    model_config = ConfigDict(strict=False)

    name: str = Field(min_length=1, max_length=255, description="Descriptive name for the ZIP load")
    p0: float = Field(gt=0.0, description="Nominal active power at rated voltage (per-unit)")
    q0: float = Field(default=0.0, description="Nominal reactive power at rated voltage (per-unit)")
    coefficients: Optional[ZIPCoefficientsModel] = Field(
        default=None, description="Custom ZIP coefficients (overrides preset)"
    )
    preset: Optional[str] = Field(
        default=None, description="Name of a preset ZIP model (e.g. 'constant_power')"
    )


class ZIPLoadConfigUpdateRequest(BaseModel):
    """Payload for ``PUT /api/v1/equipment/zip-generators/zip-loads/{load_id}``."""

    model_config = ConfigDict(strict=False)

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    p0: Optional[float] = Field(default=None, gt=0.0)
    q0: Optional[float] = None
    coefficients: Optional[ZIPCoefficientsModel] = None
    preset: Optional[str] = None


class ZIPLoadConfigResponse(BaseModel):
    """Public ZIP load configuration representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    p0: float
    q0: float
    coefficients: ZIPCoefficientsModel
    preset: Optional[str] = None


class ZIPLoadPreviewRequest(BaseModel):
    """Payload for ``POST /zip-loads/{load_id}/preview``."""

    model_config = ConfigDict(strict=False)

    voltage: float = Field(gt=0.0, description="Voltage magnitude in per-unit")


class ZIPLoadPreviewResponse(BaseModel):
    """ZIP load power calculation preview at a given voltage."""

    model_config = ConfigDict(from_attributes=True)

    load_id: str
    voltage: float
    p: float = Field(description="Active power at the given voltage")
    q: float = Field(description="Reactive power at the given voltage")


# ---------------------------------------------------------------------------
# Pydantic models — Generator Capability
# ---------------------------------------------------------------------------


class GeneratorCapabilityCreateRequest(BaseModel):
    """Payload for ``POST /api/v1/equipment/zip-generators/generators``."""

    model_config = ConfigDict(strict=False)

    name: str = Field(min_length=1, max_length=255, description="Descriptive name for the generator")
    max_power_real: float = Field(gt=0.0, description="Maximum real power output (per-unit)")
    max_power_reactive: float = Field(default=0.0, description="Maximum reactive power output (per-unit)")
    min_power_real: float = Field(default=0.0, description="Minimum real power output (per-unit)")
    min_power_reactive: float = Field(default=0.0, description="Minimum reactive power output (per-unit)")

    @model_validator(mode="after")
    def _validate_power_limits(self) -> "GeneratorCapabilityCreateRequest":
        """Ensure max limits are not less than min limits."""
        if self.max_power_real < self.min_power_real:
            raise ValueError(
                f"max_power_real ({self.max_power_real}) must be >= min_power_real ({self.min_power_real})"
            )
        if self.max_power_reactive < self.min_power_reactive:
            raise ValueError(
                f"max_power_reactive ({self.max_power_reactive}) must be >= "
                f"min_power_reactive ({self.min_power_reactive})"
            )
        return self


class GeneratorCapabilityUpdateRequest(BaseModel):
    """Payload for ``PUT /api/v1/equipment/zip-generators/generators/{gen_id}``."""

    model_config = ConfigDict(strict=False)

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    max_power_real: Optional[float] = Field(default=None, gt=0.0)
    max_power_reactive: Optional[float] = None
    min_power_real: Optional[float] = None
    min_power_reactive: Optional[float] = None


class GeneratorCapabilityResponse(BaseModel):
    """Public generator capability configuration representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    max_power_real: float
    max_power_reactive: float
    min_power_real: float
    min_power_reactive: float


# ---------------------------------------------------------------------------
# Pydantic models — Preset list
# ---------------------------------------------------------------------------


class ZIPPresetResponse(BaseModel):
    """Single ZIP preset entry."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    coefficients: ZIPCoefficientsModel


class ZIPPresetListResponse(BaseModel):
    """List of available ZIP presets."""

    model_config = ConfigDict(from_attributes=True)

    presets: list[ZIPPresetResponse]
    total: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/equipment/zip-generators",
    tags=["equipment", "zip-load", "generator"],
    dependencies=[Depends(get_api_key)],
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _resolve_coefficients(
    coefficients: Optional[ZIPCoefficientsModel],
    preset: Optional[str],
) -> ZIPCoefficientsModel:
    """Resolve ZIP coefficients from explicit values or a preset name.

    If *coefficients* is provided, it takes precedence. Otherwise, if *preset*
    is given, the coefficients are looked up from ``ZIP_PRESETS``. If neither
    is provided, the ``constant_power`` preset is used as default.
    """
    if coefficients is not None:
        return coefficients
    if preset is not None:
        if preset not in ZIP_PRESETS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown ZIP preset: {preset!r}. "
                f"Available presets: {', '.join(sorted(ZIP_PRESETS.keys()))}",
            )
        preset_coeffs = ZIP_PRESETS[preset]
        return ZIPCoefficientsModel(
            aZ=preset_coeffs.aZ,
            aI=preset_coeffs.aI,
            aP=preset_coeffs.aP,
            bZ=preset_coeffs.bZ,
            bI=preset_coeffs.bI,
            bP=preset_coeffs.bP,
        )
    # Default: constant power
    return ZIPCoefficientsModel()


def _get_zip_load_or_404(load_id: str) -> dict[str, Any]:
    """Retrieve a ZIP load from the in-memory store or raise 404."""
    if load_id not in _zip_loads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ZIP load not found: {load_id}",
        )
    return _zip_loads[load_id]


def _get_generator_cap_or_404(gen_id: str) -> dict[str, Any]:
    """Retrieve a generator capability from the in-memory store or raise 404."""
    if gen_id not in _generator_caps:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generator capability not found: {gen_id}",
        )
    return _generator_caps[gen_id]


# ---------------------------------------------------------------------------
# Endpoints — ZIP Presets
# ---------------------------------------------------------------------------


@router.get(
    "/zip-presets",
    response_model=ZIPPresetListResponse,
    summary="List available ZIP presets",
)
async def list_zip_presets() -> Any:
    """Return all available ZIP load model presets.

    Each preset includes the name and the six ZIP coefficients (aZ, aI, aP,
    bZ, bI, bP) that define the voltage-dependent load behaviour.
    """
    preset_list = []
    for name, coeffs in ZIP_PRESETS.items():
        preset_list.append(
            ZIPPresetResponse(
                name=name,
                coefficients=ZIPCoefficientsModel(
                    aZ=coeffs.aZ,
                    aI=coeffs.aI,
                    aP=coeffs.aP,
                    bZ=coeffs.bZ,
                    bI=coeffs.bI,
                    bP=coeffs.bP,
                ),
            )
        )
    return ZIPPresetListResponse(presets=preset_list, total=len(preset_list))


# ---------------------------------------------------------------------------
# Endpoints — ZIP Loads
# ---------------------------------------------------------------------------


@router.get(
    "/zip-loads",
    response_model=list[ZIPLoadConfigResponse],
    summary="List all configured ZIP loads",
)
async def list_zip_loads() -> Any:
    """Return all configured ZIP load entries."""
    return [
        ZIPLoadConfigResponse(
            id=data["id"],
            name=data["name"],
            p0=data["p0"],
            q0=data["q0"],
            coefficients=ZIPCoefficientsModel(**data["coefficients"]),
            preset=data.get("preset"),
        )
        for data in _zip_loads.values()
    ]


@router.post(
    "/zip-loads",
    response_model=ZIPLoadConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ZIP load config",
)
async def create_zip_load(body: ZIPLoadConfigCreateRequest) -> Any:
    """Create a new ZIP load configuration.

    The coefficients can be specified directly or by referencing a preset
    name. If both are provided, the explicit coefficients take precedence.
    If neither is given, the ``constant_power`` preset is used.
    """
    coefficients = _resolve_coefficients(body.coefficients, body.preset)
    load_id = str(uuid.uuid4())
    entry: dict[str, Any] = {
        "id": load_id,
        "name": body.name,
        "p0": body.p0,
        "q0": body.q0,
        "coefficients": coefficients.model_dump(),
        "preset": body.preset if body.coefficients is None else None,
    }
    _zip_loads[load_id] = entry
    logger.info("zip_load_created id=%s name=%s", _sanitize_for_log(load_id), _sanitize_for_log(body.name))
    return ZIPLoadConfigResponse(
        id=load_id,
        name=body.name,
        p0=body.p0,
        q0=body.q0,
        coefficients=coefficients,
        preset=entry["preset"],
    )


@router.put(
    "/zip-loads/{load_id}",
    response_model=ZIPLoadConfigResponse,
    summary="Update a ZIP load config",
)
async def update_zip_load(load_id: str, body: ZIPLoadConfigUpdateRequest) -> Any:
    """Update an existing ZIP load configuration.

    Only fields that are explicitly provided in the request body will be
    modified. Omitted fields retain their current values.
    """
    existing = _get_zip_load_or_404(load_id)

    # Merge updated fields
    if body.name is not None:
        existing["name"] = body.name
    if body.p0 is not None:
        existing["p0"] = body.p0
    if body.q0 is not None:
        existing["q0"] = body.q0

    # Resolve coefficients: if both are None, keep existing
    if body.coefficients is not None or body.preset is not None:
        new_coefficients = _resolve_coefficients(
            body.coefficients,
            body.preset,
        )
        existing["coefficients"] = new_coefficients.model_dump()
        existing["preset"] = body.preset if body.coefficients is None else None

    logger.info("zip_load_updated id=%s", _sanitize_for_log(load_id))
    return ZIPLoadConfigResponse(
        id=existing["id"],
        name=existing["name"],
        p0=existing["p0"],
        q0=existing["q0"],
        coefficients=ZIPCoefficientsModel(**existing["coefficients"]),
        preset=existing.get("preset"),
    )


@router.delete(
    "/zip-loads/{load_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a ZIP load config",
)
async def delete_zip_load(load_id: str) -> None:
    """Delete a ZIP load configuration by ID."""
    _get_zip_load_or_404(load_id)
    del _zip_loads[load_id]
    logger.info("zip_load_deleted id=%s", _sanitize_for_log(load_id))


@router.post(
    "/zip-loads/{load_id}/preview",
    response_model=ZIPLoadPreviewResponse,
    summary="Calculate power at given voltage for preview",
)
async def preview_zip_load(load_id: str, body: ZIPLoadPreviewRequest) -> Any:
    """Calculate the active and reactive power of a ZIP load at a given voltage.

    Uses the ZIP load model formula:
        P = P0 * (aZ * V^2 + aI * V + aP)
        Q = Q0 * (bZ * V^2 + bI * V + bP)
    """
    data = _get_zip_load_or_404(load_id)
    coeffs_dict = data["coefficients"]
    coeffs = ZIPCoefficients(
        aZ=coeffs_dict["aZ"],
        aI=coeffs_dict["aI"],
        aP=coeffs_dict["aP"],
        bZ=coeffs_dict["bZ"],
        bI=coeffs_dict["bI"],
        bP=coeffs_dict["bP"],
    )
    model = ZIPLoadModel(p0=data["p0"], q0=data["q0"], coefficients=coeffs)
    p, q = model.calculate_power(body.voltage)
    return ZIPLoadPreviewResponse(load_id=load_id, voltage=body.voltage, p=p, q=q)


# ---------------------------------------------------------------------------
# Endpoints — Generator Capability
# ---------------------------------------------------------------------------


@router.get(
    "/generators",
    response_model=list[GeneratorCapabilityResponse],
    summary="List all generator capability configs",
)
async def list_generators() -> Any:
    """Return all configured generator P-Q capability limits."""
    return [
        GeneratorCapabilityResponse(
            id=data["id"],
            name=data["name"],
            max_power_real=data["max_power_real"],
            max_power_reactive=data["max_power_reactive"],
            min_power_real=data["min_power_real"],
            min_power_reactive=data["min_power_reactive"],
        )
        for data in _generator_caps.values()
    ]


@router.post(
    "/generators",
    response_model=GeneratorCapabilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new generator capability config",
)
async def create_generator(body: GeneratorCapabilityCreateRequest) -> Any:
    """Create a new generator P-Q capability configuration.

    Defines the real and reactive power limits for a generator.
    """
    gen_id = str(uuid.uuid4())
    entry: dict[str, Any] = {
        "id": gen_id,
        "name": body.name,
        "max_power_real": body.max_power_real,
        "max_power_reactive": body.max_power_reactive,
        "min_power_real": body.min_power_real,
        "min_power_reactive": body.min_power_reactive,
    }
    _generator_caps[gen_id] = entry
    logger.info("generator_capability_created id=%s name=%s", _sanitize_for_log(gen_id), _sanitize_for_log(body.name))
    return GeneratorCapabilityResponse(
        id=gen_id,
        name=body.name,
        max_power_real=body.max_power_real,
        max_power_reactive=body.max_power_reactive,
        min_power_real=body.min_power_real,
        min_power_reactive=body.min_power_reactive,
    )


@router.put(
    "/generators/{gen_id}",
    response_model=GeneratorCapabilityResponse,
    summary="Update a generator capability config",
)
async def update_generator(gen_id: str, body: GeneratorCapabilityUpdateRequest) -> Any:
    """Update an existing generator P-Q capability configuration.

    Only fields that are explicitly provided in the request body will be
    modified. Omitted fields retain their current values.
    """
    existing = _get_generator_cap_or_404(gen_id)

    # Merge updated fields
    if body.name is not None:
        existing["name"] = body.name
    if body.max_power_real is not None:
        existing["max_power_real"] = body.max_power_real
    if body.max_power_reactive is not None:
        existing["max_power_reactive"] = body.max_power_reactive
    if body.min_power_real is not None:
        existing["min_power_real"] = body.min_power_real
    if body.min_power_reactive is not None:
        existing["min_power_reactive"] = body.min_power_reactive

    # Validate that max >= min after merge
    if existing["max_power_real"] < existing["min_power_real"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"max_power_real ({existing['max_power_real']}) must be >= "
            f"min_power_real ({existing['min_power_real']})",
        )
    if existing["max_power_reactive"] < existing["min_power_reactive"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"max_power_reactive ({existing['max_power_reactive']}) must be >= "
            f"min_power_reactive ({existing['min_power_reactive']})",
        )

    logger.info("generator_capability_updated id=%s", _sanitize_for_log(gen_id))
    return GeneratorCapabilityResponse(
        id=existing["id"],
        name=existing["name"],
        max_power_real=existing["max_power_real"],
        max_power_reactive=existing["max_power_reactive"],
        min_power_real=existing["min_power_real"],
        min_power_reactive=existing["min_power_reactive"],
    )


@router.delete(
    "/generators/{gen_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a generator capability config",
)
async def delete_generator(gen_id: str) -> None:
    """Delete a generator P-Q capability configuration by ID."""
    _get_generator_cap_or_404(gen_id)
    del _generator_caps[gen_id]
    logger.info("generator_capability_deleted id=%s", gen_id)
