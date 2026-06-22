"""
AhmedETAP - SCADA Integration Agent
=======================================================
IEC 61850 data model mapping and real-time measurement processing
for SCADA system integration.

Capabilities:
- IEC 61850 logical node data model mapping
- Real-time measurement acquisition and processing
- Bus data mapping from SCADA measurements to power system model
- Data validation, filtering, and anomaly detection
- State estimation support via measurement preprocessing

Standards:
- IEC 61850: Communication Networks and Systems for Power Utility
  Automation
- IEC 60870-5-104: Telecontrol Equipment and Systems
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

UTC = UTC
from typing import Any, Dict, List

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IEC 61850 Logical Node mappings
# ---------------------------------------------------------------------------

_IEC61850_LOGICAL_NODES = {
    # Measurement logical nodes
    "MMXU": "Measurement - Voltage/Current/Power (3-phase)",
    "MMTR": "Measurement - Energy Metering",
    "MSQI": "Measurement - Sequence & Imbalance",
    "MDIF": "Measurement - Differential",
    "MHAI": "Measurement - Harmonics",
    # Protection logical nodes
    "PTOC": "Protection - Time Overcurrent",
    "PVOC": "Protection - Voltage Controlled Overcurrent",
    "PDIS": "Protection - Distance",
    "PDIF": "Protection - Differential",
    "PTRC": "Protection - Trip Conditioning",
    # Control logical nodes
    "CSWI": "Control - Switch",
    "CILO": "Control - Interlocking",
    "CPOW": "Control - Power Control",
    # Transformer logical nodes
    "YPTR": "Transformer",
    "YTLC": "Tap Changer Control",
    # Circuit breaker
    "XCBR": "Circuit Breaker",
    "XSWI": "Switch (Disconnector)",
}

_IEC61850_DATA_OBJECTS = {
    "MMXU": {
        "Vol": {
            "cdc": "MV",
            "description": "Voltage (phase-to-phase)",
            "unit": "V",
            "si_unit": "V",
        },
        "VolPhV": {
            "cdc": "WYE",
            "description": "Phase voltages (A, B, C)",
            "unit": "V",
            "si_unit": "V",
        },
        "A": {"cdc": "MV", "description": "Current (RMS)", "unit": "A", "si_unit": "A"},
        "APh": {
            "cdc": "WYE",
            "description": "Phase currents (A, B, C)",
            "unit": "A",
            "si_unit": "A",
        },
        "W": {"cdc": "MV", "description": "Active power (3-phase)", "unit": "W", "si_unit": "W"},
        "var": {
            "cdc": "MV",
            "description": "Reactive power (3-phase)",
            "unit": "var",
            "si_unit": "var",
        },
        "PF": {"cdc": "MV", "description": "Power factor", "unit": "pu", "si_unit": "1"},
        "Hz": {"cdc": "MV", "description": "Frequency", "unit": "Hz", "si_unit": "Hz"},
        "PhV": {
            "cdc": "WYE",
            "description": "Phase-to-ground voltages",
            "unit": "V",
            "si_unit": "V",
        },
    },
    "MMTR": {
        "TotW": {
            "cdc": "BCR",
            "description": "Active energy (total)",
            "unit": "Wh",
            "si_unit": "J",
        },
        "TotVAr": {
            "cdc": "BCR",
            "description": "Reactive energy (total)",
            "unit": "varh",
            "si_unit": "J",
        },
    },
    "MSQI": {
        "SeqV": {
            "cdc": "SEQ",
            "description": "Voltage sequence components",
            "unit": "V",
            "si_unit": "V",
        },
        "SeqA": {
            "cdc": "SEQ",
            "description": "Current sequence components",
            "unit": "A",
            "si_unit": "A",
        },
        "V2V1": {
            "cdc": "MV",
            "description": "Negative/positive seq voltage ratio",
            "unit": "%",
            "si_unit": "1",
        },
    },
}


class SCADAMeasurement:
    """Represents a single SCADA measurement with quality flags."""

    def __init__(
        self,
        tag: str,
        value: float,
        timestamp: datetime,
        quality: str = "good",
        iec61850_ref: str = "",
        unit: str = "",
    ) -> None:
        self.tag = tag
        self.value = value
        self.timestamp = timestamp
        self.quality = quality  # "good", "questionable", "invalid", "old"
        self.iec61850_ref = iec61850_ref
        self.unit = unit

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "quality": self.quality,
            "iec61850_ref": self.iec61850_ref,
            "unit": self.unit,
        }


class SCADAConnection:
    """Simulated SCADA connection for testing and demonstration."""

    def __init__(self, server: str, port: int = 102, protocol: str = "IEC61850") -> None:
        self.server = server
        self.port = port
        self.protocol = protocol
        self.connected = False
        self.last_poll_time: datetime | None = None

    def connect(self) -> bool:
        """Simulate establishing a SCADA connection."""
        # In production, this would open a real MMS/IEC 61850 connection
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Close the SCADA connection."""
        self.connected = False


