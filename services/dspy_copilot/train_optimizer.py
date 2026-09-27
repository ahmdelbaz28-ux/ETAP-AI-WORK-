"""
services/dspy_copilot/train_optimizer.py — Offline Few-Shot Optimizer for DSPy Copilot.

OFFLINE ONLY. Never imported during standard runtime or execution flows.
Builds curated golden examples and compiles prompt demonstrations using
dspy.BootstrapFewShotWithRandomSearch (or BootstrapFewShot).
Saves compiled artifacts strictly to artifacts/dspy/v1/.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from services.dspy_copilot.metrics import metric_schema_adherence
from services.dspy_copilot.schemas import SldIngestOutput

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path("artifacts/dspy/v1")
ARTIFACT_FILE = ARTIFACT_DIR / "compiled_dspy_copilot.json"


def build_trainset() -> list[Any]:
    """Construct 7 curated golden training examples covering core edge cases:

    1. Standard 2-bus system (Slack bus 1 V=1.0, PQ bus 2 with valid line, fully grounded)
    2. Missing parameter case (Missing line reactance -> warnings: MISSING:lines[0].x1, non-executable)
    3. Missing bus voltage case (Bus 2 load given but voltage omitted -> MISSING:buses[1].voltage_magnitude)
    4. Provenance grounding case (3-bus ring with user_input and project_data source kinds)
    5. Under-voltage violation case (Bus 2 V=0.92 pu -> V-BAND)
    6. Overload line loading case (Branch loading 112% -> OVERLOAD)
    7. Unconverged solver case (Solver failed to converge -> CONVERGENCE_FAILURE)
    """
    try:
        import dspy
    except ImportError as err:
        raise RuntimeError("Compiling requires dspy-ai installed.") from err

    # 1. Valid ingest: 2-bus grounded system
    ex1_payload = {
        "buses": [
            {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.0, "voltage_angle": 0.0},
            {"bus_id": 2, "bus_type": "pq", "voltage_magnitude": 1.0, "load_power_real": 5.0, "load_power_imag": 2.0},
        ],
        "lines": [
            {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05},
        ],
        "loads": [],
        "transformers": [],
        "provenance": {
            "buses[0].voltage_magnitude": "user_input",
            "buses[1].load_power_real": "user_input",
            "lines[0].r1": "user_input",
            "lines[0].x1": "user_input",
        },
        "warnings": [],
        "is_executable": True,
    }

    # 2. Missing reactance: never invent x1, never mark standard, mark non-executable
    ex2_missing_notes = "Substation with 2 buses. Bus 1 slack 1.0 pu, Bus 2 load 10MW. Line connects Bus 1 to Bus 2 with R=0.02 pu. Line reactance not given."
    ex2_missing_payload = {
        "buses": [
            {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.0},
            {"bus_id": 2, "bus_type": "pq", "voltage_magnitude": 1.0, "load_power_real": 10.0},
        ],
        "lines": [
            {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.02},
        ],
        "loads": [],
        "transformers": [],
        "provenance": {
            "buses[0].voltage_magnitude": "user_input",
            "buses[1].load_power_real": "user_input",
            "lines[0].r1": "user_input",
        },
        "warnings": ["MISSING:lines[0].x1"],
        "is_executable": False,
    }

    # 3. Missing bus voltage: mark non-executable
    ex3_missing_v_notes = "Bus 1 Slack 13.8kV. Bus 2 with 3MW load at unstated voltage. Line R=0.03, X=0.08."
    ex3_missing_v_payload = {
        "buses": [
            {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.0},
            {"bus_id": 2, "bus_type": "pq", "load_power_real": 3.0},
        ],
        "lines": [
            {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.03, "x1": 0.08},
        ],
        "loads": [],
        "transformers": [],
        "provenance": {
            "buses[0].voltage_magnitude": "user_input",
            "buses[1].load_power_real": "user_input",
            "lines[0].r1": "user_input",
            "lines[0].x1": "user_input",
        },
        "warnings": ["MISSING:buses[1].voltage_magnitude"],
        "is_executable": False,
    }

    # 4. Multi-bus provenance grounding
    ex4_ring_notes = "3-bus ring: Bus 1 Slack 1.0 pu, Bus 2 PV 1.0 pu (Gen 10MW), Bus 3 PQ 15MW. Line 1-2 R=0.01 X=0.04, Line 2-3 R=0.015 X=0.05, Line 3-1 R=0.02 X=0.06."
    ex4_ring_payload = {
        "buses": [
            {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.0},
            {"bus_id": 2, "bus_type": "pv", "voltage_magnitude": 1.0, "generation_power_real": 10.0},
            {"bus_id": 3, "bus_type": "pq", "voltage_magnitude": 1.0, "load_power_real": 15.0},
        ],
        "lines": [
            {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.04},
            {"line_id": 2, "from_bus_id": 2, "to_bus_id": 3, "r1": 0.015, "x1": 0.05},
            {"line_id": 3, "from_bus_id": 3, "to_bus_id": 1, "r1": 0.02, "x1": 0.06},
        ],
        "loads": [],
        "transformers": [],
        "provenance": {
            "buses[0].voltage_magnitude": "user_input",
            "buses[1].voltage_magnitude": "user_input",
            "buses[1].generation_power_real": "user_input",
            "buses[2].load_power_real": "user_input",
            "lines[0].r1": "project_data",
            "lines[0].x1": "project_data",
            "lines[1].r1": "project_data",
            "lines[1].x1": "project_data",
            "lines[2].r1": "project_data",
            "lines[2].x1": "project_data",
        },
        "warnings": [],
        "is_executable": True,
    }

    # 5. Diagnostic: Under-voltage and overload
    ex5_diag_results = {
        "success": True,
        "converged": True,
        "buses": {
            "1": {"voltage_magnitude_pu": 1.0, "voltage_angle_deg": 0.0},
            "2": {"voltage_magnitude_pu": 0.92, "voltage_angle_deg": -2.4},
        },
        "lines": [
            {"line_id": 1, "loading_pct": 112.0},
        ],
    }
    ex5_diag_report = {
        "summary": "Load flow converged. Bus 2 exhibits low voltage (0.92 pu) and Line 1 is overloaded at 112%.",
        "findings": [
            {"severity": "violation", "code": "V-BAND", "message": "Bus 2 voltage 0.92 pu is below 0.95 pu", "bus_id": 2, "standard_ref": "ANSI C84.1"},
            {"severity": "violation", "code": "OVERLOAD", "message": "Line 1 loading 112% exceeds thermal rating", "bus_id": None, "standard_ref": "IEEE 3002.7"},
        ],
        "recommendations": [
            "Adjust transformer tap or dispatch shunt capacitors at Bus 2 to boost voltage.",
            "Re-dispatch generation or reinforce Line 1 conductors to relieve 112% thermal overload.",
        ],
        "citations": ["ANSI C84.1", "IEEE 3002.7-2018 Section 7.4"],
    }

    # 6. Diagnostic: Over-voltage
    ex6_diag_results = {
        "success": True,
        "converged": True,
        "buses": {
            "1": {"voltage_magnitude_pu": 1.0, "voltage_angle_deg": 0.0},
            "2": {"voltage_magnitude_pu": 1.08, "voltage_angle_deg": 0.5},
        },
        "lines": [
            {"line_id": 1, "loading_pct": 45.0},
        ],
    }
    ex6_diag_report = {
        "summary": "Load flow converged. Bus 2 exhibits high voltage (1.08 pu exceeding 1.05 pu upper limit).",
        "findings": [
            {"severity": "violation", "code": "V-BAND-HIGH", "message": "Bus 2 voltage 1.08 pu exceeds 1.05 pu upper limit", "bus_id": 2, "standard_ref": "ANSI C84.1"},
        ],
        "recommendations": [
            "Lower generator voltage setpoint or switch off shunt capacitors to reduce over-voltage.",
        ],
        "citations": ["ANSI C84.1"],
    }

    # 7. Diagnostic: Solver unconverged
    ex7_diag_results = {
        "success": False,
        "converged": False,
        "buses": {},
        "lines": [],
        "warnings": ["Power flow solver failed to converge after 100 iterations"],
    }
    ex7_diag_report = {
        "summary": "Load flow solver failed to converge. System may be operating near voltage collapse.",
        "findings": [
            {"severity": "violation", "code": "CONVERGENCE_FAILURE", "message": "Power flow solver did not converge; results are invalid", "bus_id": None, "standard_ref": "IEEE 3002.7"},
        ],
        "recommendations": [
            "Check for severe reactive power deficit or disconnected network islands.",
        ],
        "citations": ["IEEE 3002.7-2018"],
    }

    trainset = [
        dspy.Example(
            sld_notes="Bus 1 is Slack at 1.0 pu. Bus 2 has 5 MW and 2 MVAR load. Line 1 connects 1 to 2 with R=0.01 and X=0.05 pu.",
            payload_json=json.dumps(ex1_payload),
        ).with_inputs("sld_notes"),
        dspy.Example(
            sld_notes=ex2_missing_notes,
            payload_json=json.dumps(ex2_missing_payload),
        ).with_inputs("sld_notes"),
        dspy.Example(
            sld_notes=ex3_missing_v_notes,
            payload_json=json.dumps(ex3_missing_v_payload),
        ).with_inputs("sld_notes"),
        dspy.Example(
            sld_notes=ex4_ring_notes,
            payload_json=json.dumps(ex4_ring_payload),
        ).with_inputs("sld_notes"),
        dspy.Example(
            results_json=json.dumps(ex5_diag_results),
            report_json=json.dumps(ex5_diag_report),
        ).with_inputs("results_json"),
        dspy.Example(
            results_json=json.dumps(ex6_diag_results),
            report_json=json.dumps(ex6_diag_report),
        ).with_inputs("results_json"),
        dspy.Example(
            results_json=json.dumps(ex7_diag_results),
            report_json=json.dumps(ex7_diag_report),
        ).with_inputs("results_json"),
    ]

    return trainset


def compile_copilot(save_to: Path = ARTIFACT_FILE) -> Any:
    """Compile few-shot copilot program using BootstrapFewShotWithRandomSearch (or BootstrapFewShot).

    NOTE: MIPROv2 optimizer is available for future production iteration.
    Iteration 1 uses BootstrapFewShotWithRandomSearch / BootstrapFewShot
    with schema adherence validation.
    """
    try:
        import dspy
    except ImportError as err:
        raise RuntimeError("Compiling requires dspy-ai installed.") from err

    save_to.parent.mkdir(parents=True, exist_ok=True)
    trainset = build_trainset()
    logger.info("Built %d trainset examples for copilot compilation", len(trainset))

    # Compile ingest program
    from services.dspy_copilot.modules import DspySldIngestModule

    module = DspySldIngestModule()

    def metric(gold: Any, pred: Any, trace: Any = None) -> bool:
        pred_val = getattr(pred, "payload_json", "")
        return metric_schema_adherence(pred_val, SldIngestOutput)

    # Prefer BootstrapFewShotWithRandomSearch, fall back to BootstrapFewShot
    teleprompt_mod = getattr(dspy, "teleprompt", None)
    optimizer_cls = getattr(teleprompt_mod, "BootstrapFewShotWithRandomSearch", None) or getattr(
        teleprompt_mod, "BootstrapFewShot", None
    )
    if optimizer_cls is None:
        raise RuntimeError("No supported DSPy few-shot optimizer found in dspy.teleprompt")

    optimizer = optimizer_cls(
        metric=metric,
        max_bootstrapped_demos=3,
        max_labeled_demos=3,
    )
    compiled = optimizer.compile(module, trainset=[e for e in trainset if hasattr(e, "sld_notes")])
    if hasattr(compiled, "save"):
        compiled.save(str(save_to))
    logger.info("Successfully compiled and saved copilot artifact to %s", save_to)
    return compiled


if __name__ == "__main__":
    compile_copilot()

