"""Pydantic schemas for structured engineering responses (chat_structured)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EngineeringFinding(BaseModel):
    """Specific observation or compliance check from an engineering study."""

    model_config = ConfigDict(extra="ignore")

    category: str = Field(..., description="Category (e.g., Short Circuit, Arc Flash, Protection, Voltage)")
    severity: Literal["info", "warning", "critical", "pass"] = Field(
        default="info", description="Severity level"
    )
    message: str = Field(..., description="Technical finding statement")
    standard_reference: Optional[str] = Field(
        default=None, description="Clause or table from IEEE/IEC standard"
    )


class EngineeringMetric(BaseModel):
    """A numerical calculation metric with optional rating limits."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Metric name (e.g., Initial Fault Current Ik'')")
    value: float = Field(..., description="Calculated value")
    unit: str = Field(..., description="Physical unit (e.g., kA, kV, cal/cm²)")
    limit: Optional[float] = Field(default=None, description="Equipment or safety threshold")
    status: Literal["pass", "fail", "marginal", "info"] = Field(default="info")


class EngineerAnswer(BaseModel):
    """Authoritative structured engineering response schema."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Descriptive title of the engineering answer")
    summary: str = Field(..., description="Executive technical summary")
    status: Literal["complete", "warning", "error"] = Field(
        default="complete", description="Overall study status"
    )
    study_type: Optional[str] = Field(
        default=None, description="Power systems study type if applicable"
    )
    findings: List[EngineeringFinding] = Field(
        default_factory=list, description="Categorized engineering observations"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Key parameters and computed numerical values"
    )
    standards_referenced: List[str] = Field(
        default_factory=list, description="List of normative standards (e.g., IEC 60909, IEEE 1584)"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Actionable recommendations for the design/operation"
    )
    duty_table: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Breaker or equipment duty evaluation table"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score of the engineering determination"
    )