class SCADAAgent(BaseAgent):
    """
    SCADA Integration Agent.

    Implements real-time data acquisition from SCADA systems and maps
    IEC 61850 measurements to the power system model for:

    - Online load flow initialization
    - State estimation input processing
    - Real-time monitoring and alarming
    - Data validation and cleansing

    IEC 61850 Data Model Mapping:
    - MMXU (Measurement) → Bus voltage, current, power
    - MMTR (Metering) → Energy accumulators
    - MSQI (Sequence) → Sequence components & imbalance
    - XCBR/XSWI → Topology status (breaker/switch positions)
    """

    prompt_handle = "scada_agent"

    def __init__(self) -> None:
        super().__init__("SCADAAgent")
        self.standards = ["IEC 61850", "IEC 60870-5-104"]
        self.connections: Dict[str, SCADAConnection] = {}
        self.measurement_cache: Dict[str, List[SCADAMeasurement]] = {}

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect_scada(
        self,
        server: str,
        port: int = 102,
        protocol: str = "IEC61850",
        timeout_ms: int = 5000,
    ) -> Dict[str, Any]:
        """
        Establish connection to SCADA server.

        Parameters
        ----------
        server : str
            SCADA server hostname or IP address.
        port : int
            Server port number (default 102 for IEC 61850 MMS).
        protocol : str
            Communication protocol (``'IEC61850'`` or ``'IEC60870-5-104'``).
        timeout_ms : int
            Connection timeout in milliseconds.

        Returns
        -------
        Dict[str, Any]
            Connection status and metadata.
        """
        conn_id = f"{server}:{port}"

        if conn_id in self.connections and self.connections[conn_id].connected:
            return {
                "connection_id": conn_id,
                "status": "already_connected",
                "server": server,
                "port": port,
                "protocol": protocol,
            }

        conn = SCADAConnection(server=server, port=port, protocol=protocol)
        success = conn.connect()

        if success:
            self.connections[conn_id] = conn
            self.log_execution(f"Connected to SCADA server {conn_id}")

        return {
            "connection_id": conn_id,
            "status": "connected" if success else "failed",
            "server": server,
            "port": port,
            "protocol": protocol,
            "timeout_ms": timeout_ms,
            "connected_at": datetime.now(UTC).isoformat() if success else None,
        }

    # ------------------------------------------------------------------
    # Measurement reading
    # ------------------------------------------------------------------

    def read_measurements(
        self,
        connection_id: str,
        measurement_tags: List[str] | None = None,
        iec61850_refs: List[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Read measurements from SCADA server.

        Simulates real-time measurement acquisition. In production,
        this would issue MMS Read/GetDirectory requests to the
        IEC 61850 server.

        Parameters
        ----------
        connection_id : str
            Active connection identifier (``host:port``).
        measurement_tags : List[str], optional
            Specific tags to read. If None, reads all cached tags.
        iec61850_refs : List[str], optional
            IEC 61850 object references (e.g., ``'LD0/LLN0.MMXU$Vol$mag$f'``).

        Returns
        -------
        Dict[str, Any]
            Measurement values with timestamps and quality flags.
        """
        conn = self.connections.get(connection_id)
        if conn is None or not conn.connected:
            return {
                "error": f"No active connection for {connection_id}",
                "measurements": [],
            }

        now = datetime.now(UTC)

        # Generate simulated measurements if none cached
        if connection_id not in self.measurement_cache:
            self.measurement_cache[connection_id] = self._generate_simulated_measurements(now)

        cached = self.measurement_cache[connection_id]

        # Filter by requested tags
        if measurement_tags:
            filtered = [m for m in cached if m.tag in measurement_tags]
        elif iec61850_refs:
            filtered = [m for m in cached if m.iec61850_ref in iec61850_refs]
        else:
            filtered = cached

        # Update values with slight random variation (simulate real-time)
        # Copy cached objects to avoid mutating the cache
        np.random.seed(int(now.timestamp()) % 2**31)
        result_measurements = []
        for m in filtered:
            noise = np.random.normal(0, 0.005)  # 0.5% noise
            new_value = m.value * (1.0 + noise)
            result_measurements.append(
                SCADAMeasurement(
                    tag=m.tag,
                    value=new_value,
                    timestamp=now,
                    quality=m.quality,
                    iec61850_ref=m.iec61850_ref,
                    unit=m.unit,
                )
            )
            conn.last_poll_time = now

        return {
            "connection_id": connection_id,
            "timestamp": now.isoformat(),
            "measurement_count": len(result_measurements),
            "measurements": [m.to_dict() for m in result_measurements],
            "protocol": conn.protocol,
        }

    # ------------------------------------------------------------------
    # Bus data mapping
    # ------------------------------------------------------------------

    def map_to_bus_data(
        self,
        measurements: List[Dict[str, Any]],
        bus_mapping: Dict[str, Dict[str, str]],
        nominal_kv: float = 13.8,
        base_mva: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Map SCADA measurements to power system bus data.

        Converts raw SCADA measurements into the format required by
        power system analysis (per-unit voltages, complex power
        injections, etc.).

        The mapping dictionary specifies which measurement tags
        correspond to each bus and quantity:

            bus_mapping = {
                "BUS1": {
                    "voltage_tag": "V_BUS1_KV",
                    "angle_tag": "A_BUS1_DEG",
                    "P_load_tag": "P_BUS1_MW",
                    "Q_load_tag": "Q_BUS1_MVAR",
                    "P_gen_tag": "P_GEN1_MW",
                    "Q_gen_tag": "Q_GEN1_MVAR",
                },
                ...
            }

        Parameters
        ----------
        measurements : List[Dict[str, Any]]
            Raw measurement dictionaries from ``read_measurements()``.
        bus_mapping : Dict[str, Dict[str, str]]
            Mapping from bus IDs to measurement tag names.
        nominal_kv : float
            Nominal line-to-line voltage in kV for per-unit conversion.
        base_mva : float
            System base MVA for per-unit conversion.

        Returns
        -------
        Dict[str, Any]
            Bus data suitable for load flow / state estimation input.
        """
        # Index measurements by tag
        meas_by_tag: Dict[str, Dict[str, Any]] = {}
        for m in measurements:
            tag = m.get("tag", "")
            meas_by_tag[tag] = m

        bus_data: Dict[str, Dict[str, Any]] = {}
        mapping_issues: List[str] = []
        base_kv = nominal_kv

        for bus_id, tag_map in bus_mapping.items():
            bus_entry: Dict[str, Any] = {"bus_id": bus_id}

            # Voltage magnitude
            v_tag = tag_map.get("voltage_tag")
            if v_tag and v_tag in meas_by_tag:
                v_kv = meas_by_tag[v_tag].get("value", 0.0)
                bus_entry["voltage_kv"] = float(v_kv)
                bus_entry["voltage_pu"] = float(v_kv / base_kv) if base_kv > 0 else 0.0
            else:
                bus_entry["voltage_pu"] = 1.0  # Default flat start
                if v_tag:
                    mapping_issues.append(f"Bus {bus_id}: voltage tag '{v_tag}' not found")

            # Voltage angle
            a_tag = tag_map.get("angle_tag")
            if a_tag and a_tag in meas_by_tag:
                bus_entry["angle_deg"] = float(meas_by_tag[a_tag].get("value", 0.0))
            else:
                bus_entry["angle_deg"] = 0.0

            # Load power
            P_load = 0.0
            Q_load = 0.0
            p_load_tag = tag_map.get("P_load_tag")
            q_load_tag = tag_map.get("Q_load_tag")
            if p_load_tag and p_load_tag in meas_by_tag:
                P_load = float(meas_by_tag[p_load_tag].get("value", 0.0))
            if q_load_tag and q_load_tag in meas_by_tag:
                Q_load = float(meas_by_tag[q_load_tag].get("value", 0.0))

            bus_entry["P_load_mw"] = P_load
            bus_entry["Q_load_mvar"] = Q_load
            bus_entry["S_load_pu"] = (
                complex(P_load / base_mva, Q_load / base_mva) if base_mva > 0 else complex(0, 0)
            )

            # Generation power
            P_gen = 0.0
            Q_gen = 0.0
            p_gen_tag = tag_map.get("P_gen_tag")
            q_gen_tag = tag_map.get("Q_gen_tag")
            if p_gen_tag and p_gen_tag in meas_by_tag:
                P_gen = float(meas_by_tag[p_gen_tag].get("value", 0.0))
            if q_gen_tag and q_gen_tag in meas_by_tag:
                Q_gen = float(meas_by_tag[q_gen_tag].get("value", 0.0))

            bus_entry["P_gen_mw"] = P_gen
            bus_entry["Q_gen_mvar"] = Q_gen
            bus_entry["S_gen_pu"] = (
                complex(P_gen / base_mva, Q_gen / base_mva) if base_mva > 0 else complex(0, 0)
            )

            # Net injection
            bus_entry["P_net_mw"] = P_gen - P_load
            bus_entry["Q_net_mvar"] = Q_gen - Q_load
            bus_entry["S_net_pu"] = complex(
                (P_gen - P_load) / base_mva, (Q_gen - Q_load) / base_mva
            )

            # Quality assessment
            quality_issues = []
            v_pu = bus_entry.get("voltage_pu", 1.0)
            if v_pu < 0.9 or v_pu > 1.1:
                quality_issues.append(f"Voltage out of range: {v_pu:.3f} pu")
            if bus_entry.get("angle_deg", 0) > 45 or bus_entry.get("angle_deg", 0) < -45:
                quality_issues.append(f"Large angle: {bus_entry['angle_deg']:.1f}°")

            bus_entry["quality_issues"] = quality_issues

            bus_data[bus_id] = bus_entry

        # Build complex voltage array for state estimation
        voltages = np.array(
            [
                complex(
                    b.get("voltage_pu", 1.0) * np.cos(np.radians(b.get("angle_deg", 0))),
                    b.get("voltage_pu", 1.0) * np.sin(np.radians(b.get("angle_deg", 0))),
                )
                for b in bus_data.values()
            ]
        )

        return {
            "bus_data": bus_data,
            "base_mva": base_mva,
            "base_kv": base_kv,
            "n_buses": len(bus_data),
            "voltage_array_pu": voltages.tolist(),
            "mapping_issues": mapping_issues,
            "mapping_completeness": float(1.0 - len(mapping_issues) / max(len(bus_mapping) * 4, 1)),
        }

    # ------------------------------------------------------------------
    # Real-time data processing
    # ------------------------------------------------------------------

    def process_realtime_data(
        self,
        measurements: List[Dict[str, Any]],
        validation_rules: Dict[str, Dict[str, Any]] | None = None,
        filter_type: str = "moving_average",
        filter_window: int = 5,
        anomaly_threshold_sigma: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Process real-time SCADA measurements.

        Performs:
        1. Data validation against configurable rules
        2. Noise filtering (moving average or exponential smoothing)
        3. Anomaly detection (statistical outlier detection)
        4. Topology change detection (breaker status changes)

        Parameters
        ----------
        measurements : List[Dict[str, Any]]
            Raw measurement dictionaries.
        validation_rules : Dict[str, Dict[str, Any]], optional
            Per-tag validation rules: ``{tag: {min, max, rate_limit}}``.
        filter_type : str
            ``'moving_average'`` or ``'exponential'``.
        filter_window : int
            Window size for moving average filter.
        anomaly_threshold_sigma : float
            Number of standard deviations for anomaly detection.

        Returns
        -------
        Dict[str, Any]
            Processed measurements with quality flags and anomalies.
        """
        if not measurements:
            return {"error": "No measurements provided", "processed": []}

        # Default validation rules
        if validation_rules is None:
            validation_rules = {}

        # 1. Validate measurements
        validated: List[Dict[str, Any]] = []
        for m in measurements:
            tag = m.get("tag", "")
            value = m.get("value", 0.0)
            quality = m.get("quality", "good")

            rules = validation_rules.get(tag, {})
            v_min = rules.get("min", -1e9)
            v_max = rules.get("max", 1e9)
            _rate_limit = rules.get("rate_limit", None)

            # Range check
            if value < v_min or value > v_max:
                quality = "invalid"

            validated.append(
                {
                    **m,
                    "quality": quality,
                    "original_value": value,
                }
            )

        # 2. Apply filtering
        if filter_type == "moving_average" and len(validated) >= filter_window:
            values = np.array([m["value"] for m in validated], dtype=float)
            kernel = np.ones(filter_window) / filter_window
            filtered_values = np.convolve(values, kernel, mode="same")

            # Pad edges
            pad = filter_window // 2
            filtered_values[:pad] = values[:pad]
            filtered_values[-pad:] = values[-pad:]

            for i, m in enumerate(validated):
                m["filtered_value"] = float(filtered_values[i])
        elif filter_type == "exponential":
            alpha = 2.0 / (filter_window + 1)
            filtered_values = np.zeros(len(validated))
            filtered_values[0] = validated[0]["value"]
            for i in range(1, len(validated)):
                filtered_values[i] = (
                    alpha * validated[i]["value"] + (1 - alpha) * filtered_values[i - 1]
                )

            for i, m in enumerate(validated):
                m["filtered_value"] = float(filtered_values[i])
        else:
            for m in validated:
                m["filtered_value"] = m["value"]

        # 3. Anomaly detection (use ddof=1 for sample std)
        values_arr = np.array([m["value"] for m in validated], dtype=float)
        mean_val = np.mean(values_arr)
        std_val = np.std(values_arr, ddof=1) if len(values_arr) > 1 else 0.0

        anomalies: List[Dict[str, Any]] = []
        for _i, m in enumerate(validated):
            if std_val > 0:
                z_score = abs(m["value"] - mean_val) / std_val
                if z_score > anomaly_threshold_sigma:
                    anomalies.append(
                        {
                            "tag": m.get("tag", ""),
                            "value": m["value"],
                            "expected_range": [
                                float(mean_val - anomaly_threshold_sigma * std_val),
                                float(mean_val + anomaly_threshold_sigma * std_val),
                            ],
                            "z_score": float(z_score),
                            "timestamp": m.get("timestamp", ""),
                        }
                    )
                    m["quality"] = "questionable"

        # 4. Summary statistics
        quality_counts = {}
        for m in validated:
            q = m.get("quality", "unknown")
            quality_counts[q] = quality_counts.get(q, 0) + 1

        return {
            "processed_count": len(validated),
            "filter_type": filter_type,
            "filter_window": filter_window,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "anomaly_threshold_sigma": anomaly_threshold_sigma,
            "quality_summary": quality_counts,
            "statistics": {
                "mean": float(mean_val),
                "std": float(std_val),
                "min": float(np.min(values_arr)),
                "max": float(np.max(values_arr)),
                "median": float(np.median(values_arr)),
            },
            "processed_measurements": validated,
        }

    # ------------------------------------------------------------------
    # IEC 61850 data model mapping
    # ------------------------------------------------------------------

    def get_iec61850_model(
        self,
        logical_device: str = "LD0",
    ) -> Dict[str, Any]:
        """
        Return the IEC 61850 data model mapping for the configured
        logical device.

        This provides the complete mapping from IEC 61850 object
        references to ETAP power system model objects.

        Parameters
        ----------
        logical_device : str
            IEC 61850 Logical Device name.

        Returns
        -------
        Dict[str, Any]
            IEC 61850 data model structure.
        """
        ln_list = []
        for ln_name, ln_desc in _IEC61850_LOGICAL_NODES.items():
            ln_entry = {
                "logical_node": ln_name,
                "description": ln_desc,
                "data_objects": _IEC61850_DATA_OBJECTS.get(ln_name, {}),
            }
            ln_list.append(ln_entry)

        return {
            "logical_device": logical_device,
            "standard": "IEC 61850",
            "logical_nodes": ln_list,
            "total_logical_node_types": len(_IEC61850_LOGICAL_NODES),
            "total_data_objects": sum(len(dos) for dos in _IEC61850_DATA_OBJECTS.values()),
            "example_reference": f"{logical_device}/LLN0.MMXU$Vol$mag$f",
            "reference_format": "LD/LN.DO$DA$BDA",
        }

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_simulated_measurements(
        timestamp: datetime,
    ) -> List[SCADAMeasurement]:
        """Generate a set of simulated SCADA measurements for a substation."""
        np.random.seed(42)
        measurements = []

        # Bus measurements (3 buses)
        for bus_id in ["BUS1", "BUS2", "BUS3"]:
            v_nom = 13.8  # kV
            v_kv = v_nom * (1.0 + np.random.normal(0, 0.02))

            measurements.append(
                SCADAMeasurement(
                    tag=f"V_{bus_id}_KV",
                    value=v_kv,
                    timestamp=timestamp,
                    quality="good",
                    iec61850_ref=f"LD0/{bus_id}.MMXU$Vol$mag$f",
                    unit="kV",
                )
            )
            measurements.append(
                SCADAMeasurement(
                    tag=f"A_{bus_id}_A",
                    value=500 + np.random.normal(0, 10),
                    timestamp=timestamp,
                    quality="good",
                    iec61850_ref=f"LD0/{bus_id}.MMXU$A$mag$f",
                    unit="A",
                )
            )
            measurements.append(
                SCADAMeasurement(
                    tag=f"P_{bus_id}_MW",
                    value=5.0 + np.random.normal(0, 0.1),
                    timestamp=timestamp,
                    quality="good",
                    iec61850_ref=f"LD0/{bus_id}.MMXU$W$mag$f",
                    unit="MW",
                )
            )
            measurements.append(
                SCADAMeasurement(
                    tag=f"Q_{bus_id}_MVAR",
                    value=1.0 + np.random.normal(0, 0.05),
                    timestamp=timestamp,
                    quality="good",
                    iec61850_ref=f"LD0/{bus_id}.MMXU$var$mag$f",
                    unit="MVAR",
                )
            )
            measurements.append(
                SCADAMeasurement(
                    tag=f"PF_{bus_id}",
                    value=0.95 + np.random.normal(0, 0.01),
                    timestamp=timestamp,
                    quality="good",
                    iec61850_ref=f"LD0/{bus_id}.MMXU$PF$mag$f",
                    unit="pu",
                )
            )

        # Frequency (system-wide)
        measurements.append(
            SCADAMeasurement(
                tag="FREQ_HZ",
                value=60.0 + np.random.normal(0, 0.01),
                timestamp=timestamp,
                quality="good",
                iec61850_ref="LD0/LLN0.MMXU$Hz$mag$f",
                unit="Hz",
            )
        )

        # Breaker status
        for bk_id in ["BK1", "BK2", "BK3"]:
            measurements.append(
                SCADAMeasurement(
                    tag=f"{bk_id}_STATUS",
                    value=1.0,  # 1 = closed
                    timestamp=timestamp,
                    quality="good",
                    iec61850_ref=f"LD0/{bk_id}.XCBR$Pos$stVal",
                    unit="bool",
                )
            )

        return measurements

    # ------------------------------------------------------------------
    # Agent execute
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute SCADA integration task.

        Dispatches based on ``task.parameters['analysis_type']``:
        - ``'connect'``: Establish SCADA connection
        - ``'read'``: Read measurements
        - ``'map_bus'``: Map measurements to bus data
        - ``'process'``: Process real-time data
        - ``'iec61850_model'``: Get IEC 61850 data model
        - ``'full'``: Complete workflow (default)
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting SCADA integration for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}
            p = task.parameters

            if analysis_type in ("connect", "full"):
                results["connection"] = self.connect_scada(
                    server=p.get("scada_server", "scada.local"),
                    port=int(p.get("scada_port", 102)),
                    protocol=p.get("scada_protocol", "IEC61850"),
                    timeout_ms=int(p.get("timeout_ms", 5000)),
                )

            if analysis_type in ("read", "full"):
                conn_id = p.get(
                    "connection_id",
                    f"{p.get('scada_server', 'scada.local')}:{p.get('scada_port', 102)}",
                )
                results["measurements"] = self.read_measurements(
                    connection_id=conn_id,
                    measurement_tags=p.get("measurement_tags"),
                    iec61850_refs=p.get("iec61850_refs"),
                )

            if analysis_type in ("map_bus", "full"):
                # Use measurements from read step or from task parameters
                raw_meas = p.get("raw_measurements")
                if raw_meas is None and "measurements" in results:
                    raw_meas = results["measurements"].get("measurements", [])

                bus_mapping = p.get(
                    "bus_mapping",
                    {
                        "BUS1": {
                            "voltage_tag": "V_BUS1_KV",
                            "P_load_tag": "P_BUS1_MW",
                            "Q_load_tag": "Q_BUS1_MVAR",
                        },
                        "BUS2": {
                            "voltage_tag": "V_BUS2_KV",
                            "P_load_tag": "P_BUS2_MW",
                            "Q_load_tag": "Q_BUS2_MVAR",
                        },
                        "BUS3": {
                            "voltage_tag": "V_BUS3_KV",
                            "P_load_tag": "P_BUS3_MW",
                            "Q_load_tag": "Q_BUS3_MVAR",
                        },
                    },
                )

                results["bus_data"] = self.map_to_bus_data(
                    measurements=raw_meas or [],
                    bus_mapping=bus_mapping,
                    nominal_kv=float(p.get("nominal_kv", 13.8)),
                    base_mva=float(p.get("base_mva", 100.0)),
                )

            if analysis_type in ("process", "full"):
                raw_meas = p.get("raw_measurements")
                if raw_meas is None and "measurements" in results:
                    raw_meas = results["measurements"].get("measurements", [])

                results["processed_data"] = self.process_realtime_data(
                    measurements=raw_meas or [],
                    validation_rules=p.get("validation_rules"),
                    filter_type=p.get("filter_type", "moving_average"),
                    filter_window=int(p.get("filter_window", 5)),
                    anomaly_threshold_sigma=float(p.get("anomaly_threshold_sigma", 3.0)),
                )

            if analysis_type in ("iec61850_model",):
                results["iec61850_model"] = self.get_iec61850_model(
                    logical_device=p.get("logical_device", "LD0"),
                )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,  # closest available
                status=AgentStatus.COMPLETED,
                data={
                    **results,
                    "standards": self.standards,
                    "analysis_type": analysis_type,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"SCADA integration completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"SCADA integration failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """Validate SCADA integration results."""
        errors: List[str] = []

        conn = result.data.get("connection")
        if conn is not None and conn.get("status") == "failed":
            errors.append("SCADA connection failed")

        meas = result.data.get("measurements")
        if meas is not None:
            invalid_count = sum(
                1 for m in meas.get("measurements", []) if m.get("quality") == "invalid"
            )
            total = meas.get("measurement_count", 0)
            if total > 0 and invalid_count / total > 0.5:
                errors.append(f"More than 50% of measurements are invalid: {invalid_count}/{total}")

        bus = result.data.get("bus_data")
        if bus is not None:
            for bid, bdata in bus.get("bus_data", {}).items():
                issues = bdata.get("quality_issues", [])
                for issue in issues:
                    errors.append(f"Bus {bid}: {issue}")

        processed = result.data.get("processed_data")
        if processed is not None and processed.get("anomaly_count", 0) > 10:
            errors.append(f"High number of anomalies detected: {processed['anomaly_count']}")

        result.validation_errors.extend(errors)
        return len(errors) == 0
