"""Breaker catalog loader for IEC 62271 and IEC 60947 switchgear."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BreakerCatalogItem:
    """Catalog representation of a switchgear/breaker."""

    id: str
    name: str
    category: str
    subcategory: str
    model_number: str
    rated_voltage_kv: float
    rated_current_a: float
    breaking_capacity_ka: float
    making_capacity_ka: float
    short_time_withstand_ka: float = 0.0
    short_time_duration_s: float = 1.0
    standards: List[str] = field(default_factory=list)
    specs: Dict[str, Any] = field(default_factory=dict)


_CATALOG_DIR = Path(__file__).resolve().parent.parent / "data" / "components" / "breakers" / "iec62271"


def load_breaker_catalog(catalog_dir: Optional[Path] = None) -> Dict[str, BreakerCatalogItem]:
    """Load all breaker specifications from the catalog directory."""
    directory = catalog_dir or _CATALOG_DIR
    catalog: Dict[str, BreakerCatalogItem] = {}

    if not directory.exists():
        return catalog

    for json_file in directory.glob("*.json"):
        if json_file.name == "index.json":
            continue
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            specs = data.get("specs", {})
            st_ka = (
                specs.get("short_time_withstand_ka_3s")
                or specs.get("short_time_withstand_ka_1s")
                or specs.get("short_time_withstand_ka", 0.0)
            )
            st_duration = 3.0 if "short_time_withstand_ka_3s" in specs else 1.0

            item = BreakerCatalogItem(
                id=data.get("id", json_file.stem),
                name=data.get("name", json_file.stem),
                category=data.get("category", "IEC 62271"),
                subcategory=data.get("subcategory", ""),
                model_number=data.get("model_number", ""),
                rated_voltage_kv=float(specs.get("rated_voltage_kv", 0.0)),
                rated_current_a=float(specs.get("rated_current_a", 0.0)),
                breaking_capacity_ka=float(specs.get("breaking_capacity_ka", 0.0)),
                making_capacity_ka=float(specs.get("making_capacity_ka", 0.0)),
                short_time_withstand_ka=float(st_ka),
                short_time_duration_s=float(st_duration),
                standards=data.get("standards", []),
                specs=specs,
            )
            catalog[item.id] = item
            # Also index by model_number and filename stem for convenience
            catalog[json_file.stem] = item
            if item.model_number:
                catalog[item.model_number] = item
        except Exception:
            continue

    return catalog
