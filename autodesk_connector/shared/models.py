"""
Unified Engineering Model — Python Dataclass Implementation
============================================================
Pydantic models for the Unified Engineering Model schema,
shared across ETAP, AutoCAD, Revit, and the AI copilot.
"""

from __future__ import annotations

import uuid
<<<<<<< HEAD
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
import contextlib
from typing import Any, Optional
=======
from datetime import UTC, datetime

UTC = UTC
from typing import Any, Dict, List
>>>>>>> origin/fix/scenario-tests-properly

from pydantic import BaseModel, Field

from compat import StrEnum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceSystem(StrEnum):
    ETAP = "etap"
    AUTOCAD = "autocad"
    REVIT = "revit"
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"


class RelationshipType(StrEnum):
    CONNECTED_TO = "connected_to"
    FEEDS = "feeds"
    PROTECTED_BY = "protected_by"
    LOCATED_IN = "located_in"
    SUPPLIES = "supplies"
    CONTAINS = "contains"
    REFERENCES = "references"
    SYNCHRONIZED_WITH = "synchronized_with"


class BusType(StrEnum):
    SLACK = "slack"
    PV = "pv"
    PQ = "pq"
    SWING = "swing"


class TransformerType(StrEnum):
    STEP_UP = "step_up"
    STEP_DOWN = "step_down"
    ISOLATION = "isolation"
    AUTO = "auto"
    DISTRIBUTION = "distribution"
    POWER = "power"
    INSTRUMENT = "instrument"


class GeneratorType(StrEnum):
    SYNCHRONOUS = "synchronous"
    INDUCTION = "induction"
    INVERTER = "inverter"
    DIESEL = "diesel"
    GAS_TURBINE = "gas_turbine"
    STEAM = "steam"
    HYDRO = "hydro"
    WIND = "wind"
    SOLAR_PV = "solar_pv"
    BATTERY_STORAGE = "battery_storage"


class LoadType(StrEnum):
    CONSTANT_POWER = "constant_power"
    CONSTANT_IMPEDANCE = "constant_impedance"
    CONSTANT_CURRENT = "constant_current"
    MOTOR = "motor"
    LIGHTING = "lighting"
    HVAC = "hvac"
    RECEPTACLE = "receptacle"
    ELEVATOR = "elevator"
    PUMP = "pump"
    COMPRESSOR = "compressor"
    WELDER = "welder"
    DATA_CENTER = "data_center"
    GENERIC = "generic"


class PanelType(StrEnum):
    MDP = "MDP"
    SP = "SP"
    DP = "DP"
    LP = "LP"
    CP = "CP"
    AHUB = "AHUB"
    MCC = "MCC"
    POWER_PANEL = "POWER_PANEL"
    LIGHTING_PANEL = "LIGHTING_PANEL"
    SUB_PANEL = "SUB_PANEL"


class BreakerType(StrEnum):
    MCCB = "mccb"
    ACB = "acb"
    MCB = "mcb"
    VCB = "vcb"
    SF6 = "sf6"
    AIR_BLAST = "air_blast"
    OIL = "oil"
    MOLDED_CASE = "molded_case"
    INSULATED_CASE = "insulated_case"
    LOAD_BREAK_SWITCH = "load_break_switch"


class RelayType(StrEnum):
    OVERCURRENT = "overcurrent"
    DISTANCE = "distance"
    DIFFERENTIAL = "differential"
    VOLTAGE = "voltage"
    FREQUENCY = "frequency"
    DIRECTIONAL = "directional"
    PILOT = "pilot"
    RECLOSER = "recloser"


class CableType(StrEnum):
    POWER = "power"
    CONTROL = "control"
    INSTRUMENTATION = "instrumentation"
    MEDIUM_VOLTAGE = "medium_voltage"
    LOW_VOLTAGE = "low_voltage"
    FIBER_OPTIC = "fiber_optic"


class MotorType(StrEnum):
    INDUCTION = "induction"
    SYNCHRONOUS = "synchronous"
    DC = "dc"
    SERVO = "servo"
    STEPPER = "stepper"


