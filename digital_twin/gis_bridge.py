"""
GIS ↔ Digital Twin Synchronization Bridge
===========================================
Bidirectional synchronization between GIS (PostGIS/QGIS) and the
AhmedETAP Digital Twin.

Synchronization Flow:
  GIS Change -> PostGIS -> GIS Bridge -> Digital Twin Event Bus ->
  Topology Update -> Ybus Rebuild -> Load Flow -> State Update

  Digital Twin Change -> State Snapshot -> GIS Bridge -> PostGIS -> QGIS

Asset Mapping:
  GIS Object        | Electrical Object
  ------------------|------------------
  Substation Point  | Bus (slack/pv)
  Transformer Point | Transformer
  Feeder LineString | Line
  Switch Point      | Switch/Breaker
  Load Area Polygon | Load
  Generator Point   | Generator
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from digital_twin.event_bus import (
    DigitalTwinStateUpdated,
    DomainEvent,
    EventBus,
    EventType,
    SwitchClosed,
    SwitchOpened,
    TopologyChanged,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GIS ↔ Electrical Asset Mapping
# ---------------------------------------------------------------------------

GIS_TO_ELECTRICAL_MAP: dict[str, str] = {
    "substation": "bus",
    "bus": "bus",
    "transformer": "transformer",
    "feeder": "line",
    "line": "line",
    "switch": "switch",
    "breaker": "switch",
    "load": "load",
    "generator": "generator",
    "capacitor": "load",
    "recloser": "switch",
    "fuse": "switch",
    "sectionalizer": "switch",
}

ELECTRICAL_TO_GIS_MAP: dict[str, str] = {
    "bus": "substation",
    "transformer": "transformer",
    "line": "feeder",
    "switch": "switch",
    "load": "load",
    "generator": "generator",
}


@dataclass
class SyncRecord:
    """A single synchronization record."""

    direction: str  # gis_to_dt or dt_to_gis
    asset_id: str
    asset_type: str
    action: str  # created, updated, deleted
    success: bool
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class GISSyncBridge:
    """Bidirectional sync between GIS (PostGIS/QGIS) and Digital Twin.

    Parameters
    ----------
    dt_state : DigitalTwinState
        The unified digital twin state.
    event_bus : EventBus
        Event bus for publishing sync-driven events.
    postgis : PostGISProvider, optional
        PostGIS provider for spatial persistence.
    """

    def __init__(
        self,
        dt_state: Any,
        event_bus: EventBus,
        postgis: Any = None,
    ):
        self.dt_state = dt_state
        self.event_bus = event_bus
        self.postgis = postgis
        self._sync_log: list[SyncRecord] = []
        self._subscribed = False
        self._ensure_subscriptions()

    def _ensure_subscriptions(self) -> None:
        if not self._subscribed:
            self.event_bus.subscribe(
                EventType.DIGITAL_TWIN_STATE_UPDATED,
                self._on_dt_state_updated,
                priority=5,
            )
            self.event_bus.subscribe(
                EventType.SWITCH_OPENED,
                self._on_switch_change,
                priority=5,
            )
            self.event_bus.subscribe(
                EventType.SWITCH_CLOSED,
                self._on_switch_change,
                priority=5,
            )
            self._subscribed = True

    # ------------------------------------------------------------------
    # Direction: GIS -> Digital Twin
    # ------------------------------------------------------------------

    def sync_gis_to_digital_twin(self) -> list[SyncRecord]:
        """Pull changes from PostGIS and push them into the digital twin.

        Step-by-step:
        1. Query PostGIS for all spatial assets
        2. Map GIS asset types to electrical types
        3. Update the electrical model (System.buses, etc.)
        4. Rebuild Ybus and publish topology event
        5. Validate the digital twin state
        """
        records = []
        if self.postgis is None:
            logger.warning("No PostGIS provider bound — cannot sync GIS -> DT")
            return records

        all_assets = self.postgis.get_all_assets()
        logger.info("GIS sync: found %d assets in PostGIS", len(all_assets))

        for asset in all_assets:
            record = self._sync_gis_asset(asset)
            records.append(record)

        # After all assets are synced, trigger topology rebuild
        if self.dt_state.system is not None:
            try:
                self.dt_state.system.Ybus_seq.clear()
                self.dt_state.system.build_ybus(seq="1")
                self.event_bus.publish(
                    TopologyChanged(
                        change_description=f"GIS sync: {len(all_assets)} assets processed",
                        source="gis_bridge",
                    ),
                )
                logger.info("GIS sync: Ybus rebuilt after %d assets", len(all_assets))
            except Exception as exc:
                logger.exception("GIS sync: Ybus rebuild failed: %s", exc)

        self._sync_log.extend(records)
        return records

    def _sync_gis_asset(self, asset: Any) -> SyncRecord:
        """Sync a single GIS asset into the electrical model."""
        gis_type = asset.asset_type.lower()
        electrical_type = GIS_TO_ELECTRICAL_MAP.get(gis_type, gis_type)
        electrical_id = asset.electrical_id or asset.asset_id

        try:
            geometry = asset.geometry
            coords = self._extract_coords(geometry)

            if self.dt_state.system is None:
                return SyncRecord(
                    direction="gis_to_dt",
                    asset_id=asset.asset_id,
                    asset_type=gis_type,
                    action="skipped",
                    success=False,
                    details={"error": "No electrical model bound"},
                )

            # Map to electrical model based on type
            if electrical_type in ("bus", "substation"):
                self._upsert_bus(electrical_id, coords)
            elif electrical_type == "transformer":
                self._upsert_transformer(electrical_id, coords)
            elif electrical_type == "line":
                self._upsert_line(electrical_id, coords, geometry)
            elif electrical_type == "switch":
                self._upsert_switch(electrical_id, coords)
            elif electrical_type == "load":
                self._upsert_load(electrical_id, coords, asset.properties)
            elif electrical_type == "generator":
                self._upsert_generator(electrical_id, coords, asset.properties)

            return SyncRecord(
                direction="gis_to_dt",
                asset_id=asset.asset_id,
                asset_type=gis_type,
                action="created",
                success=True,
                details={"electrical_type": electrical_type, "electrical_id": electrical_id},
            )
        except Exception as exc:
            logger.exception("GIS sync failed for %s: %s", asset.asset_id, exc)
            return SyncRecord(
                direction="gis_to_dt",
                asset_id=asset.asset_id,
                asset_type=gis_type,
                action="error",
                success=False,
                details={"error": str(exc)},
            )

    def _upsert_bus(self, bus_id: str, _coords: tuple | None) -> None:
        """Create or update a bus in the electrical model."""
        from core_model.bus import Bus

        try:
            bid = int(bus_id) if bus_id.isdigit() else abs(hash(bus_id)) % 99999 + 1
        except (ValueError, TypeError):
            bid = abs(hash(bus_id)) % 99999 + 1

        if bid not in self.dt_state.system.buses:
            bus = Bus(
                bus_id=bid,
                voltage_magnitude=1.0,
                voltage_angle=0.0,
                bus_type="pq" if bid != 1 else "slack",
                base_kv=11.0,
            )
            self.dt_state.system.add_bus(bus)

    def _upsert_transformer(self, xf_id: str, _coords: tuple | None) -> None:
        """Create or update a transformer in the electrical model."""
        from core_model.transformer import Transformer

        xid = int(xf_id.split("_")[-1]) if "_" in xf_id else int(xf_id) if xf_id.isdigit() else 1
        # Ensure the transformer exists — default to unit transformer if buses not yet present
        existing = [t for t in self.dt_state.system.transformers if t.transformer_id == xid]
        if not existing:
            buses = list(self.dt_state.system.buses.values())
            if len(buses) >= 2:
                xf = Transformer(
                    transformer_id=xid,
                    from_bus=buses[0],
                    to_bus=buses[-1],
                    z1=complex(0.01, 0.05),
                    tap_ratio=1.0,
                    phase_shift=0.0,
                )
                self.dt_state.system.add_transformer(xf)

    def _upsert_line(self, line_id: str, _coords: tuple | None, _geometry: dict) -> None:
        """Create or update a line in the electrical model."""
        from core_model.line import Line

        lid = (
            int(line_id.split("_")[-1])
            if "_" in line_id
            else int(line_id)
            if line_id.isdigit()
            else 1
        )
        existing = [l for l in self.dt_state.system.lines if l.line_id == lid]
        if not existing:
            buses = list(self.dt_state.system.buses.values())
            if len(buses) >= 2:
                from_idx = (lid - 1) % len(buses)
                to_idx = lid % len(buses)
                line = Line(
                    line_id=lid,
                    from_bus=buses[from_idx],
                    to_bus=buses[to_idx],
                    z1=complex(0.01, 0.05),
                )
                self.dt_state.system.add_line(line)

    def _upsert_switch(self, switch_id: str, _coords: tuple | None) -> None:
        """Register a switch in the digital twin."""
        if self.dt_state.adms is not None:
            if hasattr(self.dt_state.adms, "topology") and hasattr(
                self.dt_state.adms.topology, "switches",
            ) and switch_id not in self.dt_state.adms.topology.switches:
                buses = list(self.dt_state.system.buses.keys()) if self.dt_state.system else []
                if len(buses) >= 2:
                    bus1 = str(buses[0])
                    bus2 = str(buses[-1])
                    self.dt_state.adms.topology.switches[switch_id] = (bus1, bus2)

    def _upsert_load(self, load_id: str, _coords: tuple | None, props: dict) -> None:
        """Create or update a load in the electrical model."""
        from core_model.load import Load

        lid = (
            int(load_id.split("_")[-1])
            if "_" in load_id
            else int(load_id)
            if load_id.isdigit()
            else 1
        )
        existing = [l for l in self.dt_state.system.loads if l.load_id == lid]
        if not existing and self.dt_state.system.buses:
            first_bus = list(self.dt_state.system.buses.values())[0]
            p_mw = float(props.get("load_mw", 0))
            q_mvar = float(props.get("load_mvar", 0))
            load = Load(
                load_id=lid,
                bus=first_bus,
                load_power=complex(
                    p_mw / max(self.dt_state.system.base_mva, 1),
                    q_mvar / max(self.dt_state.system.base_mva, 1),
                ),
            )
            self.dt_state.system.add_load(load)

    def _upsert_generator(self, gen_id: str, _coords: tuple | None, _props: dict) -> None:
        """Create or update a generator in the electrical model."""
        from core_model.generator import Generator

        gid = (
            int(gen_id.split("_")[-1]) if "_" in gen_id else int(gen_id) if gen_id.isdigit() else 1
        )
        existing = [g for g in self.dt_state.system.generators if g.generator_id == gid]
        if not existing and self.dt_state.system.buses:
            first_bus = list(self.dt_state.system.buses.values())[0]
            gen = Generator(
                generator_id=gid,
                bus=first_bus,
                internal_voltage={"1": complex(1.05, 0), "2": complex(0, 0), "0": complex(0, 0)},
                impedance={"1": complex(0, 0.2), "2": complex(0, 0.2), "0": complex(0, 0.1)},
            )
            self.dt_state.system.add_generator(gen)

    # ------------------------------------------------------------------
    # Direction: Digital Twin -> GIS
    # ------------------------------------------------------------------

    def _on_dt_state_updated(self, event: DomainEvent) -> None:
        """Handle DT state update by syncing back to GIS."""
        if not isinstance(event, DigitalTwinStateUpdated):
            return
        self.sync_digital_twin_to_gis()

    def _on_switch_change(self, event: DomainEvent) -> None:
        """Handle switch change by syncing switch state to GIS."""
        if isinstance(event, (SwitchOpened, SwitchClosed)):
            switch_id = event.switch_id
            is_closed = isinstance(event, SwitchClosed)
            if self.postgis is not None:
                asset = self.postgis.get_asset(switch_id)
                if asset:
                    asset.properties["is_closed"] = is_closed
                    self.postgis.upsert_asset(asset)

    def sync_digital_twin_to_gis(self) -> list[SyncRecord]:
        """Push digital twin state changes back to PostGIS/QGIS.

        Captures a current snapshot and writes bus states, switch states,
        and simulation results as spatial assets.
        """
        records = []
        if self.postgis is None:
            logger.warning("No PostGIS provider — cannot sync DT -> GIS")
            return records

        snapshot = (
            self.dt_state.get_current_snapshot()
            if hasattr(self.dt_state, "get_current_snapshot")
            else None
        )
        if snapshot is None:
            logger.warning("No DT snapshot available — cannot sync to GIS")
            return records

        # Sync bus states
        for bid, bus_state in snapshot.bus_states.items():
            try:
                from gis_integration.providers.postgis_provider import SpatialAsset

                existing = self.postgis.get_asset(bid)
                # Build geometry from lat/lon if available
                gis_asset = snapshot.gis_assets.get(bid)
                geometry = None
                if gis_asset and (gis_asset.latitude or gis_asset.longitude):
                    geometry = {
                        "type": "Point",
                        "coordinates": [gis_asset.longitude, gis_asset.latitude],
                    }
                elif existing and existing.geometry:
                    geometry = existing.geometry

                # Remove old entry without geometry if we can't position it
                if geometry is None:
                    continue

                asset = SpatialAsset(
                    asset_id=bid,
                    asset_type="bus",
                    geometry=geometry,
                    properties={
                        "voltage_magnitude": bus_state.voltage_magnitude,
                        "voltage_angle": bus_state.voltage_angle,
                        "load_power_real": bus_state.load_power.real,
                        "load_power_imag": bus_state.load_power.imag,
                        "generation_real": bus_state.generation_power.real,
                        "generation_imag": bus_state.generation_power.imag,
                        "bus_type": bus_state.bus_type,
                        "source": "digital_twin",
                        "synced_at": time.time(),
                    },
                    electrical_id=bid,
                )
                self.postgis.upsert_asset(asset)
                records.append(
                    SyncRecord(
                        direction="dt_to_gis",
                        asset_id=bid,
                        asset_type="bus",
                        action="updated",
                        success=True,
                    ),
                )
            except Exception as exc:
                logger.warning("DT->GIS sync failed for bus %s: %s", bid, exc)

        # Sync switch states
        for sid, switch_state in snapshot.switch_states.items():
            try:
                from gis_integration.providers.postgis_provider import SpatialAsset

                existing = self.postgis.get_asset(sid)
                geometry = existing.geometry if existing else None

                if geometry is None:
                    gis_asset = snapshot.gis_assets.get(sid)
                    if gis_asset and (gis_asset.latitude or gis_asset.longitude):
                        geometry = {
                            "type": "Point",
                            "coordinates": [gis_asset.longitude, gis_asset.latitude],
                        }
                if geometry is None:
                    continue

                asset = SpatialAsset(
                    asset_id=sid,
                    asset_type="switch",
                    geometry=geometry,
                    properties={
                        "is_closed": switch_state.is_closed,
                        "from_bus": switch_state.from_bus,
                        "to_bus": switch_state.to_bus,
                        "trip_count": switch_state.trip_count,
                        "source": "digital_twin",
                        "synced_at": time.time(),
                    },
                    electrical_id=sid,
                )
                self.postgis.upsert_asset(asset)
            except Exception as exc:
                logger.warning("DT->GIS sync failed for switch %s: %s", sid, exc)

        # Sync simulation results
        try:
            sim = snapshot.simulation_results
            if sim and hasattr(sim, "load_flow_converged"):
                metadata_asset = self.postgis.get_asset("_simulation_metadata")
                from gis_integration.providers.postgis_provider import SpatialAsset

                if metadata_asset:
                    metadata_asset.properties.update(
                        {
                            "load_flow_converged": sim.load_flow_converged,
                            "protection_coordination_ok": sim.protection_coordination_ok,
                            "state_estimation_converged": sim.state_estimation_converged,
                            "synced_at": time.time(),
                        },
                    )
                    self.postgis.upsert_asset(metadata_asset)
        except Exception as exc:
            logger.warning("DT->GIS simulation sync failed: %s", exc)

        self._sync_log.extend(records)
        logger.info("DT->GIS: synced %d assets", len(records))
        return records

    # ------------------------------------------------------------------
    # Electrical Network Mapping
    # ------------------------------------------------------------------

    def build_electrical_network_map(self) -> dict[str, Any]:
        """Build a complete GIS-compatible electrical network map.

        Returns a GeoJSON FeatureCollection with:
        - Bus points (colored by voltage)
        - Line features (with impedance/rating)
        - Switch points (colored by state)
        - Transformer symbols
        - Load symbols
        - Generator symbols
        """
        features = []

        if self.dt_state.system is None:
            return {"type": "FeatureCollection", "features": []}

        # Map buses
        for bid, bus in self.dt_state.system.buses.items():
            feat = self._build_bus_feature(bid, bus)
            if feat:
                features.append(feat)

        # Map lines
        for line in self.dt_state.system.lines:
            feat = self._build_line_feature(line)
            if feat:
                features.append(feat)

        # Map transformers
        for xf in self.dt_state.system.transformers:
            feat = self._build_transformer_feature(xf)
            if feat:
                features.append(feat)

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "bus_count": len(self.dt_state.system.buses),
                "line_count": len(self.dt_state.system.lines),
                "transformer_count": len(self.dt_state.system.transformers),
                "generator_count": len(self.dt_state.system.generators),
                "load_count": len(self.dt_state.system.loads),
                "source": "ahmed_etap_digital_twin",
            },
        }

    def _build_bus_feature(self, bid, bus) -> dict[str, Any] | None:
        """Build a GeoJSON Feature for a bus."""
        coord = self._get_bus_coordinates(bid)
        if coord is None:
            return None
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": list(coord)},
            "properties": {
                "asset_type": "bus",
                "electrical_id": str(bid),
                "voltage_magnitude_pu": bus.voltage_magnitude,
                "voltage_angle_deg": bus.voltage_angle,
                "bus_type": bus.bus_type,
                "load_power_mw": bus.load_power.real * self.dt_state.system.base_mva,
                "generation_mw": bus.generation_power.real * self.dt_state.system.base_mva,
                "base_kv": bus.base_kv or 11.0,
            },
        }

    def _build_line_feature(self, line) -> dict[str, Any] | None:
        """Build a GeoJSON Feature for a line."""
        from_bus = line.from_bus
        to_bus = line.to_bus
        from_coord = self._get_bus_coordinates(from_bus.bus_id)
        to_coord = self._get_bus_coordinates(to_bus.bus_id)
        if from_coord is None or to_coord is None:
            return None
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [list(from_coord), list(to_coord)],
            },
            "properties": {
                "asset_type": "line",
                "electrical_id": f"line_{line.line_id}",
                "r1_pu": line.z1.real,
                "x1_pu": line.z1.imag,
                "from_bus": str(from_bus.bus_id),
                "to_bus": str(to_bus.bus_id),
                "rating_mva": line.rating or 100,
            },
        }

    def _build_transformer_feature(self, xf) -> dict[str, Any] | None:
        """Build a GeoJSON Feature for a transformer."""
        from_coord = self._get_bus_coordinates(xf.from_bus.bus_id)
        to_coord = self._get_bus_coordinates(xf.to_bus.bus_id)
        if from_coord is None or to_coord is None:
            return None
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [list(from_coord), list(to_coord)],
            },
            "properties": {
                "asset_type": "transformer",
                "electrical_id": f"xf_{xf.transformer_id}",
                "r1_pu": xf.z1.real,
                "x1_pu": xf.z1.imag,
                "tap_ratio": xf.tap_ratio,
                "phase_shift_deg": xf.phase_shift,
            },
        }

    def _get_bus_coordinates(self, bus_id) -> tuple | None:
        """Try to get GIS coordinates for a bus from PostGIS."""
        if self.postgis is not None:
            asset = self.postgis.get_asset(str(bus_id))
            if asset and asset.geometry:
                return self._extract_coords(asset.geometry)
            # Try electrical_id lookup
            mapping = self.postgis.map_electrical_to_gis([str(bus_id)])
            if str(bus_id) in mapping:
                geom = mapping[str(bus_id)].get("geometry")
                if geom:
                    return self._extract_coords(geom)
        return None

    @staticmethod
    def _extract_coords(geometry: dict | None) -> tuple | None:
        """Extract (lon, lat) from a GeoJSON geometry dict."""
        if geometry is None:
            return None
        gtype = geometry.get("type")
        coords = geometry.get("coordinates")
        if not coords:
            return None
        if gtype == "Point":
            return (coords[0], coords[1])
        if gtype in ("LineString", "MultiPoint"):
            # coords is guaranteed non-empty by the early return above
            # (SonarCloud S2583 flagged the redundant `if coords` check).
            return (coords[0][0], coords[0][1])
        return None

    # ------------------------------------------------------------------
    # Sync Log
    # ------------------------------------------------------------------

    def get_sync_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent sync activity."""
        recent = self._sync_log[-limit:]
        return [
            {
                "direction": r.direction,
                "asset_id": r.asset_id,
                "asset_type": r.asset_type,
                "action": r.action,
                "success": r.success,
                "details": r.details,
                "timestamp": r.timestamp,
            }
            for r in recent
        ]

    def get_sync_statistics(self) -> dict[str, Any]:
        """Get sync statistics."""
        total = len(self._sync_log)
        success = sum(1 for r in self._sync_log if r.success)
        gis_to_dt = sum(1 for r in self._sync_log if r.direction == "gis_to_dt")
        dt_to_gis = sum(1 for r in self._sync_log if r.direction == "dt_to_gis")
        return {
            "total_syncs": total,
            "successful": success,
            "failed": total - success,
            "gis_to_dt": gis_to_dt,
            "dt_to_gis": dt_to_gis,
            "postgis_connected": self.postgis.is_connected() if self.postgis else False,
        }

    def run_full_sync(self) -> dict[str, Any]:
        """Run a full bidirectional sync cycle.

        1. GIS -> DT: pull spatial assets, update electrical model
        2. DT -> GIS: push state snapshots and results back
        3. Return sync statistics
        """
        start = time.time()
        gis_records = self.sync_gis_to_digital_twin()
        dt_records = self.sync_digital_twin_to_gis()
        elapsed = time.time() - start
        return {
            "success": all(r.success for r in gis_records + dt_records),
            "gis_to_dt_count": len(gis_records),
            "dt_to_gis_count": len(dt_records),
            "total_assets": len(gis_records) + len(dt_records),
            "elapsed_seconds": round(elapsed, 3),
            "timestamp": time.time(),
        }
