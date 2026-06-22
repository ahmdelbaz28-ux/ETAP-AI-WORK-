"""
GIS Map Visualization — Engineering Results on Geographic Maps
===============================================================
Produces folium/leaflet interactive maps overlaying engineering study
results (load flow, voltage profiles, fault currents, arc flash, protection)
on geographic basemaps.

Every method returns a folium Map object that can be:
- Displayed in Jupyter notebooks
- Saved to standalone HTML files
- Embedded in web dashboards
- Exported as GeoJSON for QGIS import

Supported Visualizations:
- Load Flow: voltage contours, power flow arrows, bus labels
- Voltage Profile: color-coded buses by voltage magnitude
- Fault Analysis: fault current markers with severity coloring
- Arc Flash: incident energy heat map at each bus
- Protection Coordination: relay coverage zones
- Full network: complete electrical network overlay
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy folium import
# ---------------------------------------------------------------------------

_HAS_FOLIUM = False
try:
    import folium  # type: ignore
    from folium.plugins import HeatMap, MarkerCluster  # type: ignore

    _HAS_FOLIUM = True
except ImportError:
    logger.warning(
        "folium not installed. GIS visualization will return GeoJSON/HTML "
        "templates instead. Install: pip install folium"
    )


# ---------------------------------------------------------------------------
# Color scales
# ---------------------------------------------------------------------------

VOLTAGE_COLORS = {
    "excellent": "#00cc00",  # > 1.02 pu
    "good": "#66cc00",  # 0.98 - 1.02
    "fair": "#cccc00",  # 0.95 - 0.98
    "poor": "#cc6600",  # 0.90 - 0.95
    "critical": "#cc0000",  # < 0.90
}

FAULT_SEVERITY_COLORS = {
    "low": "#00cc00",  # < 5 kA
    "medium": "#cccc00",  # 5 - 15 kA
    "high": "#cc6600",  # 15 - 30 kA
    "severe": "#cc0000",  # 30 - 50 kA
    "extreme": "#990000",  # > 50 kA
}

ARC_FLASH_COLORS = {
    "safe": "#00cc00",  # < 1.2 cal/cm2 (Category 0)
    "low": "#66cc00",  # 1.2 - 4 (Category 1)
    "medium": "#cccc00",  # 4 - 8 (Category 2)
    "high": "#cc6600",  # 8 - 25 (Category 3)
    "severe": "#cc0000",  # 25 - 40 (Category 4)
    "extreme": "#990000",  # > 40 (Category 4+)
}

PPE_LEVELS = {
    "0": "PPE Level 0 - No PPE Required",
    "1": "PPE Level 1 - FR Shirt & Pants",
    "2": "PPE Level 2 - FR Coat & Pants",
    "3": "PPE Level 3 - Double Layer Switching Coat & Pants",
    "4": "PPE Level 4 - FR Flash Suit",
}


# ---------------------------------------------------------------------------
# GIS Visualizer
# ---------------------------------------------------------------------------


class GISVisualizer:
    """Create interactive GIS maps with engineering study overlays.

    Parameters
    ----------
    center_lat : float
        Map center latitude (default: 30.0 for generic placement).
    center_lon : float
        Map center longitude (default: 31.0).
    zoom_start : int
        Initial zoom level (default: 10).
    tile_layer : str
        Basemap tile layer URL template.
    """

    def __init__(
        self,
        center_lat: float = 30.0,
        center_lon: float = 31.0,
        zoom_start: int = 10,
        tile_layer: str = "OpenStreetMap",
    ):
        self.center = (center_lat, center_lon)
        self.zoom = zoom_start
        self.tile_layer = tile_layer
        self._last_map = None

    def _create_base_map(self) -> Any:
        """Create the base folium Map."""
        if not _HAS_FOLIUM:
            return None

        # Determine tile URL based on layer name
        tile_urls = {
            "OpenStreetMap": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "Satellite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "Terrain": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            "Light": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            "Dark": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        }
        tile = tile_urls.get(self.tile_layer, tile_urls["OpenStreetMap"])
        attr = "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>"

        m = folium.Map(
            location=self.center,
            zoom_start=self.zoom,
            tiles=tile,
            attr=attr,
            control_scale=True,
        )

        # Add fullscreen button
        try:
            from folium.plugins import Fullscreen

            Fullscreen().add_to(m)
        except Exception:
            pass

        # Add layer control
        folium.LayerControl().add_to(m)

        return m

    def _add_bus_marker(
        self,
        m: Any,
        coord: Tuple[float, float],
        label: str,
        color: str,
        popup_text: str,
        radius: int = 8,
    ) -> None:
        """Add a colored circle marker for a bus."""
        if not _HAS_FOLIUM:
            return

        folium.CircleMarker(
            location=[coord[1], coord[0]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            weight=2,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=label,
        ).add_to(m)

    def _add_line_feature(
        self,
        m: Any,
        coords: List[Tuple[float, float]],
        color: str,
        weight: int = 2,
        popup_text: str = "",
    ) -> None:
        """Add a line/polyline feature."""
        if not _HAS_FOLIUM or len(coords) < 2:
            return

        # Convert from [lon, lat] to (lat, lon) for folium
        latlngs = [(c[1], c[0]) for c in coords]

        folium.PolyLine(
            locations=latlngs,
            color=color,
            weight=weight,
            opacity=0.8,
            popup=folium.Popup(popup_text, max_width=300) if popup_text else None,
        ).add_to(m)

    # ------------------------------------------------------------------
    # Load Flow Visualization
    # ------------------------------------------------------------------

    def visualize_load_flow(
        self,
        buses: Dict[str, Dict[str, Any]],
        lines: List[Dict[str, Any]] | None = None,
        bus_coords: Dict[str, Tuple[float, float]] | None = None,
        title: str = "Load Flow Results",
        output_path: str | None = None,
    ) -> Any:
        """Visualize load flow results on a geographic map.

        Parameters
        ----------
        buses : dict
            Dict of bus_id -> {voltage_magnitude, voltage_angle, bus_type, ...}
        lines : list, optional
            List of line dicts with from_bus, to_bus, loading_pct, etc.
        bus_coords : dict, optional
            Dict of bus_id -> (lon, lat). If None, uses center point.
        title : str
            Map title.
        output_path : str, optional
            Path to save HTML file. If None, returns map object.

        Returns
        -------
        folium.Map or str
            Map object or path to saved HTML file.
        """
        m = self._create_base_map()
        if m is None:
            return self._fallback_geojson("load_flow", buses)

        # Add title
        self._add_title(m, title)

        # Color buses by voltage magnitude
        for bid, bus_data in buses.items():
            vm = bus_data.get("voltage_magnitude", 1.0)
            coord = bus_coords.get(str(bid)) if bus_coords else None
            if coord is None:
                coord = self._assign_coordinates(
                    bid, list(buses.keys()).index(str(bid)) if str(bid) in buses else 0, len(buses)
                )

            color = self._voltage_color(vm)
            va_deg = bus_data.get("voltage_angle", 0.0)
            if isinstance(va_deg, (int, float)):
                va_deg = float(va_deg)
            else:
                va_deg = 0.0

            popup = (
                f"<b>Bus: {bid}</b><br>"
                f"Voltage: {vm:.4f} pu<br>"
                f"Angle: {va_deg:.2f}°<br>"
                f"Type: {bus_data.get('bus_type', 'N/A')}<br>"
                f"P: {bus_data.get('active_power', 0):.2f} MW<br>"
                f"Q: {bus_data.get('reactive_power', 0):.2f} MVAr"
            )

            self._add_bus_marker(
                m,
                coord,
                str(bid),
                color,
                popup,
                radius=10 if bus_data.get("bus_type") == "slack" else 8,
            )

        # Draw lines between buses
        if lines and bus_coords:
            for line in lines:
                from_id = str(line.get("from_bus", line.get("from_bus_id", "")))
                to_id = str(line.get("to_bus", line.get("to_bus_id", "")))
                if from_id in bus_coords and to_id in bus_coords:
                    loading = line.get("loading_percent", 0)
                    color = "#cc0000" if loading and loading > 90 else "#0066cc"
                    popup = (
                        f"<b>Line: {line.get('line_id', line.get('id', 'N/A'))}</b><br>"
                        f"From: {from_id} → To: {to_id}<br>"
                        f"Loading: {loading:.1f}%<br>"
                        f"P: {line.get('active_power_from', 0):.2f} MW"
                    )
                    self._add_line_feature(
                        m,
                        [bus_coords[from_id], bus_coords[to_id]],
                        color,
                        weight=3 if loading and loading > 90 else 2,
                        popup_text=popup,
                    )

        # Add legend
        self._add_voltage_legend(m)

        # Add marker cluster for dense networks
        try:
            MarkerCluster().add_to(m)
        except Exception:
            pass

        return self._save_or_return(m, output_path)

    # ------------------------------------------------------------------
    # Voltage Profile Visualization
    # ------------------------------------------------------------------

    def visualize_voltage_profile(
        self,
        buses: Dict[str, Dict[str, Any]],
        bus_coords: Dict[str, Tuple[float, float]] | None = None,
        title: str = "Voltage Profile Map",
        output_path: str | None = None,
    ) -> Any:
        """Visualize voltage profile with color-coded buses and contour overlay."""
        m = self._create_base_map()
        if m is None:
            return self._fallback_geojson("voltage_profile", buses)

        self._add_title(m, title)

        voltage_values = []
        for idx, (bid, bus_data) in enumerate(buses.items()):
            vm = bus_data.get("voltage_magnitude", 1.0)
            coord = bus_coords.get(str(bid)) if bus_coords else None
            if coord is None:
                coord = self._assign_coordinates(bid, idx, len(buses))
            color = self._voltage_color(vm)

            popup = (
                f"<b>Bus: {bid}</b><br>"
                f"Voltage: {vm:.4f} pu<br>"
                f"Deviation: {(vm - 1.0) * 100:.2f}%<br>"
                f"Type: {bus_data.get('bus_type', 'N/A')}"
            )

            self._add_bus_marker(
                m, coord, f"{bid} ({vm:.3f})", color, popup, radius=10 - abs(vm - 1.0) * 5 + 5
            )
            voltage_values.append(
                {
                    "lat": coord[1],
                    "lon": coord[0],
                    "voltage": vm,
                }
            )

        # Add heatmap layer for voltage distribution
        try:
            heat_data = [[v["lat"], v["lon"], v["voltage"]] for v in voltage_values]
            HeatMap(
                heat_data,
                min_opacity=0.3,
                max_zoom=15,
                radius=20,
                gradient={
                    0.85: "red",
                    0.90: "orange",
                    0.95: "yellow",
                    1.0: "lime",
                    1.05: "green",
                },
            ).add_to(m)
        except Exception:
            pass

        self._add_voltage_legend(m)
        return self._save_or_return(m, output_path)

    # ------------------------------------------------------------------
    # Fault Visualization
    # ------------------------------------------------------------------

    def visualize_fault_analysis(
        self,
        fault_currents: Dict[str, Dict[str, Any]],
        bus_coords: Dict[str, Tuple[float, float]] | None = None,
        fault_type: str = "Three Phase",
        title: str = "Fault Analysis Results",
        output_path: str | None = None,
    ) -> Any:
        """Visualize fault current magnitudes at each bus.

        Colors indicate severity:
        - Green: < 5 kA (low)
        - Yellow: 5-15 kA (medium)
        - Orange: 15-30 kA (high)
        - Red: 30-50 kA (severe)
        - Dark Red: > 50 kA (extreme)
        """
        m = self._create_base_map()
        if m is None:
            return self._fallback_geojson("fault_analysis", fault_currents)

        self._add_title(m, f"{title} ({fault_type})")

        for idx, (bid, fc_data) in enumerate(fault_currents.items()):
            # Get the fault current for the specified type or three_phase
            fc_ka = fc_data.get(
                f"{fault_type.lower().replace(' ', '_')}_ka",
                fc_data.get("three_phase_ka", fc_data.get("fault_current_ka", 0)),
            )
            coord = bus_coords.get(str(bid)) if bus_coords else None
            if coord is None:
                coord = self._assign_coordinates(bid, idx, len(fault_currents))

            color = self._fault_severity_color(fc_ka)
            radius = min(max(fc_ka * 0.5, 5), 20)

            popup = (
                f"<b>Bus: {bid}</b><br>"
                f"Fault Current: {fc_ka:.2f} kA<br>"
                f"Fault Type: {fault_type}<br>"
                f"Severity: {self._fault_severity_label(fc_ka)}"
            )

            self._add_bus_marker(
                m, coord, f"{bid}: {fc_ka:.1f} kA", color, popup, radius=int(radius)
            )

        # Add fault legend
        self._add_legend(
            m,
            items=[
                ("#00cc00", "Low (< 5 kA)"),
                ("#cccc00", "Medium (5-15 kA)"),
                ("#cc6600", "High (15-30 kA)"),
                ("#cc0000", "Severe (30-50 kA)"),
                ("#990000", "Extreme (> 50 kA)"),
            ],
            title="Fault Severity",
        )

        return self._save_or_return(m, output_path)

    # ------------------------------------------------------------------
    # Arc Flash Visualization
    # ------------------------------------------------------------------

    def visualize_arc_flash(
        self,
        arc_flash_results: Dict[str, Dict[str, Any]],
        bus_coords: Dict[str, Tuple[float, float]] | None = None,
        title: str = "Arc Flash Risk Assessment",
        output_path: str | None = None,
    ) -> Any:
        """Visualize arc flash incident energy at each bus.

        Colors indicate PPE category:
        - Green: < 1.2 cal/cm2 (Cat 0)
        - Light: 1.2-4 (Cat 1)
        - Yellow: 4-8 (Cat 2)
        - Orange: 8-25 (Cat 3)
        - Red: 25-40 (Cat 4)
        - Dark Red: > 40 (Cat 4+)
        """
        m = self._create_base_map()
        if m is None:
            return self._fallback_geojson("arc_flash", arc_flash_results)

        self._add_title(m, title)

        heat_data = []
        for idx, (bid, af_data) in enumerate(arc_flash_results.items()):
            ie = af_data.get("incident_energy_cal_cm2", 0)
            coord = bus_coords.get(str(bid)) if bus_coords else None
            if coord is None:
                coord = self._assign_coordinates(bid, idx, len(arc_flash_results))

            color = self._arc_flash_color(ie)
            radius = min(max(ie * 1.5, 5), 25)
            ppe_level = af_data.get("ppe_level", "N/A")
            ppe_desc = PPE_LEVELS.get(str(ppe_level), f"PPE Level {ppe_level}")

            popup = (
                f"<b>Bus: {bid}</b><br>"
                f"Incident Energy: {ie:.2f} cal/cm²<br>"
                f"Arc Flash Boundary: {af_data.get('arc_flash_boundary_mm', 0):.0f} mm<br>"
                f"PPE Level: {ppe_level} — {ppe_desc}<br>"
                f"Arc Duration: {af_data.get('arc_duration_sec', 0):.3f} s<br>"
                f"Method: {af_data.get('method', 'IEEE 1584')}"
            )

            self._add_bus_marker(
                m, coord, f"{bid}: {ie:.1f} cal/cm²", color, popup, radius=int(radius)
            )

            # Collect for heatmap
            lat = coord[1]
            lon = coord[0]
            heat_data.append([lat, lon, min(ie / 40, 1.0)])  # Normalized to 0-1

        # Add incident energy heatmap
        try:
            if heat_data:
                HeatMap(
                    heat_data,
                    min_opacity=0.2,
                    radius=25,
                    gradient={
                        0.0: "green",
                        0.2: "lime",
                        0.4: "yellow",
                        0.6: "orange",
                        0.8: "red",
                        1.0: "darkred",
                    },
                ).add_to(m)
        except Exception:
            pass

        self._add_legend(
            m,
            items=[
                ("#00cc00", "Cat 0: < 1.2 (< 1.2 cal/cm²)"),
                ("#66cc00", "Cat 1: 1.2-4"),
                ("#cccc00", "Cat 2: 4-8"),
                ("#cc6600", "Cat 3: 8-25"),
                ("#cc0000", "Cat 4: 25-40"),
                ("#990000", "Cat 4+: > 40"),
            ],
            title="Incident Energy",
        )

        return self._save_or_return(m, output_path)

    # ------------------------------------------------------------------
    # Protection Coordination Visualization
    # ------------------------------------------------------------------

    def visualize_protection_coordination(
        self,
        relay_data: Dict[str, Dict[str, Any]],
        bus_coords: Dict[str, Tuple[float, float]] | None = None,
        title: str = "Protection Coordination View",
        output_path: str | None = None,
    ) -> Any:
        """Visualize protection relay coverage and coordination status."""
        m = self._create_base_map()
        if m is None:
            return self._fallback_geojson("protection", relay_data)

        self._add_title(m, title)

        for idx, (rid, rdata) in enumerate(relay_data.items()):
            coord = bus_coords.get(str(rid)) if bus_coords else None
            if coord is None:
                coord = self._assign_coordinates(rid, idx, len(relay_data))

            all_coordinated = rdata.get("all_coordinated", rdata.get("coordinated", True))
            icon_type = "ok" if all_coordinated else "warning"

            popup = (
                f"<b>Relay: {rid}</b><br>"
                f"Coordinated: {'✓' if all_coordinated else '✗'}<br>"
                f"Curve Type: {rdata.get('curve_type', 'N/A')}<br>"
                f"TMS: {rdata.get('tms', 0):.3f}<br>"
                f"Results: {len(rdata.get('results', []))} fault levels checked"
            )

            if _HAS_FOLIUM:
                from folium import Icon

                icon = Icon(
                    color="green" if all_coordinated else "red", icon=icon_type, prefix="glyphicon"
                )
                folium.Marker(
                    location=[coord[1], coord[0]],
                    popup=folium.Popup(popup, max_width=300),
                    tooltip=rid,
                    icon=icon,
                ).add_to(m)

        return self._save_or_return(m, output_path)

    # ------------------------------------------------------------------
    # Full Network Visualization
    # ------------------------------------------------------------------

    def visualize_network_map(
        self,
        network_geojson: Dict[str, Any],
        title: str = "Electrical Network Map",
        output_path: str | None = None,
    ) -> Any:
        """Visualize the complete electrical network from a GeoJSON FeatureCollection."""
        m = self._create_base_map()
        if m is None:
            return self._fallback_geojson("network", network_geojson)

        self._add_title(m, title)

        # Parse features
        features = network_geojson.get("features", [])
        metadata = network_geojson.get("metadata", {})

        for feat in features:
            geom = feat.get("geometry", {})
            props = feat.get("properties", {})
            asset_type = props.get("asset_type", "unknown")

            if geom.get("type") == "Point":
                coords = geom.get("coordinates", [0, 0])
                color = self._asset_type_color(asset_type)
                popup = self._build_asset_popup(asset_type, props)
                self._add_bus_marker(
                    m,
                    (coords[0], coords[1]),
                    f"{asset_type}: {props.get('electrical_id', '')}",
                    color,
                    popup,
                    radius=8,
                )

            elif geom.get("type") == "LineString":
                line_coords = geom.get("coordinates", [])
                if len(line_coords) >= 2:
                    asset_type = props.get("asset_type", "line")
                    color = "#0066cc" if asset_type == "line" else "#cc6600"
                    popup = self._build_asset_popup(asset_type, props)
                    self._add_line_feature(
                        m,
                        line_coords,
                        color,
                        weight=3,
                        popup_text=popup,
                    )

        # Add feature count summary
        summary = ", ".join(f"{k}: {v}" for k, v in metadata.items() if k.endswith("_count"))
        if summary:
            self._add_legend(
                m,
                items=[
                    ("#0066cc", "Lines"),
                    ("#cc6600", "Transformers"),
                    ("#00cc00", "Buses (normal)"),
                    ("#cc0000", "Buses (alert)"),
                ],
                title=f"Network ({summary})",
            )

        return self._save_or_return(m, output_path)

    # ------------------------------------------------------------------
    # Combined Dashboard Map
    # ------------------------------------------------------------------

    def create_dashboard_map(
        self,
        load_flow_buses: Dict | None = None,
        fault_currents: Dict | None = None,
        arc_flash_results: Dict | None = None,
        network_geojson: Dict | None = None,
        bus_coords: Dict[str, Tuple[float, float]] | None = None,
        title: str = "AhmedETAP Engineering Dashboard",
        output_path: str | None = None,
    ) -> Any:
        """Create a combined dashboard with multiple data layers.

        Uses folium FeatureGroups to allow toggling layers on/off.
        """
        m = self._create_base_map()
        if m is None:
            return "Folium not available"

        self._add_title(m, title)

        try:
            from folium import FeatureGroup
        except ImportError:
            return self._save_or_return(m, output_path)

        # Network overlay
        if network_geojson:
            fg_network = FeatureGroup(name="Electrical Network", show=True)
            for feat in network_geojson.get("features", []):
                geom = feat.get("geometry", {})
                props = feat.get("properties", {})
                if geom.get("type") == "Point":
                    coords = geom.get("coordinates", [0, 0])
                    folium.CircleMarker(
                        location=[coords[1], coords[0]],
                        radius=6,
                        color="#0066cc",
                        fill=True,
                        popup=str(props.get("electrical_id", "")),
                    ).add_to(fg_network)
                elif geom.get("type") == "LineString":
                    line_coords = geom.get("coordinates", [])
                    folium.PolyLine(
                        locations=[(c[1], c[0]) for c in line_coords],
                        color="#0066cc",
                        weight=2,
                    ).add_to(fg_network)
            fg_network.add_to(m)

        # Load flow overlay
        if load_flow_buses:
            fg_lf = FeatureGroup(name="Load Flow", show=False)
            for bid, bus_data in load_flow_buses.items():
                vm = bus_data.get("voltage_magnitude", 1.0)
                coord = bus_coords.get(str(bid)) if bus_coords else None
                if coord is None:
                    continue
                color = self._voltage_color(vm)
                folium.CircleMarker(
                    location=[coord[1], coord[0]],
                    radius=8,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    popup=f"Bus {bid}: {vm:.4f} pu",
                ).add_to(fg_lf)
            fg_lf.add_to(m)

        # Fault overlay
        if fault_currents:
            fg_fault = FeatureGroup(name="Fault Currents", show=False)
            for bid, fc_data in fault_currents.items():
                fc = fc_data.get("three_phase_ka", 0)
                coord = bus_coords.get(str(bid)) if bus_coords else None
                if coord is None:
                    continue
                color = self._fault_severity_color(fc)
                folium.CircleMarker(
                    location=[coord[1], coord[0]],
                    radius=min(max(fc * 0.5, 5), 15),
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.5,
                    popup=f"Bus {bid}: {fc:.1f} kA",
                ).add_to(fg_fault)
            fg_fault.add_to(m)

        # Arc flash overlay
        if arc_flash_results:
            fg_af = FeatureGroup(name="Arc Flash", show=False)
            for bid, af_data in arc_flash_results.items():
                ie = af_data.get("incident_energy_cal_cm2", 0)
                coord = bus_coords.get(str(bid)) if bus_coords else None
                if coord is None:
                    continue
                color = self._arc_flash_color(ie)
                folium.CircleMarker(
                    location=[coord[1], coord[0]],
                    radius=min(max(ie, 5), 20),
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.5,
                    popup=f"Bus {bid}: {ie:.1f} cal/cm²",
                ).add_to(fg_af)
            fg_af.add_to(m)

        return self._save_or_return(m, output_path)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _voltage_color(vm: float) -> str:
        if vm >= 1.02:
            return VOLTAGE_COLORS["excellent"]
        elif vm >= 0.98:
            return VOLTAGE_COLORS["good"]
        elif vm >= 0.95:
            return VOLTAGE_COLORS["fair"]
        elif vm >= 0.90:
            return VOLTAGE_COLORS["poor"]
        return VOLTAGE_COLORS["critical"]

    @staticmethod
    def _fault_severity_color(fc_ka: float) -> str:
        if fc_ka < 5:
            return FAULT_SEVERITY_COLORS["low"]
        elif fc_ka < 15:
            return FAULT_SEVERITY_COLORS["medium"]
        elif fc_ka < 30:
            return FAULT_SEVERITY_COLORS["high"]
        elif fc_ka < 50:
            return FAULT_SEVERITY_COLORS["severe"]
        return FAULT_SEVERITY_COLORS["extreme"]

    @staticmethod
    def _fault_severity_label(fc_ka: float) -> str:
        if fc_ka < 5:
            return "Low"
        elif fc_ka < 15:
            return "Medium"
        elif fc_ka < 30:
            return "High"
        elif fc_ka < 50:
            return "Severe"
        return "Extreme"

    @staticmethod
    def _arc_flash_color(ie: float) -> str:
        if ie < 1.2:
            return ARC_FLASH_COLORS["safe"]
        elif ie < 4:
            return ARC_FLASH_COLORS["low"]
        elif ie < 8:
            return ARC_FLASH_COLORS["medium"]
        elif ie < 25:
            return ARC_FLASH_COLORS["high"]
        elif ie < 40:
            return ARC_FLASH_COLORS["severe"]
        return ARC_FLASH_COLORS["extreme"]

    @staticmethod
    def _asset_type_color(asset_type: str) -> str:
        colors = {
            "bus": "#0066cc",
            "substation": "#cc6600",
            "switch": "#990000",
            "load": "#cccc00",
            "generator": "#00cc00",
            "transformer": "#cc6600",
        }
        return colors.get(asset_type, "#666666")

    @staticmethod
    def _build_asset_popup(asset_type: str, props: Dict) -> str:
        lines = [f"<b>Type: {asset_type.capitalize()}</b>"]
        for k, v in props.items():
            if k == "asset_type":
                continue
            if isinstance(v, float):
                lines.append(f"{k}: {v:.4f}")
            else:
                lines.append(f"{k}: {v}")
        return "<br>".join(lines)

    @staticmethod
    def _assign_coordinates(asset_id: str, idx: int, total: int) -> Tuple[float, float]:
        """Assign coordinates in a ring pattern when coordinates are unknown."""
        import math

        radius = 0.02 * (1 + idx // 20)
        angle = (2 * math.pi * idx) / max(total, 1)
        # Place around center with slight offset per asset
        base_lat = 30.0 + 0.005 * (idx % 5)
        base_lon = 31.0 + 0.005 * ((idx // 5) % 5)
        lat = base_lat + radius * math.cos(angle)
        lon = base_lon + radius * math.sin(angle)
        return (lon, lat)

    @staticmethod
    def _add_title(m: Any, title: str) -> None:
        """Add an HTML title overlay to the map."""
        if not _HAS_FOLIUM:
            return
        title_html = f"""
        <div style="position: fixed;
                    top: 10px; left: 50px; z-index: 1000;
                    background: white; padding: 8px 16px;
                    border-radius: 4px; box-shadow: 0 0 8px rgba(0,0,0,0.3);
                    font-family: Arial; font-size: 16px; font-weight: bold;">
            {title}
        </div>
        """
        m.get_root().html.add_child(folium.Element(title_html))

    @staticmethod
    def _add_legend(m: Any, items: List[Tuple[str, str]], title: str = "Legend") -> None:
        """Add a color legend to the map."""
        if not _HAS_FOLIUM:
            return
        legend_html = f"""
        <div style="position: fixed;
                    bottom: 50px; right: 20px; z-index: 1000;
                    background: white; padding: 10px;
                    border-radius: 4px; box-shadow: 0 0 8px rgba(0,0,0,0.3);
                    font-family: Arial; font-size: 12px;
                    max-height: 300px; overflow-y: auto;">
            <b>{title}</b><br>
            {"".join(f'<i class="fa fa-circle" style="color:{c}"></i> {l}<br>' for c, l in items)}
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

    def _add_voltage_legend(self, m: Any) -> None:
        """Add the standard voltage color legend."""
        self._add_legend(
            m,
            items=[
                ("#00cc00", "≥ 1.02 pu (Excellent)"),
                ("#66cc00", "0.98 - 1.02 pu (Good)"),
                ("#cccc00", "0.95 - 0.98 pu (Fair)"),
                ("#cc6600", "0.90 - 0.95 pu (Poor)"),
                ("#cc0000", "< 0.90 pu (Critical)"),
            ],
            title="Voltage Legend",
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _save_or_return(self, m: Any, output_path: str | None = None) -> Any:
        """Save map to HTML or return the map object."""
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            m.save(output_path)
            logger.info("Map saved to %s", output_path)
            return output_path
        self._last_map = m
        return m

    def _fallback_geojson(self, viz_type: str, data: Dict) -> Dict[str, Any]:
        """Return GeoJSON when folium is unavailable."""
        return {
            "visualization_type": viz_type,
            "note": "folium not installed. Install with: pip install folium",
            "data": data,
            "geojson_template": {
                "type": "FeatureCollection",
                "features": [],
            },
        }

    def get_last_map(self) -> Any:
        """Get the last created map object."""
        return self._last_map