class Standard(StrEnum):
    IEC = "IEC"
    ANSI = "ANSI"
    IEEE = "IEEE"
    BS = "BS"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------


class Coordinates(BaseModel):
    x: float
    y: float
    z: float = 0.0


class Relationship(BaseModel):
    type: RelationshipType
    target_id: str
    target_type: str
<<<<<<< HEAD
    metadata: dict[str, Any] = Field(default_factory=dict)
=======
    metadata: Dict[str, Any] = Field(default_factory=dict)
>>>>>>> origin/fix/scenario-tests-properly


class BaseEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
<<<<<<< HEAD
    coordinates: Optional[Coordinates] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    relationships: list[Relationship] = Field(default_factory=list)
=======
    coordinates: Coordinates | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relationships: List[Relationship] = Field(default_factory=list)
>>>>>>> origin/fix/scenario-tests-properly
    source_system: SourceSystem = SourceSystem.MANUAL
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Project(BaseEntity):
    entity_type: str = "project"
<<<<<<< HEAD
    buildings: list[Building] = Field(default_factory=list)
    electrical_rooms: list[ElectricalRoom] = Field(default_factory=list)
    panels: list[Panel] = Field(default_factory=list)
    switchboards: list[Switchboard] = Field(default_factory=list)
=======
    buildings: List[Building] = Field(default_factory=list)
    electrical_rooms: List[ElectricalRoom] = Field(default_factory=list)
    panels: List[Panel] = Field(default_factory=list)
    switchboards: List[Switchboard] = Field(default_factory=list)
>>>>>>> origin/fix/scenario-tests-properly
    base_mva: float = 100.0
    frequency_hz: float = 60.0
    standard: Standard = Standard.IEC


class Building(BaseEntity):
    entity_type: str = "building"
<<<<<<< HEAD
    levels: list[Level] = Field(default_factory=list)
    address: str = ""
    total_area_sqm: Optional[float] = None
=======
    levels: List[Level] = Field(default_factory=list)
    address: str = ""
    total_area_sqm: float | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Level(BaseEntity):
    entity_type: str = "level"
<<<<<<< HEAD
    elevation_m: Optional[float] = None
    height_m: Optional[float] = None
    rooms: list[Room] = Field(default_factory=list)
    building_id: Optional[str] = None
=======
    elevation_m: float | None = None
    height_m: float | None = None
    rooms: List[Room] = Field(default_factory=list)
    building_id: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Room(BaseEntity):
    entity_type: str = "room"
<<<<<<< HEAD
    area_sqm: Optional[float] = None
    volume_m3: Optional[float] = None
    level_id: Optional[str] = None
    electrical_rooms: list[ElectricalRoom] = Field(default_factory=list)
=======
    area_sqm: float | None = None
    volume_m3: float | None = None
    level_id: str | None = None
    electrical_rooms: List[ElectricalRoom] = Field(default_factory=list)
>>>>>>> origin/fix/scenario-tests-properly


class ElectricalRoom(BaseEntity):
    entity_type: str = "electrical_room"
<<<<<<< HEAD
    room_id: Optional[str] = None
    equipment: list[Equipment] = Field(default_factory=list)
    panels: list[Panel] = Field(default_factory=list)
    cable_trays: list[Tray] = Field(default_factory=list)
    clearance_mm: float = 1100
    ventilation_type: Optional[str] = None
=======
    room_id: str | None = None
    equipment: List[Equipment] = Field(default_factory=list)
    panels: List[Panel] = Field(default_factory=list)
    cable_trays: List[Tray] = Field(default_factory=list)
    clearance_mm: float = 1100
    ventilation_type: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Panel(BaseEntity):
    entity_type: str = "panel"
    panel_type: PanelType
    voltage_nominal_v: float
    phase_count: int = 3
    wire_count: int = 3
<<<<<<< HEAD
    main_breaker_a: Optional[float] = None
    bus_rating_a: Optional[float] = None
    interrupting_rating_ka: Optional[float] = None
    feeders: list[BreakerDef] = Field(default_factory=list)
    feed_from: Optional[Relationship] = None
    location: Optional[Coordinates] = None
    mounting: Optional[str] = None
    enclosure_type: Optional[str] = None
