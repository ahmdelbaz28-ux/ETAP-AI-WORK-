"""
Data models for the multi-agent engineering orchestration system.

Contains the core data structures used across all agents and the
ChiefEngineeringOrchestrator: the ``StudyType`` enum (canonical snake_case
keys per ADR-0001), ``AgentStatus``, ``AgentResult``, and ``EngineeringTask``.

This module was extracted from ``agents/orchestrator.py`` to provide a
clean seam: data models live here, the ``BaseAgent`` class lives in
``agents/base.py``, and orchestration logic remains in
``agents/orchestrator.py``. All three symbols are re-exported from
``agents/orchestrator.py`` for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

UTC = timezone.utc  # noqa: UP017

# Module-level string constants (extracted to satisfy S1192).
_SYSTEM_DATA_NOT_PROVIDED_MSG = "System data not provided"  # NOSONAR
_ENGINEERING_REPORT_TITLE = "Engineering Report"  # NOSONAR
_ANALYSIS_RESULTS_TITLE = "Analysis Results"  # NOSONAR


class AgentStatus(Enum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATING = "validating"
    REJECTED = "rejected"
    SKIPPED_WITH_REASON = "skipped_with_reason"


class StudyType(Enum):
    """Power system study types (canonical snake_case values)."""

    LOAD_FLOW = "load_flow"
    SHORT_CIRCUIT = "short_circuit"
    HARMONIC_ANALYSIS = "harmonic_analysis"
    OPTIMAL_POWER_FLOW = "optimal_power_flow"
    PROTECTION_COORDINATION = "protection_coordination"
    MOTOR_STARTING = "motor_starting"
    TRANSIENT_STABILITY = "transient_stability"
    ARC_FLASH = "arc_flash"
    CABLE_SIZING = "cable_sizing"
    EARTH_GRID = "earth_grid"
    RENEWABLE_INTEGRATION = "renewable_integration"
    BATTERY_STORAGE = "battery_storage"
    SCADA = "scada"
    # Added 2026-07-26: referenced by PEER_REVIEW_MATRIX (scada <-> digital_twin)
    # but was missing from the enum, causing StudyType("digital_twin") to fail
    # and fall back to LOAD_FLOW in the AhmedETAP skill pipeline.
    DIGITAL_TWIN = "digital_twin"
    ETAP_EXPERT = "etap_expert"
    ETAP_GUI = "etap_gui"
    GENERATIVE_DESIGN = "generative_design"


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_name: str
    study_type: StudyType
    status: AgentStatus
    data: dict[str, Any]
    validation_status: bool = False
    validation_errors: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    # M2.2 wire contract linkage fields (backward-compatible: all optional)
    run_id: str | None = None
    plan_id: str | None = None
    node_id: str | None = None


@dataclass
class EngineeringTask:
    """Complete engineering task specification."""

    task_id: str
    description: str
    study_types: list[StudyType]
    parameters: dict[str, Any]
    priority: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: AgentStatus = AgentStatus.IDLE
    results: list[AgentResult] = field(default_factory=list)
    # M2.2 wire contract linkage fields (backward-compatible: all optional)
    run_id: str | None = None
    plan_id: str | None = None


@dataclass
class PlanningIntent:
    """Structured intent derived from user goal for engineering execution planning.

    Mandated by M3.1 (explicitly distinct from deprecated/forbidden EngineeringIntent).
    """

    raw_goal: str
    study_types: list[StudyType] = field(default_factory=list)
    confidence: float = 1.0
    routing_source: str = "keyword"  # "keyword", "bandit", "explicit"
    intent_type: str = "analysis"  # "analysis", "optimization", "coordination", "design"
    parameters: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    target_system: str | None = None
    reason: str = ""


@dataclass
class PlanningPlan:
    """High-level engineering plan derived from a PlanningIntent.

    Mandated by M3.1: binds intent to dependency-ordered execution batches and tasks.
    """

    plan_id: str
    intent: PlanningIntent
    execution_order: list[StudyType] = field(default_factory=list)
    tasks: list[EngineeringTask] = field(default_factory=list)
    critical_path: list[str] = field(default_factory=list)
    execution_batches: list[list[str]] = field(default_factory=list)
    status: str = "draft"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

