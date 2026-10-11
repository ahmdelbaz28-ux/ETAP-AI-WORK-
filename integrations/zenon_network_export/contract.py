"""Zenon Network Export v1 Contract Schema.

Strict Pydantic models for importing electrical topology and parameters exported
from ABB/COPA-DATA zenon SCADA / Energy Edition.

Rule: Missing electrical values are declared explicitly as None.
Synthetic or assumed defaults are strictly forbidden in production.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ZenonProjectMetadata(BaseModel):
    """Metadata describing the zenon export project."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1, max_length=256)
    version: Optional[str] = Field(default=None)
    export_timestamp: Optional[str] = Field(default=None)
    substation_name: Optional[str] = Field(default=None)
    system_frequency_hz: Optional[float] = Field(default=None)
    base_mva: Optional[float] = Field(default=None)
    source_system: str = Field(default="zenon")
    author: Optional[str] = Field(default=None)


class ZenonElementBase(BaseModel):
    """Base class for any electrical element extracted from zenon."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=128)
    source_ref: Optional[str] = Field(default=None, description="zenon Variable or Tag path")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ZenonBus(ZenonElementBase):
    """Substation busbar or junction node."""

    base_kv: Optional[float] = Field(default=None, description="Nominal line-to-line kV")
    kv: Optional[float] = Field(default=None, description="Alternative voltage specification")
    v_mag: Optional[float] = Field(default=None, description="Measured or operating voltage magnitude in pu")
    v_ang: Optional[float] = Field(default=None, description="Voltage angle in degrees")
    bus_type: Optional[str] = Field(default=None, description="slack, pv, or pq")


class ZenonLine(ZenonElementBase):
    """Overhead transmission or distribution line."""

    from_bus: str = Field(..., min_length=1)
    to_bus: str = Field(..., min_length=1)
    r_pu: Optional[float] = Field(default=None, description="Positive sequence resistance in pu")
    x_pu: Optional[float] = Field(default=None, description="Positive sequence reactance in pu")
    b_pu: Optional[float] = Field(default=None, description="Positive sequence susceptance in pu")
    length_km: Optional[float] = Field(default=None, description="Physical line length in km")
    rating_mva: Optional[float] = Field(default=None, description="Continuous thermal rating MVA")
    rating_a: Optional[float] = Field(default=None, description="Continuous thermal rating Amperes")


class ZenonCable(ZenonElementBase):
    """Underground or insulated cable feeder."""

    from_bus: str = Field(..., min_length=1)
    to_bus: str = Field(..., min_length=1)
    r_pu: Optional[float] = Field(default=None)
    x_pu: Optional[float] = Field(default=None)
    b_pu: Optional[float] = Field(default=None)
    length_km: Optional[float] = Field(default=None)
    rating_a: Optional[float] = Field(default=None)
    conductor_material: Optional[str] = Field(default=None, description="Cu or Al")


class ZenonTransformer(ZenonElementBase):
    """Two-winding or power transformer."""

    from_bus: str = Field(..., min_length=1, description="Primary bus ID")
    to_bus: str = Field(..., min_length=1, description="Secondary bus ID")
    rating_mva: Optional[float] = Field(default=None, description="Rated power MVA")
    prim_kv: Optional[float] = Field(default=None, description="Primary rated kV")
    sec_kv: Optional[float] = Field(default=None, description="Secondary rated kV")
    r_pu: Optional[float] = Field(default=None, description="Short-circuit resistance in pu")
    x_pu: Optional[float] = Field(default=None, description="Short-circuit reactance in pu")
    tap_ratio: Optional[float] = Field(default=None, description="Off-nominal tap ratio")
    vector_group: Optional[str] = Field(default=None, description="e.g. Dyn11, YNd1")


class ZenonBreaker(ZenonElementBase):
    """Substation circuit breaker (XCBR)."""

    bus: Optional[str] = Field(default=None)
    from_bus: Optional[str] = Field(default=None)
    to_bus: Optional[str] = Field(default=None)
    status: Optional[Literal["normal_open", "normal_closed", "open", "closed"]] = Field(default=None)
    rated_a: Optional[float] = Field(default=None, description="Continuous rated current in A")
    breaking_capacity_ka: Optional[float] = Field(default=None, description="Rated short-circuit breaking current kA")


class ZenonSwitch(ZenonElementBase):
    """Disconnect switch or disconnector (XSWI)."""

    bus: Optional[str] = Field(default=None)
    from_bus: Optional[str] = Field(default=None)
    to_bus: Optional[str] = Field(default=None)
    status: Optional[Literal["normal_open", "normal_closed", "open", "closed"]] = Field(default=None)
    rated_a: Optional[float] = Field(default=None)


class ZenonLoad(ZenonElementBase):
    """Lumped consumer or industrial load."""

    bus: str = Field(..., min_length=1)
    p_mw: Optional[float] = Field(default=None, description="Active power in MW")
    q_mvar: Optional[float] = Field(default=None, description="Reactive power in Mvar")
    model: Optional[str] = Field(default=None, description="constant_power, constant_current, or constant_impedance")
    status: Optional[Literal["connected", "disconnected"]] = Field(default=None)


class ZenonGenerator(ZenonElementBase):
    """Synchronous or inverter-based generator."""

    bus: str = Field(..., min_length=1)
    p_mw: Optional[float] = Field(default=None, description="Active power in MW")
    q_mvar: Optional[float] = Field(default=None, description="Reactive power in Mvar")
    rating_mva: Optional[float] = Field(default=None, description="Nameplate MVA rating")
    v_setpoint: Optional[float] = Field(default=None, description="Voltage setpoint in pu")
    q_min: Optional[float] = Field(default=None, description="Minimum reactive power Mvar")
    q_max: Optional[float] = Field(default=None, description="Maximum reactive power Mvar")
    status: Optional[Literal["connected", "disconnected"]] = Field(default=None)


class ZenonMotor(ZenonElementBase):
    """Induction or synchronous motor."""

    bus: str = Field(..., min_length=1)
    rated_kw: Optional[float] = Field(default=None, description="Mechanical rating in kW")
    rated_kv: Optional[float] = Field(default=None)
    pf: Optional[float] = Field(default=None, description="Power factor (0.0 to 1.0)")
    efficiency: Optional[float] = Field(default=None, description="Efficiency percentage (0 to 100)")
    status: Optional[Literal["connected", "disconnected"]] = Field(default=None)


class ZenonRelay(ZenonElementBase):
    """Protection relay parameter block (PTOC/PDIS)."""

    bus: str = Field(..., min_length=1)
    protected_element: Optional[str] = Field(default=None, description="Line, XFMR, or Bus ID protected")
    curve_type: Optional[str] = Field(default=None, description="IEC Standard Inverse, Very Inverse, IEEE Extremely Inverse")
    time_dial: Optional[float] = Field(default=None, description="Time dial multiplier (TMS)")
    pickup_a: Optional[float] = Field(default=None, description="Pickup current in Amperes")


class ZenonCapacitor(ZenonElementBase):
    """Shunt capacitor bank."""

    bus: str = Field(..., min_length=1)
    q_mvar: Optional[float] = Field(default=None, description="Rated capacitive Mvar")
    rated_kv: Optional[float] = Field(default=None)
    status: Optional[Literal["connected", "disconnected"]] = Field(default=None)


class ZenonReactor(ZenonElementBase):
    """Series or shunt reactor."""

    bus: Optional[str] = Field(default=None)
    from_bus: Optional[str] = Field(default=None)
    to_bus: Optional[str] = Field(default=None)
    x_pu: Optional[float] = Field(default=None, description="Reactance in pu")
    rating_mva: Optional[float] = Field(default=None)
    status: Optional[Literal["connected", "disconnected"]] = Field(default=None)


class ZenonSource(ZenonElementBase):
    """Utility grid equivalent infeed source."""

    bus: str = Field(..., min_length=1)
    base_kv: Optional[float] = Field(default=None)
    s_sc_mva: Optional[float] = Field(default=None, description="Short-circuit MVA")
    rx_ratio: Optional[float] = Field(default=None, description="R/X impedance ratio")
    status: Optional[Literal["connected", "disconnected"]] = Field(default=None)


class ZenonNetworkExport(BaseModel):
    """Root contract for Zenon Network Export v1 (JSON)."""

    model_config = ConfigDict(extra="ignore")

    contract_version: str = Field(default="1.0.0")
    project: ZenonProjectMetadata
    buses: list[ZenonBus] = Field(default_factory=list)
    lines: list[ZenonLine] = Field(default_factory=list)
    cables: list[ZenonCable] = Field(default_factory=list)
    transformers: list[ZenonTransformer] = Field(default_factory=list)
    breakers: list[ZenonBreaker] = Field(default_factory=list)
    switches: list[ZenonSwitch] = Field(default_factory=list)
    loads: list[ZenonLoad] = Field(default_factory=list)
    generators: list[ZenonGenerator] = Field(default_factory=list)
    motors: list[ZenonMotor] = Field(default_factory=list)
    relays: list[ZenonRelay] = Field(default_factory=list)
    capacitors: list[ZenonCapacitor] = Field(default_factory=list)
    reactors: list[ZenonReactor] = Field(default_factory=list)
    sources: list[ZenonSource] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