=======
    main_breaker_a: float | None = None
    bus_rating_a: float | None = None
    interrupting_rating_ka: float | None = None
    feeders: List[BreakerDef] = Field(default_factory=list)
    feed_from: Relationship | None = None
    location: Coordinates | None = None
    mounting: str | None = None
    enclosure_type: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


class BreakerDef(BaseModel):
    """Lightweight breaker definition used inside Panel feeders."""

    breaker_id: str
    rated_current_a: float
    poles: int = 3
<<<<<<< HEAD
    load_name: Optional[str] = None
    load_kw: Optional[float] = None
=======
    load_name: str | None = None
    load_kw: float | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Switchboard(BaseEntity):
    entity_type: str = "switchboard"
<<<<<<< HEAD
    voltage_nominal_v: Optional[float] = None
    bus_rating_a: Optional[float] = None
    interrupting_rating_ka: Optional[float] = None
    main_breaker_a: Optional[float] = None
    sections: list[Equipment] = Field(default_factory=list)
    feeders: list[BreakerDef] = Field(default_factory=list)
=======
    voltage_nominal_v: float | None = None
    bus_rating_a: float | None = None
    interrupting_rating_ka: float | None = None
    main_breaker_a: float | None = None
    sections: List[Equipment] = Field(default_factory=list)
    feeders: List[BreakerDef] = Field(default_factory=list)
>>>>>>> origin/fix/scenario-tests-properly


class Bus(BaseEntity):
    entity_type: str = "bus"
    bus_type: BusType = BusType.PQ
    voltage_magnitude_pu: float = 1.0
    voltage_angle_deg: float = 0.0
    base_kv: float
<<<<<<< HEAD
    nominal_kv: Optional[float] = None
=======
    nominal_kv: float | None = None
>>>>>>> origin/fix/scenario-tests-properly
    load_mw: float = 0.0
    load_mvar: float = 0.0
    gen_mw: float = 0.0
    gen_mvar: float = 0.0
    q_min_mvar: float = -999.0
    q_max_mvar: float = 999.0
<<<<<<< HEAD
    substation_id: Optional[str] = None
    zone: Optional[str] = None
    area: Optional[str] = None
=======
    substation_id: str | None = None
    zone: str | None = None
    area: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Transformer(BaseEntity):
    entity_type: str = "transformer"
    transformer_type: TransformerType = TransformerType.DISTRIBUTION
    from_bus_id: str
    to_bus_id: str
    rated_power_mva: float
<<<<<<< HEAD
    primary_voltage_kv: Optional[float] = None
    secondary_voltage_kv: Optional[float] = None
    impedance_percent: Optional[float] = None
    xr_ratio: Optional[float] = None
    winding_config: Optional[str] = None
    tap_ratio: float = 1.0
    phase_shift_deg: float = 0.0
    cooling_type: Optional[str] = None
    vector_group: Optional[str] = None
=======
    primary_voltage_kv: float | None = None
    secondary_voltage_kv: float | None = None
    impedance_percent: float | None = None
    xr_ratio: float | None = None
    winding_config: str | None = None
    tap_ratio: float = 1.0
    phase_shift_deg: float = 0.0
    cooling_type: str | None = None
    vector_group: str | None = None
>>>>>>> origin/fix/scenario-tests-properly
    r1_pu: float = 0.0
    x1_pu: float = 0.0
    r0_pu: float = 0.0
    x0_pu: float = 0.0


class Generator(BaseEntity):
    entity_type: str = "generator"
    generator_type: GeneratorType = GeneratorType.SYNCHRONOUS
    bus_id: str
<<<<<<< HEAD
    rated_power_mva: Optional[float] = None
    rated_power_mw: float
    power_factor: float = 0.85
    internal_voltage_pu: float = 1.0
    xd_percent: Optional[float] = None
    xd_prime_percent: Optional[float] = None
    xd_second_percent: Optional[float] = None
    max_p_mw: Optional[float] = None
    min_p_mw: float = 0.0
    max_q_mvar: Optional[float] = None
    min_q_mvar: float = 0.0
    fuel_type: Optional[str] = None
    excitation_type: Optional[str] = None
    governor_type: Optional[str] = None
