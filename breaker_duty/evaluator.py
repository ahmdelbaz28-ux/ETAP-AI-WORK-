"""Breaker duty evaluation engine per IEC 62271-100 and IEC 60947-2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from breaker_duty.catalog import BreakerCatalogItem, load_breaker_catalog


@dataclass
class DutyLimitCheck:
    """Individual duty check row for a breaker rating."""

    parameter: str
    calculated_value: float
    rated_limit: float
    unit: str
    duty_percent: float
    margin: float
    passed: bool
    standard_clause: str


@dataclass
class BreakerDutyResult:
    """Comprehensive breaker duty evaluation result."""

    breaker_id: str
    breaker_name: str
    operating_voltage_kv: float
    max_duty_percent: float
    is_compliant: bool
    status: str
    duty_table: List[Dict[str, Any]]
    violations: List[str]
    standards_referenced: List[str] = field(
        default_factory=lambda: ["IEC 62271-100", "IEC 60909-0", "IEC 60947-2"]
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "breaker_id": self.breaker_id,
            "breaker_name": self.breaker_name,
            "operating_voltage_kv": self.operating_voltage_kv,
            "max_duty_percent": round(self.max_duty_percent, 2),
            "is_compliant": self.is_compliant,
            "status": self.status,
            "duty_table": self.duty_table,
            "violations": self.violations,
            "standards_referenced": self.standards_referenced,
        }


class BreakerDutyEvaluator:
    """Evaluates short-circuit stresses against circuit breaker equipment ratings per IEC 62271-100."""

    def __init__(self, catalog: Optional[Dict[str, BreakerCatalogItem]] = None) -> None:
        self.catalog = catalog or load_breaker_catalog()

    def evaluate_breaker(
        self,
        breaker: BreakerCatalogItem | Dict[str, Any] | str,
        ik_initial_ka: float,
        ip_peak_ka: float,
        ib_breaking_ka: float,
        ith_thermal_ka: Optional[float] = None,
        operating_voltage_kv: Optional[float] = None,
        operating_current_a: Optional[float] = None,
    ) -> BreakerDutyResult:
        """Evaluate breaker duty against fault currents and operating conditions."""
        item: Optional[BreakerCatalogItem] = None

        if isinstance(breaker, str):
            item = self.catalog.get(breaker)
            if item is None:
                raise ValueError(f"Breaker '{breaker}' not found in catalog")
        elif isinstance(breaker, BreakerCatalogItem):
            item = breaker
        elif isinstance(breaker, dict):
            specs = breaker.get("specs", breaker)
            item = BreakerCatalogItem(
                id=str(breaker.get("id", "custom_breaker")),
                name=str(breaker.get("name", "Custom Breaker")),
                category=str(breaker.get("category", "IEC 62271")),
                subcategory=str(breaker.get("subcategory", "")),
                model_number=str(breaker.get("model_number", "")),
                rated_voltage_kv=float(specs.get("rated_voltage_kv", 0.0)),
                rated_current_a=float(specs.get("rated_current_a", 0.0)),
                breaking_capacity_ka=float(specs.get("breaking_capacity_ka", 0.0)),
                making_capacity_ka=float(specs.get("making_capacity_ka", 0.0)),
                short_time_withstand_ka=float(
                    specs.get("short_time_withstand_ka_3s")
                    or specs.get("short_time_withstand_ka_1s")
                    or specs.get("short_time_withstand_ka", 0.0)
                ),
                standards=breaker.get("standards", ["IEC 62271-100"]),
                specs=specs,
            )

        if item is None:
            raise ValueError("Invalid breaker specification provided")

        op_voltage = operating_voltage_kv if operating_voltage_kv is not None else item.rated_voltage_kv

        rows: List[DutyLimitCheck] = []
        violations: List[str] = []

        # 1. Symmetrical Breaking Capacity Duty (Ib vs Icu / rated breaking)
        breaking_limit = item.breaking_capacity_ka
        if breaking_limit > 0:
            duty_breaking = (ib_breaking_ka / breaking_limit) * 100.0
            margin_breaking = breaking_limit - ib_breaking_ka
            passed_breaking = duty_breaking <= 100.0
            if not passed_breaking:
                violations.append(
                    f"Breaking duty {duty_breaking:.1f}% exceeds 100% rating: "
                    f"Ib={ib_breaking_ka:.2f} kA > rated Icu={breaking_limit:.2f} kA"
                )
            rows.append(
                DutyLimitCheck(
                    parameter="Symmetrical Breaking Current (Ib)",
                    calculated_value=round(ib_breaking_ka, 3),
                    rated_limit=round(breaking_limit, 3),
                    unit="kA",
                    duty_percent=round(duty_breaking, 2),
                    margin=round(margin_breaking, 3),
                    passed=passed_breaking,
                    standard_clause="IEC 62271-100 Cl. 6.101",
                )
            )

        # 2. Peak Making Capacity Duty (ip vs rated making peak)
        making_limit = item.making_capacity_ka
        if making_limit > 0:
            duty_making = (ip_peak_ka / making_limit) * 100.0
            margin_making = making_limit - ip_peak_ka
            passed_making = duty_making <= 100.0
            if not passed_making:
                violations.append(
                    f"Making peak duty {duty_making:.1f}% exceeds 100% rating: "
                    f"ip={ip_peak_ka:.2f} kA > rated peak={making_limit:.2f} kA"
                )
            rows.append(
                DutyLimitCheck(
                    parameter="Peak Making Current (ip)",
                    calculated_value=round(ip_peak_ka, 3),
                    rated_limit=round(making_limit, 3),
                    unit="kA",
                    duty_percent=round(duty_making, 2),
                    margin=round(margin_making, 3),
                    passed=passed_making,
                    standard_clause="IEC 62271-100 Cl. 6.101.3",
                )
            )

        # 3. Short-Time Withstand (Thermal) Duty (Ith vs rated short-time)
        thermal_calc = ith_thermal_ka if ith_thermal_ka is not None else ik_initial_ka
        thermal_limit = item.short_time_withstand_ka
        if thermal_limit > 0:
            duty_thermal = (thermal_calc / thermal_limit) * 100.0
            margin_thermal = thermal_limit - thermal_calc
            passed_thermal = duty_thermal <= 100.0
            if not passed_thermal:
                violations.append(
                    f"Thermal short-time duty {duty_thermal:.1f}% exceeds 100% rating: "
                    f"Ith={thermal_calc:.2f} kA > rated short-time={thermal_limit:.2f} kA"
                )
            rows.append(
                DutyLimitCheck(
                    parameter="Short-Time Thermal Current (Ith)",
                    calculated_value=round(thermal_calc, 3),
                    rated_limit=round(thermal_limit, 3),
                    unit="kA",
                    duty_percent=round(duty_thermal, 2),
                    margin=round(margin_thermal, 3),
                    passed=passed_thermal,
                    standard_clause="IEC 62271-100 Cl. 6.102",
                )
            )

        # 4. Voltage Duty (operating_voltage vs rated_voltage)
        if item.rated_voltage_kv > 0:
            duty_voltage = (op_voltage / item.rated_voltage_kv) * 100.0
            margin_voltage = item.rated_voltage_kv - op_voltage
            passed_voltage = duty_voltage <= 100.0
            if not passed_voltage:
                violations.append(
                    f"Voltage duty {duty_voltage:.1f}% exceeds 100% rating: "
                    f"Ue={op_voltage:.2f} kV > Ur={item.rated_voltage_kv:.2f} kV"
                )
            rows.append(
                DutyLimitCheck(
                    parameter="Operating Voltage (Ue)",
                    calculated_value=round(op_voltage, 3),
                    rated_limit=round(item.rated_voltage_kv, 3),
                    unit="kV",
                    duty_percent=round(duty_voltage, 2),
                    margin=round(margin_voltage, 3),
                    passed=passed_voltage,
                    standard_clause="IEC 62271-1 Cl. 4.1",
                )
            )

        # 5. Continuous Current Duty (if operating current provided)
        if operating_current_a is not None and item.rated_current_a > 0:
            duty_current = (operating_current_a / item.rated_current_a) * 100.0
            margin_current = item.rated_current_a - operating_current_a
            passed_current = duty_current <= 100.0
            if not passed_current:
                violations.append(
                    f"Continuous current duty {duty_current:.1f}% exceeds 100% rating: "
                    f"I={operating_current_a:.1f} A > Ir={item.rated_current_a:.1f} A"
                )
            rows.append(
                DutyLimitCheck(
                    parameter="Continuous Current (Ir)",
                    calculated_value=round(operating_current_a, 2),
                    rated_limit=round(item.rated_current_a, 2),
                    unit="A",
                    duty_percent=round(duty_current, 2),
                    margin=round(margin_current, 2),
                    passed=passed_current,
                    standard_clause="IEC 62271-1 Cl. 4.4",
                )
            )

        max_duty = max((r.duty_percent for r in rows), default=0.0)
        is_compliant = len(violations) == 0
        status = "COMPLIANT_PASS" if is_compliant else "OVERDUTY_REJECTED"

        duty_table = [
            {
                "parameter": r.parameter,
                "calculated_value": r.calculated_value,
                "rated_limit": r.rated_limit,
                "unit": r.unit,
                "duty_percent": r.duty_percent,
                "margin": r.margin,
                "status": "PASS" if r.passed else "FAIL",
                "standard_clause": r.standard_clause,
            }
            for r in rows
        ]

        return BreakerDutyResult(
            breaker_id=item.id,
            breaker_name=item.name,
            operating_voltage_kv=round(op_voltage, 3),
            max_duty_percent=max_duty,
            is_compliant=is_compliant,
            status=status,
            duty_table=duty_table,
            violations=violations,
        )

    def execute_study(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute breaker duty analysis from parameters."""
        breaker_id = parameters.get("breaker_id") or parameters.get("breaker")
        if not breaker_id and "breakers" not in parameters:
            # Default to first MV breaker if none specified
            breaker_id = "mv_vcb_12kv_1250a_25ka"

        ik_initial_ka = float(parameters.get("ik_initial_ka", parameters.get("ik_ss_ka", 20.0)))
        ip_peak_ka = float(parameters.get("ip_peak_ka", ik_initial_ka * 2.5))
        ib_breaking_ka = float(parameters.get("ib_breaking_ka", ik_initial_ka * 0.9))
        ith_thermal_ka = float(parameters.get("ith_thermal_ka", ik_initial_ka))
        voltage_kv = float(parameters.get("voltage_kv", 11.0)) if "voltage_kv" in parameters else None
        current_a = float(parameters.get("current_a", 800.0)) if "current_a" in parameters else None

        res = self.evaluate_breaker(
            breaker=breaker_id,
            ik_initial_ka=ik_initial_ka,
            ip_peak_ka=ip_peak_ka,
            ib_breaking_ka=ib_breaking_ka,
            ith_thermal_ka=ith_thermal_ka,
            operating_voltage_kv=voltage_kv,
            operating_current_a=current_a,
        )
        return res.to_dict()
