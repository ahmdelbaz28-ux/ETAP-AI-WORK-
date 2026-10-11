"""zenon field mapping engine.

Loads user-configurable mappings from YAML and applies them to normalize
raw zenon SCADA tags and object parameters to canonical electrical fields.
Emits explicit warnings for any unmapped fields instead of silent guessing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_MAPPING_PATH = Path("config/zenon_field_mapping.yaml")


class ZenonFieldMapper:
    """Manages translation of raw zenon fields into canonical electrical parameters."""

    def __init__(self, mapping_path: str | Path | None = None) -> None:
        self.mapping_path = Path(mapping_path) if mapping_path else DEFAULT_MAPPING_PATH
        self.mappings: dict[str, dict[str, str]] = {}
        self._load_mappings()

    def _load_mappings(self) -> None:
        if self.mapping_path.is_file():
            try:
                with open(self.mapping_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                for key, val in data.items():
                    if isinstance(val, dict):
                        self.mappings[key] = {str(k).upper(): str(v) for k, v in val.items()}
                logger.info("Loaded zenon field mapping from %s", self.mapping_path)
            except Exception as e:
                logger.warning("Failed to load %s: %s. Using default mappings.", self.mapping_path, e)
                self._apply_builtin_defaults()
        else:
            self._apply_builtin_defaults()

    def _apply_builtin_defaults(self) -> None:
        self.mappings = {
            "bus_mapping": {
                "U_NOM": "base_kv",
                "UN": "base_kv",
                "NOMINAL_VOLTAGE": "base_kv",
                "V_MAG": "v_mag",
                "V_ANG": "v_ang",
            },
            "line_mapping": {
                "R": "r_pu",
                "X": "x_pu",
                "B": "b_pu",
                "LENGTH": "length_km",
                "I_MAX": "rating_a",
                "S_MAX": "rating_mva",
            },
            "transformer_mapping": {
                "SR": "rating_mva",
                "UR1": "prim_kv",
                "UR2": "sec_kv",
                "UK": "x_pu",
                "URR": "r_pu",
            },
            "load_mapping": {
                "P": "p_mw",
                "Q": "q_mvar",
            },
            "generator_mapping": {
                "PG": "p_mw",
                "QG": "q_mvar",
                "SN": "rating_mva",
            },
        }

    def map_element_attributes(
        self,
        element_type: str,
        element_id: str,
        raw_attributes: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """Maps raw attributes to canonical attributes.

        Returns (canonical_dict, warnings).
        """
        table_key = f"{element_type}_mapping"
        type_mapping = self.mappings.get(table_key, {})
        canonical: dict[str, Any] = {}
        warnings: list[str] = []

        for raw_k, raw_v in raw_attributes.items():
            upper_k = str(raw_k).upper().strip()
            if upper_k in type_mapping:
                target_k = type_mapping[upper_k]
                canonical[target_k] = raw_v
            else:
                # Keep original key in metadata, emit warning
                canonical[raw_k] = raw_v
                warnings.append(
                    f"Element {element_type} '{element_id}': raw attribute '{raw_k}' has no mapped electrical equivalent"
                )

        return canonical, warnings