=======
    rated_power_mva: float | None = None
    rated_power_mw: float
    power_factor: float = 0.85
    internal_voltage_pu: float = 1.0
    xd_percent: float | None = None
    xd_prime_percent: float | None = None
    xd_second_percent: float | None = None
    max_p_mw: float | None = None
    min_p_mw: float = 0.0
    max_q_mvar: float | None = None
    min_q_mvar: float = 0.0
    fuel_type: str | None = None
    excitation_type: str | None = None
    governor_type: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Cable(BaseEntity):
    entity_type: str = "cable"
    cable_type: CableType = CableType.POWER
    from_bus_id: str
    to_bus_id: str
    length_m: float
<<<<<<< HEAD
    conductor_size_mm2: Optional[float] = None
    conductor_material: str = "copper"
    insulation_type: Optional[str] = None
    voltage_rating_kv: Optional[float] = None
    ampacity_a: Optional[float] = None
    r_ohm_per_km: float = 0.0
    x_ohm_per_km: float = 0.0
    r0_ohm_per_km: Optional[float] = None
    x0_ohm_per_km: Optional[float] = None
    number_of_cores: int = 3
    installation_method: Optional[str] = None
    cable_tray_id: Optional[str] = None
    conduit_id: Optional[str] = None
    routing_path: list[Coordinates] = Field(default_factory=list)
=======
    conductor_size_mm2: float | None = None
    conductor_material: str = "copper"
    insulation_type: str | None = None
    voltage_rating_kv: float | None = None
    ampacity_a: float | None = None
    r_ohm_per_km: float = 0.0
    x_ohm_per_km: float = 0.0
    r0_ohm_per_km: float | None = None
    x0_ohm_per_km: float | None = None
    number_of_cores: int = 3
    installation_method: str | None = None
    cable_tray_id: str | None = None
    conduit_id: str | None = None
    routing_path: List[Coordinates] = Field(default_factory=list)
>>>>>>> origin/fix/scenario-tests-properly


class Load(BaseEntity):
    entity_type: str = "load"
    load_type: LoadType = LoadType.CONSTANT_POWER
    bus_id: str
    rated_power_kw: float
<<<<<<< HEAD
    rated_power_kva: Optional[float] = None
    power_factor: float = 0.85
    voltage_v: Optional[float] = None
=======
    rated_power_kva: float | None = None
    power_factor: float = 0.85
    voltage_v: float | None = None
>>>>>>> origin/fix/scenario-tests-properly
    phase_count: int = 3
    demand_factor: float = 1.0
    diversity_factor: float = 1.0
    load_category: str = "normal"
    is_interruptible: bool = False
<<<<<<< HEAD
    zip_model: dict[str, float] | None = None
=======
    zip_model: Dict[str, float] | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Motor(BaseEntity):
    entity_type: str = "motor"
    motor_type: MotorType = MotorType.INDUCTION
    bus_id: str
    rated_power_kw: float
    rated_voltage_v: float = 400.0
<<<<<<< HEAD
    rated_speed_rpm: Optional[float] = None
    starting_method: str = "across_the_line"
    starting_current_multiplier: float = 6.0
    efficiency_percent: Optional[float] = None
    power_factor: float = 0.85
    locked_rotor_current_a: Optional[float] = None
    full_load_current_a: Optional[float] = None
    acceleration_time_sec: Optional[float] = None
    load_type: Optional[str] = None
    load_inertia_kgm2: Optional[float] = None
    breaker_id: Optional[str] = None
=======
    rated_speed_rpm: float | None = None
    starting_method: str = "across_the_line"
    starting_current_multiplier: float = 6.0
    efficiency_percent: float | None = None
    power_factor: float = 0.85
    locked_rotor_current_a: float | None = None
    full_load_current_a: float | None = None
    acceleration_time_sec: float | None = None
    load_type: str | None = None
    load_inertia_kgm2: float | None = None
    breaker_id: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Breaker(BaseEntity):
    entity_type: str = "breaker"
    breaker_type: BreakerType = BreakerType.MCCB
    rated_current_a: float
    interrupting_rating_ka: float
