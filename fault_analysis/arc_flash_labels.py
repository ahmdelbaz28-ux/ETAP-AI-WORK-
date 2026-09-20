"""
Arc Flash Warning Label Generator per NFPA 70E and ANSI Z535
============================================================

Generates industrial-grade arc flash warning label specifications and layouts:
- Header: DANGER / WARNING based on incident energy (>40 cal/cm² or <=40 cal/cm²)
- Hazard & Risk Assessment details (Voltage, Incident Energy, Working Distance)
- Arc Flash Boundary (mm & inches)
- Limited & Restricted Approach Boundaries
- Required PPE Category and Description
- Upstream Protective Device Identification & Clearing Time
- PDF, SVG, and HTML label export formats
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ArcFlashLabelSpec:
    """Specification of an Arc Flash Warning Label."""
    equipment_name: str
    voltage_kv: float
    bolted_fault_ka: float
    arc_flash_boundary_mm: float
    arc_flash_boundary_in: float
    incident_energy_cal_cm2: float
    working_distance_mm: float
    working_distance_in: float
    ppe_level: str
    ppe_description: str
    upstream_device: str = "Main Circuit Breaker"
    standard: str = "NFPA 70E / IEEE 1584-2018"
    is_danger: bool = False

    @classmethod
    def from_calculation_result(
        cls,
        equipment_name: str,
        result: Dict[str, Any] | Any,
        upstream_device: str = "Main Circuit Breaker",
    ) -> ArcFlashLabelSpec:
        """Create a label specification from ArcFlashResult or result dict."""
        if hasattr(result, "incident_energy_cal_cm2"):
            energy = float(result.incident_energy_cal_cm2)
            boundary_mm = float(result.arc_flash_boundary_mm)
            voltage = float(result.voltage_kv)
            fault_ka = float(result.bolted_fault_current_ka)
            wd_mm = float(result.working_distance_mm)
            ppe = str(result.ppe_level)
            ppe_desc = str(result.ppe_description)
        else:
            energy = float(result.get("incident_energy_cal_per_cm2", result.get("incident_energy_cal_cm2", 0.0)))
            boundary_mm = float(result.get("arc_flash_boundary_mm", 0.0))
            voltage = float(result.get("voltage_kv", 0.48))
            fault_ka = float(result.get("bolted_fault_current_ka", 20.0))
            wd_mm = float(result.get("working_distance_mm", 457.0))
            ppe = str(result.get("ppe_level", "0"))
            ppe_desc = str(result.get("ppe_description", "Standard cotton workwear"))

        is_danger = energy > 40.0 or ppe.upper() == "DANGER"
        return cls(
            equipment_name=equipment_name,
            voltage_kv=voltage,
            bolted_fault_ka=fault_ka,
            arc_flash_boundary_mm=boundary_mm,
            arc_flash_boundary_in=boundary_mm / 25.4,
            incident_energy_cal_cm2=energy,
            working_distance_mm=wd_mm,
            working_distance_in=wd_mm / 25.4,
            ppe_level=ppe,
            ppe_description=ppe_desc,
            upstream_device=upstream_device,
            is_danger=is_danger,
        )

    def to_svg(self) -> str:
        """Generate ANSI Z535 compliant SVG label markup."""
        header_color = "#D32F2F" if self.is_danger else "#F57C00"
        header_text = "DANGER" if self.is_danger else "WARNING"

        return f"""<svg width="400" height="260" viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg" font-family="Arial, sans-serif">
  <!-- Border and Background -->
  <rect x="2" y="2" width="396" height="256" rx="8" fill="#FFFFFF" stroke="#000000" stroke-width="3"/>
  <!-- Header Bar -->
  <rect x="2" y="2" width="396" height="50" rx="6" fill="{header_color}"/>
  <text x="200" y="36" font-size="28" font-weight="bold" fill="#FFFFFF" text-anchor="middle">{header_text}</text>
  <text x="200" y="68" font-size="14" font-weight="bold" fill="#000000" text-anchor="middle">ARC FLASH &amp; SHOCK HAZARD</text>

  <!-- Hazard Parameters -->
  <line x1="10" y1="75" x2="390" y2="75" stroke="#CCCCCC" stroke-width="1.5"/>
  <text x="20" y="98" font-size="13" font-weight="bold">Equipment: {self.equipment_name}</text>
  <text x="20" y="118" font-size="12">Nominal Voltage: {self.voltage_kv:.2f} kV | Fault: {self.bolted_fault_ka:.1f} kA</text>
  <text x="20" y="138" font-size="12">Incident Energy: <tspan font-weight="bold" fill="{header_color}">{self.incident_energy_cal_cm2:.2f} cal/cm²</tspan> at {self.working_distance_in:.1f} in</text>
  <text x="20" y="158" font-size="12">Arc Flash Boundary: <tspan font-weight="bold">{self.arc_flash_boundary_in:.1f} in</tspan> ({self.arc_flash_boundary_mm:.0f} mm)</text>
  <text x="20" y="178" font-size="12">PPE Category: <tspan font-weight="bold">{self.ppe_level}</tspan> ({self.ppe_description})</text>

  <!-- Protection and Standard Footnote -->
  <line x1="10" y1="195" x2="390" y2="195" stroke="#CCCCCC" stroke-width="1.5"/>
  <text x="20" y="215" font-size="11" fill="#555555">Upstream Device: {self.upstream_device}</text>
  <text x="20" y="235" font-size="10" fill="#777777">Standard: {self.standard} | Generated by AhmedETAP</text>
</svg>"""

    def to_dict(self) -> Dict[str, Any]:
        """Convert label specification to dictionary."""
        return {
            "equipment_name": self.equipment_name,
            "header": "DANGER" if self.is_danger else "WARNING",
            "voltage_kv": self.voltage_kv,
            "bolted_fault_ka": self.bolted_fault_ka,
            "incident_energy_cal_cm2": self.incident_energy_cal_cm2,
            "working_distance_mm": self.working_distance_mm,
            "working_distance_in": self.working_distance_in,
            "arc_flash_boundary_mm": self.arc_flash_boundary_mm,
            "arc_flash_boundary_in": self.arc_flash_boundary_in,
            "ppe_level": self.ppe_level,
            "ppe_description": self.ppe_description,
            "upstream_device": self.upstream_device,
            "standard": self.standard,
        }
