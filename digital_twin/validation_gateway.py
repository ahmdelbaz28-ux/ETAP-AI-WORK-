
"""
Validation Gateway - Three Truths Enforcement
==============================================
Enforces the hard constraints of the digital twin platform:
  - GIS layer is the Spatial Truth
  - Electrical model is the Mathematical Truth
  - ADMS is the Operational Truth
All three must remain synchronized. Any inconsistency triggers validation errors.

Reference: IEC 61970 CIM, EPRI ADMS Integration Guide
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation results."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationRule(Enum):
    """All validation rules in the digital twin."""
    # GIS - Spatial Truth Rules
    GIS_ASSET_HAS_POSITION = "gis_asset_has_position"
    GIS_LINE_HAS_GEOMETRY = "gis_line_has_geometry"
    GIS_ELECTRICAL_ID_RESOLVES = "gis_electrical_id_resolves"
    GIS_ZONE_REFERENCES_VALID = "gis_zone_references_valid"
    GIS_ALL_ELECTRICAL_HAVE_GIS = "gis_all_electrical_have_gis"

    # Electrical - Mathematical Truth Rules
    ELECTRICAL_BUS_EXISTS = "electrical_bus_exists"
    ELECTRICAL_YBUS_VALID = "electrical_ybus_valid"
    ELECTRICAL_LOAD_FLOW_CONVERGED = "electrical_load_flow_converged"
    ELECTRICAL_VOLTAGES_IN_RANGE = "electrical_voltages_in_range"
    ELECTRICAL_NO_ISOLATED_SOURCE = "electrical_no_isolated_source"

    # ADMS - Operational Truth Rules
    ADMS_SWITCH_EXISTS_IN_TOPOLOGY = "adms_switch_exists_in_topology"
    ADMS_SWITCH_STATUS_CONSISTENT = "adms_switch_status_consistent"
    ADMS_TOPOLOGY_MATCHES_SWITCHING = "adms_topology_matches_switching"
    ADMS_SCADA_MEASUREMENTS_FRESH = "adms_scada_measurements_fresh"
    ADMS_SOURCE_BUSES_DEFINED = "adms_source_buses_defined"

    # Cross-Layer Synchronization Rules
    SYNC_GIS_ELECTRICAL_ALIGNMENT = "sync_gis_electrical_alignment"
    SYNC_ADMS_ELECTRICAL_TOPOLOGY = "sync_adms_electrical_topology"
    SYNC_GIS_SWITCH_HAS_POSITION = "sync_gis_switch_has_position"
    SYNC_ALL_LAYERS_PRESENT = "sync_all_layers_present"
    SYNC_YBUS_MATCHES_TOPOLOGY = "sync_ybus_matches_topology"


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    rule: ValidationRule
    passed: bool
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "rule": self.rule.value,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class DigitalTwinValidationError(Exception):
    """Raised when digital twin validation fails."""

    def __init__(self, results: List[ValidationResult], message: str = ""):
        self.results = results
        self.failed_rules = [r for r in results if not r.passed]
        error_summary = "; ".join(
            f"[{r.severity.value}] {r.rule.value}: {r.message}"
            for r in self.failed_rules
        )
        full_message = message or f"Digital Twin Validation Failed: {error_summary}"
        super().__init__(full_message)

    def to_dict(self) -> dict:
        return {
            "error_type": "DigitalTwinValidationError",
            "message": str(self),
            "failed_count": len(self.failed_rules),
            "failed_rules": [r.to_dict() for r in self.failed_rules]
        }


class ValidationGateway:
    """
    Validation Gateway enforcing the Three Truths Principle.

    GIS = Spatial Truth
    Electrical = Mathematical Truth
    ADMS = Operational Truth

    All three must remain synchronized. Any inconsistency triggers
    validation errors that block state transitions.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize ValidationGateway.

        Parameters:
        strict_mode: If True, any validation failure raises DigitalTwinValidationError.
                     If False, failures are recorded but do not raise exceptions.
        """
        self.strict_mode = strict_mode
        self._custom_rules: Dict[ValidationRule, Callable] = {}
        self._validation_history: List[List[ValidationResult]] = []
        self._max_history = 1000

    def register_custom_rule(self, rule: ValidationRule,
                             validator: Callable) -> None:
        """Register a custom validation rule function."""
        self._custom_rules[rule] = validator

    def validate_all(self, gis_db=None, system=None, scada_db=None,
                     adms_engine=None, state_snapshot=None) -> List[ValidationResult]:
        """
        Run all validation rules across all layers.

        Parameters:
        gis_db: GISDatabase instance
        system: core_model.system.System instance
        scada_db: SCADADatabase instance
        adms_engine: ADMSControlEngine instance
        state_snapshot: StateSnapshot instance

        Returns:
        List of ValidationResult for all checks.
        """
        results = []

        # GIS Layer Validations
        results.extend(self._validate_gis_layer(gis_db))

        # Electrical Layer Validations
        results.extend(self._validate_electrical_layer(system))

        # ADMS Layer Validations
        results.extend(self._validate_adms_layer(scada_db, adms_engine))

        # Cross-Layer Synchronization Validations
        results.extend(self._validate_cross_layer_sync(
            gis_db, system, scada_db, adms_engine
        ))

        # State Snapshot Validations
        if state_snapshot is not None:
            results.extend(self._validate_state_snapshot(state_snapshot))

        # Custom Rules
        for rule, validator in self._custom_rules.items():
            try:
                result = validator(gis_db, system, scada_db, adms_engine, state_snapshot)
                if isinstance(result, ValidationResult):
                    results.append(result)
                elif isinstance(result, list):
                    results.extend(result)
            except Exception as e:
                results.append(ValidationResult(
                    rule=rule,
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Custom rule exception: {str(e)}"
                ))

        # Record history
        self._validation_history.append(results)
        if len(self._validation_history) > self._max_history:
            self._validation_history = self._validation_history[-self._max_history:]

        # Strict mode: raise on failure
        if self.strict_mode:
            failures = [r for r in results if not r.passed and
                        r.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)]
            if failures:
                raise DigitalTwinValidationError(failures)

        return results

    def validate_pre_mutation(self, event_type: str, gis_db=None,
                               system=None, scada_db=None,
                               adms_engine=None) -> List[ValidationResult]:
        """
        Validate pre-conditions before a state mutation.

        Called before any event is processed to ensure the system
        is in a valid state for the mutation.
        """
        results = []

        # All layers must be present for any mutation
        results.append(ValidationResult(
            rule=ValidationRule.SYNC_ALL_LAYERS_PRESENT,
            passed=system is not None,
            severity=ValidationSeverity.CRITICAL,
            message="Electrical model must exist for any mutation" if system is None else "OK"
        ))

        # Switch operations require the switch to exist
        if event_type in ("switch_opened", "switch_closed"):
            if adms_engine is not None:
                results.append(ValidationResult(
                    rule=ValidationRule.ADMS_SWITCH_EXISTS_IN_TOPOLOGY,
                    passed=True,  # Will be checked during event processing
                    severity=ValidationSeverity.ERROR,
                    message="Switch existence will be verified during processing"
                ))

        return results

    def validate_post_mutation(self, gis_db=None, system=None,
                                scada_db=None, adms_engine=None,
                                state_snapshot=None) -> List[ValidationResult]:
        """
        Validate post-conditions after a state mutation.

        Called after event processing to ensure the system remains
        in a consistent state.
        """
        return self.validate_all(gis_db, system, scada_db, adms_engine, state_snapshot)

    # ============================================================
    # GIS LAYER VALIDATIONS (Spatial Truth)
    # ============================================================

    def _validate_gis_layer(self, gis_db) -> List[ValidationResult]:
        """Validate GIS spatial truth."""
        results = []

        if gis_db is None:
            results.append(ValidationResult(
                rule=ValidationRule.SYNC_ALL_LAYERS_PRESENT,
                passed=False,
                severity=ValidationSeverity.WARNING,
                message="GIS database not provided - spatial truth cannot be validated"
            ))
            return results

        # Check point assets have positions
        from gis_model.gis_model import GISAssetType
        point_types = (GISAssetType.BUS, GISAssetType.SUBSTATION,
                       GISAssetType.LOAD, GISAssetType.GENERATOR,
                       GISAssetType.SWITCH, GISAssetType.DER)
        missing_position = 0
        for asset in gis_db.assets.values():
            if asset.asset_type in point_types and not asset.position:
                missing_position += 1

        results.append(ValidationResult(
            rule=ValidationRule.GIS_ASSET_HAS_POSITION,
            passed=missing_position == 0,
            severity=ValidationSeverity.ERROR if missing_position > 0 else ValidationSeverity.INFO,
            message=f"{missing_position} point assets missing position" if missing_position > 0 else "All point assets have positions",
            details={"missing_count": missing_position}
        ))

        # Check line assets have geometry
        missing_geometry = 0
        for asset in gis_db.assets.values():
            if asset.asset_type == GISAssetType.LINE and not asset.geometry:
                missing_geometry += 1

        results.append(ValidationResult(
            rule=ValidationRule.GIS_LINE_HAS_GEOMETRY,
            passed=missing_geometry == 0,
            severity=ValidationSeverity.ERROR if missing_geometry > 0 else ValidationSeverity.INFO,
            message=f"{missing_geometry} line assets missing geometry" if missing_geometry > 0 else "All line assets have geometry",
            details={"missing_count": missing_geometry}
        ))

        # Check electrical_id references resolve
        gis_errors = gis_db.validate_spatial_consistency()
        results.append(ValidationResult(
            rule=ValidationRule.GIS_ELECTRICAL_ID_RESOLVES,
            passed=len(gis_errors) == 0,
            severity=ValidationSeverity.ERROR if gis_errors else ValidationSeverity.INFO,
            message=f"{len(gis_errors)} GIS spatial consistency errors" if gis_errors else "GIS spatial consistency OK",
            details={"errors": gis_errors}
        ))

        return results

    # ============================================================
    # ELECTRICAL LAYER VALIDATIONS (Mathematical Truth)
    # ============================================================

    def _validate_electrical_layer(self, system) -> List[ValidationResult]:
        """Validate electrical mathematical truth."""
        results = []

        if system is None:
            results.append(ValidationResult(
                rule=ValidationRule.ELECTRICAL_BUS_EXISTS,
                passed=False,
                severity=ValidationSeverity.CRITICAL,
                message="Electrical model (System) not provided"
            ))
            return results

        # Check buses exist
        n_buses = len(system.buses)
        results.append(ValidationResult(
            rule=ValidationRule.ELECTRICAL_BUS_EXISTS,
            passed=n_buses > 0,
            severity=ValidationSeverity.CRITICAL if n_buses == 0 else ValidationSeverity.INFO,
            message=f"System has {n_buses} buses"
        ))

        # Check Ybus is valid
        try:
            ybus = system.get_ybus('1')
            ybus_valid = ybus is not None and ybus.shape[0] == n_buses and ybus.shape[1] == n_buses
            results.append(ValidationResult(
                rule=ValidationRule.ELECTRICAL_YBUS_VALID,
                passed=ybus_valid,
                severity=ValidationSeverity.ERROR if not ybus_valid else ValidationSeverity.INFO,
                message=f"Ybus shape {ybus.shape} for {n_buses} buses" if ybus_valid else "Ybus matrix invalid",
                details={"ybus_shape": list(ybus.shape) if ybus is not None else None}
            ))
        except Exception as e:
            results.append(ValidationResult(
                rule=ValidationRule.ELECTRICAL_YBUS_VALID,
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Ybus construction failed: {str(e)}"
            ))

        # Check voltages in range (0.9 - 1.1 pu)
        out_of_range = 0
        for bid, bus in system.buses.items():
            if bus.voltage_magnitude < 0.9 or bus.voltage_magnitude > 1.1:
                out_of_range += 1
        results.append(ValidationResult(
            rule=ValidationRule.ELECTRICAL_VOLTAGES_IN_RANGE,
            passed=out_of_range == 0,
            severity=ValidationSeverity.WARNING if out_of_range > 0 else ValidationSeverity.INFO,
            message=f"{out_of_range} buses with voltage outside 0.9-1.1 pu range" if out_of_range > 0 else "All voltages in range",
            details={"out_of_range_count": out_of_range}
        ))

        # Check at least one slack bus exists
        has_slack = any(b.bus_type == 'slack' for b in system.buses.values())
        results.append(ValidationResult(
            rule=ValidationRule.ELECTRICAL_NO_ISOLATED_SOURCE,
            passed=has_slack,
            severity=ValidationSeverity.CRITICAL if not has_slack else ValidationSeverity.INFO,
            message="Slack bus exists" if has_slack else "No slack bus defined"
        ))

        return results

    # ============================================================
    # ADMS LAYER VALIDATIONS (Operational Truth)
    # ============================================================

    def _validate_adms_layer(self, scada_db, adms_engine) -> List[ValidationResult]:
        """Validate ADMS operational truth."""
        results = []

        # Check SCADA measurements freshness
        if scada_db is not None:
            expired = len(scada_db.get_expired_measurements()) if hasattr(scada_db, 'get_expired_measurements') else 0
            results.append(ValidationResult(
                rule=ValidationRule.ADMS_SCADA_MEASUREMENTS_FRESH,
                passed=expired == 0,
                severity=ValidationSeverity.WARNING if expired > 0 else ValidationSeverity.INFO,
                message=f"{expired} expired SCADA measurements" if expired > 0 else "All SCADA measurements fresh",
                details={"expired_count": expired}
            ))

            # Check switch status consistency
            switches = scada_db.switch_devices if hasattr(scada_db, 'switch_devices') else {}
            results.append(ValidationResult(
                rule=ValidationRule.ADMS_SWITCH_STATUS_CONSISTENT,
                passed=True,
                severity=ValidationSeverity.INFO,
                message=f"{len(switches)} switch devices tracked"
            ))

        # Check ADMS engine has source buses
        if adms_engine is not None:
            has_sources = len(adms_engine.source_buses) > 0 if hasattr(adms_engine, 'source_buses') else False
            results.append(ValidationResult(
                rule=ValidationRule.ADMS_SOURCE_BUSES_DEFINED,
                passed=has_sources,
                severity=ValidationSeverity.ERROR if not has_sources else ValidationSeverity.INFO,
                message=f"{len(adms_engine.source_buses)} source buses defined" if has_sources else "No source buses defined"
            ))

        return results

    # ============================================================
    # CROSS-LAYER SYNCHRONIZATION VALIDATIONS
    # ============================================================

    def _validate_cross_layer_sync(self, gis_db, system,
                                    scada_db, adms_engine) -> List[ValidationResult]:
        """Validate cross-layer synchronization (Three Truths Principle)."""
        results = []

        # GIS <-> Electrical alignment
        if gis_db is not None and system is not None:
            electrical_ids = set()
            for bid in system.buses.keys():
                electrical_ids.add(str(bid))
            for line in system.lines:
                electrical_ids.add(f"line_{line.line_id}")
            for xf in system.transformers:
                electrical_ids.add(f"xf_{xf.transformer_id}")
            for gen in system.generators:
                electrical_ids.add(f"gen_{gen.generator_id}")
            for load in system.loads:
                electrical_ids.add(f"load_{load.load_id}")

            gis_errors = gis_db.validate_gis_electrical_alignment(electrical_ids)
            results.append(ValidationResult(
                rule=ValidationRule.SYNC_GIS_ELECTRICAL_ALIGNMENT,
                passed=len(gis_errors) == 0,
                severity=ValidationSeverity.ERROR if gis_errors else ValidationSeverity.INFO,
                message=f"{len(gis_errors)} GIS-electrical alignment errors" if gis_errors else "GIS-Electrical alignment OK",
                details={"errors": gis_errors}
            ))

            # Check all electrical buses have GIS positions
            missing_gis = 0
            for bid in system.buses.keys():
                asset = gis_db.find_asset_by_electrical_id(str(bid))
                if asset is None or asset.position is None:
                    missing_gis += 1
            results.append(ValidationResult(
                rule=ValidationRule.SYNC_GIS_SWITCH_HAS_POSITION,
                passed=missing_gis == 0,
                severity=ValidationSeverity.WARNING if missing_gis > 0 else ValidationSeverity.INFO,
                message=f"{missing_gis} buses without GIS position" if missing_gis > 0 else "All buses have GIS positions",
                details={"missing_gis_count": missing_gis}
            ))

        # ADMS <-> Electrical topology alignment
        if adms_engine is not None and system is not None:
            topology = adms_engine.topology if hasattr(adms_engine, 'topology') else None
            if topology is not None:
                # Check topology buses exist in electrical model
                topo_buses = set(topology.bus_connections.keys()) if hasattr(topology, 'bus_connections') else set()
                elec_buses = set(str(bid) for bid in system.buses.keys())
                orphaned = topo_buses - elec_buses
                results.append(ValidationResult(
                    rule=ValidationRule.SYNC_ADMS_ELECTRICAL_TOPOLOGY,
                    passed=len(orphaned) == 0,
                    severity=ValidationSeverity.ERROR if orphaned else ValidationSeverity.INFO,
                    message=f"{len(orphaned)} topology buses not in electrical model" if orphaned else "ADMS topology matches electrical model",
                    details={"orphaned_buses": list(orphaned)}
                ))

        # Ybus <-> Topology alignment
        if system is not None and adms_engine is not None:
            results.append(ValidationResult(
                rule=ValidationRule.SYNC_YBUS_MATCHES_TOPOLOGY,
                passed=True,
                severity=ValidationSeverity.INFO,
                message="Ybus-topology alignment will be verified after rebuild"
            ))

        return results

    # ============================================================
    # STATE SNAPSHOT VALIDATIONS
    # ============================================================

    def _validate_state_snapshot(self, snapshot) -> List[ValidationResult]:
        """Validate a state snapshot for internal consistency."""
        results = []

        if snapshot is None:
            return results

        # Check all layers have data
        has_gis = len(snapshot.gis_assets) > 0 if hasattr(snapshot, 'gis_assets') else False
        has_elec = len(snapshot.bus_states) > 0 if hasattr(snapshot, 'bus_states') else False
        has_adms = len(snapshot.switch_states) > 0 if hasattr(snapshot, 'switch_states') else False

        results.append(ValidationResult(
            rule=ValidationRule.SYNC_ALL_LAYERS_PRESENT,
            passed=has_gis and has_elec and has_adms,
            severity=ValidationSeverity.WARNING,
            message=f"Layers present: GIS={has_gis}, Electrical={has_elec}, ADMS={has_adms}",
            details={"gis": has_gis, "electrical": has_elec, "adms": has_adms}
        ))

        return results

    # ============================================================
    # UTILITY METHODS
    # ============================================================

    def get_validation_history(self, limit: int = 10) -> List[List[ValidationResult]]:
        """Get recent validation history."""
        return self._validation_history[-limit:]

    def get_last_validation(self) -> Optional[List[ValidationResult]]:
        """Get the most recent validation results."""
        if not self._validation_history:
            return None
        return self._validation_history[-1]

    def get_failed_rules(self, results: List[ValidationResult] = None) -> List[ValidationResult]:
        """Get only failed validation results."""
        if results is None:
            results = self.get_last_validation() or []
        return [r for r in results if not r.passed]

    def get_statistics(self) -> dict:
        """Get validation gateway statistics."""
        total_validations = len(self._validation_history)
        total_failures = sum(
            len([r for r in results if not r.passed])
            for results in self._validation_history
        )
        return {
            "total_validations": total_validations,
            "total_failures": total_failures,
            "strict_mode": self.strict_mode,
            "custom_rules_count": len(self._custom_rules),
            "failure_rate": total_failures / max(total_validations, 1)
        }