<<<<<<< HEAD
    voltage_rating_kv: Optional[float] = None
    poles: int = 3
    frame_size_a: Optional[float] = None
    trip_unit_type: Optional[str] = None
    trip_curve: str = "C"
    bus_id: Optional[str] = None
    panel_id: Optional[str] = None
    feeder_number: Optional[int] = None
    load_id: Optional[str] = None
=======
    voltage_rating_kv: float | None = None
    poles: int = 3
    frame_size_a: float | None = None
    trip_unit_type: str | None = None
    trip_curve: str = "C"
    bus_id: str | None = None
    panel_id: str | None = None
    feeder_number: int | None = None
    load_id: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Relay(BaseEntity):
    entity_type: str = "relay"
    relay_type: RelayType = RelayType.OVERCURRENT
    relay_curve: str = "iec_standard_inverse"
    pickup_a: float
    time_dial: float = 0.1
    ct_ratio: float = 1.0
<<<<<<< HEAD
    bus_id: Optional[str] = None
    breaker_id: Optional[str] = None
    instantaneous_pickup_a: Optional[float] = None
    phase_count: int = 3
    function_numbers: list[int] = Field(default_factory=lambda: [50, 51])
=======
    bus_id: str | None = None
    breaker_id: str | None = None
    instantaneous_pickup_a: float | None = None
    phase_count: int = 3
    function_numbers: List[int] = Field(default_factory=lambda: [50, 51])
>>>>>>> origin/fix/scenario-tests-properly


class ProtectionDevice(BaseEntity):
    entity_type: str = "protection_device"
    device_category: str
<<<<<<< HEAD
    rated_voltage_kv: Optional[float] = None
    continuous_current_a: Optional[float] = None
    interrupting_current_ka: Optional[float] = None
    bus_id: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    settings: dict[str, Any] = Field(default_factory=dict)
=======
    rated_voltage_kv: float | None = None
    continuous_current_a: float | None = None
    interrupting_current_ka: float | None = None
    bus_id: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    settings: Dict[str, Any] = Field(default_factory=dict)
>>>>>>> origin/fix/scenario-tests-properly


class Conduit(BaseEntity):
    entity_type: str = "conduit"
    conduit_type: str = "rmc"
    diameter_mm: float
<<<<<<< HEAD
    wall_thickness_mm: Optional[float] = None
    length_m: float
    fill_percent: float = 0.0
    cable_ids: list[str] = Field(default_factory=list)
    from_point: Optional[Coordinates] = None
    to_point: Optional[Coordinates] = None
    routing_path: list[Coordinates] = Field(default_factory=list)
=======
    wall_thickness_mm: float | None = None
    length_m: float
    fill_percent: float = 0.0
    cable_ids: List[str] = Field(default_factory=list)
    from_point: Coordinates | None = None
    to_point: Coordinates | None = None
    routing_path: List[Coordinates] = Field(default_factory=list)
>>>>>>> origin/fix/scenario-tests-properly


class Tray(BaseEntity):
    entity_type: str = "tray"
    tray_type: str = "ladder"
    width_mm: float
<<<<<<< HEAD
    height_mm: Optional[float] = None
    length_m: float
    fill_percent: float = 0.0
    cable_ids: list[str] = Field(default_factory=list)
    routing_path: list[Coordinates] = Field(default_factory=list)
=======
    height_mm: float | None = None
    length_m: float
    fill_percent: float = 0.0
    cable_ids: List[str] = Field(default_factory=list)
    routing_path: List[Coordinates] = Field(default_factory=list)
>>>>>>> origin/fix/scenario-tests-properly
    supports_interval_m: float = 1.5
    material: str = "steel"


class Equipment(BaseEntity):
    entity_type: str = "equipment"
    equipment_category: str
<<<<<<< HEAD
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    rated_power_kva: Optional[float] = None
    voltage_nominal_v: Optional[float] = None
    weight_kg: Optional[float] = None
    dimensions: dict[str, float] | None = None
