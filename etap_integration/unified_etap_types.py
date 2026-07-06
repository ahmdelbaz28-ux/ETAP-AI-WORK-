"""
unified_etap_types.py — Single Source of Truth for ETAP types
==============================================================
يحل مشكلة وجود 3 ETAPStudyType enums + 3 ETAPResult classes غير متوافقة
في etap_com.py, etap_provider.py, etap_adapter.py.

يُستورد من قبل كل ملفات etap_integration/ + أي مكان يحتاج ETAP types.

Branch: fix/etap-unified-types
Refs: PRODUCTION_PLAN/02_DUPLICATION_REPORT.md Cluster #1
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ETAPStudyType(Enum):
    """
    أنواع الدراسات في ETAP 2021.

    القيم (value) تطابق أسماء modules في ETAP 2021 COM API.
    تم التحقق منها لـ ETAP 2021 (verified via COM registry browser).

    ⚠️ ملاحظات:
    - HARMONIC = "Harmonic" (وليس "HarmonicAnalysis" كما في الكود القديم)
    - MOTOR_STARTING = "MotorStarting" (وليس "MotorAcceleration")
    - HARMONIC_ANALYSIS و MOTOR_ACCELERATION محفوظان كـ aliases
      للتوافق مع الكود القديم (backward compatibility)

    Backward compatibility:
        ETAPStudyType.HARMONIC_ANALYSIS is ETAPStudyType.HARMONIC  → True
        ETAPStudyType.MOTOR_ACCELERATION is ETAPStudyType.MOTOR_STARTING  → True
    """

    LOAD_FLOW = "LoadFlow"
    SHORT_CIRCUIT = "ShortCircuit"
    ARC_FLASH = "ArcFlash"
    HARMONIC = "Harmonic"  # ⚠️ ETAP 2021 uses "Harmonic" not "HarmonicAnalysis"
    OPTIMAL_POWER_FLOW = "OptimalPowerFlow"
    MOTOR_STARTING = "MotorStarting"  # ⚠️ unified (was MotorAcceleration + MotorStarting)
    TRANSIENT_STABILITY = "TransientStability"
    PROTECTION_COORDINATION = "ProtectionCoordination"
    CABLE_AMACITY = "CableAmpacity"
    GROUND_GRID = "GroundGrid"
    RELIABILITY = "Reliability"

    # ── Backward-compatibility aliases ─────────────────────────────
    # These map old names to the unified names. In Python's Enum, when
    # two members share the same value, the second becomes an alias:
    #   ETAPStudyType.HARMONIC_ANALYSIS is ETAPStudyType.HARMONIC → True
    # This means old code using HARMONIC_ANALYSIS or MOTOR_ACCELERATION
    # continues to work without modification.
    HARMONIC_ANALYSIS = "Harmonic"  # alias for HARMONIC
    MOTOR_ACCELERATION = "MotorStarting"  # alias for MOTOR_STARTING

    @classmethod
    def from_com_string(cls, name: str) -> "ETAPStudyType":
        """
        تحويل string من COM (مثل "LoadFlow") إلى enum.

        Raises:
            ValueError: لو الـ string لا يطابق أي member أو value.
        """
        # Direct match on value (COM module name)
        for member in cls:
            if member.value == name:
                return member

        # Backward compat: accept old snake_case names (LOAD_FLOW, load_flow)
        legacy_mapping = {
            "LOAD_FLOW": cls.LOAD_FLOW,
            "load_flow": cls.LOAD_FLOW,
            "SHORT_CIRCUIT": cls.SHORT_CIRCUIT,
            "short_circuit": cls.SHORT_CIRCUIT,
            "ARC_FLASH": cls.ARC_FLASH,
            "arc_flash": cls.ARC_FLASH,
            "HARMONIC_ANALYSIS": cls.HARMONIC,  # legacy name → unified
            "harmonic_analysis": cls.HARMONIC,
            "OPTIMAL_POWER_FLOW": cls.OPTIMAL_POWER_FLOW,
            "optimal_power_flow": cls.OPTIMAL_POWER_FLOW,
            "MOTOR_STARTING": cls.MOTOR_STARTING,
            "motor_starting": cls.MOTOR_STARTING,
            "MOTOR_ACCELERATION": cls.MOTOR_STARTING,  # legacy alias
            "motor_acceleration": cls.MOTOR_STARTING,
            "TRANSIENT_STABILITY": cls.TRANSIENT_STABILITY,
            "transient_stability": cls.TRANSIENT_STABILITY,
            "PROTECTION_COORDINATION": cls.PROTECTION_COORDINATION,
            "protection_coordination": cls.PROTECTION_COORDINATION,
            "CABLE_AMACITY": cls.CABLE_AMACITY,
            "cable_ampacity": cls.CABLE_AMACITY,
            "GROUND_GRID": cls.GROUND_GRID,
            "ground_grid": cls.GROUND_GRID,
            "RELIABILITY": cls.RELIABILITY,
            "reliability": cls.RELIABILITY,
        }
        if name in legacy_mapping:
            return legacy_mapping[name]

        raise ValueError(
            f"Unknown ETAP study type: {name!r}. "
            f"Valid values: {[m.value for m in cls]}"
        )

    @classmethod
    def from_name(cls, name: str) -> "ETAPStudyType":
        """تحويل enum name (مثل "LOAD_FLOW") إلى enum."""
        try:
            return cls[name]
        except KeyError as e:
            raise ValueError(f"Unknown ETAPStudyType name: {name!r}") from e


@dataclass
class ETAPResult:
    """
    Container موحَّد لنتائج دراسات ETAP.

    يحل مشكلة وجود 3 classes بـ signatures مختلفة:
    - etap_com.py:    (study_type, success, data, warnings, errors, timestamp)
    - etap_provider.py: (success, data, warnings, errors, execution_time)
    - etap_adapter.py:  (success, data, warnings, errors, execution_time)

    التصميم:
    - الحقول الإلزامية أولاً (success, data) — متوافق مع كل الاستدعاءات
    - الحقول الاختيارية بعدها بـ defaults — متوافق مع etap_provider/adapter
    - study_type + timestamp في النهاية بـ defaults — متوافق مع etap_com
    - كل الحقول serializable (لـ JSON / Supabase / Langfuse)

    Usage (all forms work):
        ETAPResult(False, {}, [], ["error"], 1.5)  # positional (etap_provider style)
        ETAPResult(success=True, data={...})  # keyword (etap_adapter style)
        ETAPResult(study_type="LoadFlow", success=True, data=...,
                   warnings=[], errors=[], timestamp=...)  # keyword (etap_com style)
    """

    success: bool
    data: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    # Extra fields from etap_com.py's version, with defaults for backward compat
    study_type: str = ""  # string value of ETAPStudyType (e.g., "LoadFlow")
    timestamp: float = field(default_factory=time.time)
    etap_version: str = ""  # يُملأ من COM (app.Version)
    trace_id: str = ""  # Langfuse trace ID

    def to_dict(self) -> dict[str, Any]:
        """Serialize لـ dict (JSON-safe)."""
        return {
            "success": self.success,
            "data": self.data,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "execution_time": self.execution_time,
            "study_type": self.study_type,
            "timestamp": self.timestamp,
            "etap_version": self.etap_version,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ETAPResult":
        """Deserialize من dict."""
        return cls(
            success=d.get("success", False),
            data=d.get("data", {}),
            warnings=d.get("warnings", []),
            errors=d.get("errors", []),
            execution_time=d.get("execution_time", 0.0),
            study_type=d.get("study_type", ""),
            timestamp=d.get("timestamp", time.time()),
            etap_version=d.get("etap_version", ""),
            trace_id=d.get("trace_id", ""),
        )

    def add_warning(self, msg: str) -> None:
        if msg and msg not in self.warnings:
            self.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        if msg and msg not in self.errors:
            self.errors.append(msg)


class IEtapProvider(ABC):
    """
    Abstract interface لكل ETAP providers.

    Implementations:
    - LocalEtapProvider: Windows COM direct (in etap_provider.py)
    - RemoteEtapProvider: HTTP to Windows worker (in etap_provider.py)
    - MockEtapProvider: dev only, forbidden in production (in etap_provider.py)
    - NullEtapProvider: default when ETAP unavailable (in etap_provider.py)
    """

    @abstractmethod
    def execute_study(
        self,
        project_path: str,
        study_type: ETAPStudyType,
        visible: bool = False,
    ) -> ETAPResult:
        """تنفيذ دراسة على ETAP backend."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """هل الـ provider متاح؟"""
        ...

    def health_check(self) -> dict[str, Any]:
        """فحص صحة الـ provider — يُرجِع تفاصيل الاتصال."""
        return {
            "provider": type(self).__name__,
            "available": self.is_available(),
        }

    def get_version(self) -> str:
        """إصدار ETAP المتصل (مثل "21.0.0")."""
        return "N/A"


__all__ = [
    "ETAPStudyType",
    "ETAPResult",
    "IEtapProvider",
]
