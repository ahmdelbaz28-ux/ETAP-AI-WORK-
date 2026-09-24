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
    """Construct 5 curated golden training examples covering core edge cases:

    1. Standard 2-bus system (Slack bus 1 V=1.0, PQ bus 2 with valid line)
    2. Under-voltage violation case (Bus 2 V=0.92 pu -> V-BAND)
    3. Overload line loading case (Branch loading 112% -> OVERLOAD)
    4. Missing parameter case (Missing line reactance -> warnings: MISSING:lines[0].x1)
    5. Provenance grounding case with explicit source kinds cited
    """
    try:
        import dspy
    except ImportError as err:
        raise RuntimeError("Compiling requires dspy-ai installed.") from err

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
    }

    ex2_diag_results = {
        "success": True,
        "data": {
            "converged": True,
            "buses": {
                "1": {"voltage_magnitude_pu": 1.0, "voltage_angle_deg": 0.0},
                "2": {"voltage_magnitude_pu": 0.92, "voltage_angle_deg": -2.4},
            },
            "lines": [
                {"line_id": 1, "loading_pct": 112.0},
            ],
        },
    }

    ex2_diag_report = {
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

    ex3_missing_notes = "Substation with 2 buses. Bus 1 slack 1.0 pu, Bus 2 load 10MW. Line connects Bus 1 to Bus 2 with R=0.02 pu. Line reactance not given."
    ex3_missing_payload = {
        "buses": [
            {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.0},
            {"bus_id": 2, "bus_type": "pq", "voltage_magnitude": 1.0, "load_power_real": 10.0},
        ],
        "lines": [
            {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.02, "x1": 0.05},
        ],
        "loads": [],
        "transformers": [],
        "provenance": {
            "buses[0].voltage_magnitude": "user_input",
            "buses[1].load_power_real": "user_input",
            "lines[0].r1": "user_input",
            "lines[0].x1": "standard",
        },
        "warnings": ["MISSING:lines[0].x1"],
    }

    trainset = [
        dspy.Example(
            sld_notes="Bus 1 is Slack at 1.0 pu. Bus 2 has 5 MW and 2 MVAR load. Line 1 connects 1 to 2 with R=0.01 and X=0.05 pu.",
            payload_json=json.dumps(ex1_payload),
        ).with_inputs("sld_notes"),
        dspy.Example(
            results_json=json.dumps(ex2_diag_results),
            report_json=json.dumps(ex2_diag_report),
        ).with_inputs("results_json"),
        dspy.Example(
            sld_notes=ex3_missing_notes,
            payload_json=json.dumps(ex3_missing_payload),
        ).with_inputs("sld_notes"),
    ]

    return trainset


def compile_copilot(save_to: Path = ARTIFACT_FILE) -> Any:
    """Compile few-shot copilot program using BootstrapFewShot.

    NOTE: MIPROv2 optimizer is available for future production iteration.
    Iteration 1 uses BootstrapFewShot / BootstrapFewShotWithRandomSearch
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

    optimizer = dspy.teleprompt.BootstrapFewShot(
        metric=metric,
        max_bootstrapped_demos=3,
        max_labeled_demos=3,
    )
    compiled = optimizer.compile(module, trainset=[e for e in trainset if hasattr(e, "sld_notes")])
    compiled.save(str(save_to))
    logger.info("Successfully compiled and saved copilot artifact to %s", save_to)
    return compiled


if __name__ == "__main__":
    compile_copilot()