=======
    manufacturer: str | None = None
    model: str | None = None
    rated_power_kva: float | None = None
    voltage_nominal_v: float | None = None
    weight_kg: float | None = None
    dimensions: Dict[str, float] | None = None
>>>>>>> origin/fix/scenario-tests-properly


class Annotation(BaseEntity):
    entity_type: str = "annotation"
    annotation_type: str
    text: str = ""
    font_size: float = 2.5
    rotation_deg: float = 0.0
    layer: str = "0"
<<<<<<< HEAD
    attached_to_id: Optional[str] = None
    attached_to_type: Optional[str] = None
=======
    attached_to_id: str | None = None
    attached_to_type: str | None = None
>>>>>>> origin/fix/scenario-tests-properly


# ---------------------------------------------------------------------------
# Unified Engineering Model Container
# ---------------------------------------------------------------------------


class UnifiedEngineeringModel(BaseModel):
    """Top-level container holding the entire engineering project model."""

    schema_version: str = "1.0.0"
    project: Project
<<<<<<< HEAD
    metadata: dict[str, Any] = Field(default_factory=dict)
=======
    metadata: Dict[str, Any] = Field(default_factory=dict)
>>>>>>> origin/fix/scenario-tests-properly

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, data: str | bytes) -> UnifiedEngineeringModel:
        return cls.model_validate_json(data)

    @classmethod
    def from_dict(cls, data: dict) -> UnifiedEngineeringModel:
        return cls.model_validate(data)

    def add_building(self, building: Building) -> None:
        self.project.buildings.append(building)

    def add_panel(self, panel: Panel) -> None:
        self.project.panels.append(panel)

<<<<<<< HEAD
    def get_all_buses(self) -> list[Bus]:
        """Collect all Bus entities from metadata."""
        buses: list[Bus] = []
        for bus_data in self.metadata.get("buses", []):
            with contextlib.suppress(Exception):
                buses.append(Bus(**bus_data))
        return buses

    def get_all_cables(self) -> list[Cable]:
        """Collect all Cable entities from metadata."""
        cables: list[Cable] = []
        for cable_data in self.metadata.get("cables", []):
            with contextlib.suppress(Exception):
                cables.append(Cable(**cable_data))
        return cables

    def get_all_transformers(self) -> list[Transformer]:
        """Collect all Transformer entities from metadata."""
        transformers: list[Transformer] = []
        for xf_data in self.metadata.get("transformers", []):
            with contextlib.suppress(Exception):
                transformers.append(Transformer(**xf_data))
        return transformers

    def summary(self) -> dict[str, int]:
        """Return counts of all entity types."""
        counts: dict[str, int] = {
=======
    def get_all_buses(self) -> List[Bus]:
        """Collect all Bus entities from metadata."""
        buses: List[Bus] = []
        for bus_data in self.metadata.get("buses", []):
            try:
                buses.append(Bus(**bus_data))
            except Exception:
                pass
        return buses

    def get_all_cables(self) -> List[Cable]:
        """Collect all Cable entities from metadata."""
        cables: List[Cable] = []
        for cable_data in self.metadata.get("cables", []):
            try:
                cables.append(Cable(**cable_data))
            except Exception:
                pass
        return cables

    def get_all_transformers(self) -> List[Transformer]:
        """Collect all Transformer entities from metadata."""
        transformers: List[Transformer] = []
        for xf_data in self.metadata.get("transformers", []):
            try:
                transformers.append(Transformer(**xf_data))
            except Exception:
                pass
        return transformers

    def summary(self) -> Dict[str, int]:
        """Return counts of all entity types."""
        counts: Dict[str, int] = {
>>>>>>> origin/fix/scenario-tests-properly
            "buildings": len(self.project.buildings),
            "panels": len(self.project.panels),
            "electrical_rooms": len(self.project.electrical_rooms),
            "buses": len(self.metadata.get("buses", [])),
            "cables": len(self.metadata.get("cables", [])),
            "transformers": len(self.metadata.get("transformers", [])),
        }
        return counts


# ---------------------------------------------------------------------------
# ETAP ↔ Unified Model Adapter
# ---------------------------------------------------------------------------


class ETAPModelAdapter:
    """Converts between ETAP native objects and the Unified Engineering Model."""

    @staticmethod
    def bus_to_unified(etap_bus_data: dict) -> Bus:
        """Convert ETAP bus data dict to a unified Bus model."""
        return Bus(
            id=etap_bus_data.get("id", str(uuid.uuid4())),
            name=etap_bus_data.get("name", f"BUS_{etap_bus_data.get('id', 'UNKNOWN')}"),
            bus_type=BusType(etap_bus_data.get("bus_type", "pq")),
            voltage_magnitude_pu=float(etap_bus_data.get("voltage_magnitude", 1.0)),
            voltage_angle_deg=float(etap_bus_data.get("voltage_angle", 0.0)),
            base_kv=float(etap_bus_data.get("base_kv", 11.0)),
            load_mw=float(etap_bus_data.get("load_mw", 0.0)),
            load_mvar=float(etap_bus_data.get("load_mvar", 0.0)),
            gen_mw=float(etap_bus_data.get("gen_mw", 0.0)),
            gen_mvar=float(etap_bus_data.get("gen_mvar", 0.0)),
            source_system=SourceSystem.ETAP,
        )

    @staticmethod
    def transformer_to_unified(etap_xf_data: dict) -> Transformer:
        """Convert ETAP transformer data to a unified Transformer model."""
        return Transformer(
            id=etap_xf_data.get("id", str(uuid.uuid4())),
            name=etap_xf_data.get("name", f"XF_{etap_xf_data.get('id', 'UNKNOWN')}"),
            from_bus_id=etap_xf_data.get("from_bus", ""),
            to_bus_id=etap_xf_data.get("to_bus", ""),
            rated_power_mva=float(etap_xf_data.get("rated_power_mva", 1.0)),
            impedance_percent=float(etap_xf_data.get("impedance_percent", 5.75)),
            tap_ratio=float(etap_xf_data.get("tap_ratio", 1.0)),
            phase_shift_deg=float(etap_xf_data.get("phase_shift", 0.0)),
            r1_pu=float(etap_xf_data.get("r1", 0.0)),
            x1_pu=float(etap_xf_data.get("x1", 0.0)),
            source_system=SourceSystem.ETAP,
        )

    @staticmethod
    def cable_to_unified(etap_cable_data: dict) -> Cable:
        """Convert ETAP cable data to a unified Cable model."""
        return Cable(
            id=etap_cable_data.get("id", str(uuid.uuid4())),
            name=etap_cable_data.get("name", f"CBL_{etap_cable_data.get('id', 'UNKNOWN')}"),
            from_bus_id=etap_cable_data.get("from_bus", ""),
            to_bus_id=etap_cable_data.get("to_bus", ""),
            length_m=float(etap_cable_data.get("length_m", 100.0)),
            conductor_size_mm2=float(etap_cable_data.get("conductor_size_mm2", 95.0)),
            voltage_rating_kv=float(etap_cable_data.get("voltage_rating_kv", 0.6)),
            r_ohm_per_km=float(etap_cable_data.get("r_ohm_per_km", 0.0)),
            x_ohm_per_km=float(etap_cable_data.get("x_ohm_per_km", 0.0)),
            source_system=SourceSystem.ETAP,
        )


# ---------------------------------------------------------------------------
# MCP Tool Schema Helpers
# ---------------------------------------------------------------------------


MCP_TOOL_DEFINITIONS = {
    "create_panel": {
        "description": "Create a new electrical panel with specified parameters",
        "input_schema": Panel.model_json_schema(),
    },
    "create_transformer": {
        "description": "Create a new transformer with specified parameters",
        "input_schema": Transformer.model_json_schema(),
    },
    "create_bus": {
        "description": "Create a new electrical bus",
        "input_schema": Bus.model_json_schema(),
    },
    "create_cable": {
        "description": "Create a new cable connecting two buses",
        "input_schema": Cable.model_json_schema(),
    },
    "create_breaker": {
        "description": "Create a new circuit breaker",
        "input_schema": Breaker.model_json_schema(),
    },
}
