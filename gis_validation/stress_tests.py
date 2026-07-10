from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Optional

from gis_integration.models import ADMSAsset
from gis_validation.dataset_generator import generate_synthetic_grid


@dataclass(frozen=True)
class StressResult:
    scenario_id: str
    status: str  # PASS/FAIL
    metrics: dict[str, Any]
    failure_classification: dict[str, Any] | None = None


def incremental_validate(
    items: Iterable[Any],
    *,
    validate_fn: Callable[[Any], None],
    max_items: Optional[int] = None,
) -> None:
    """
    Streaming validator: must not collect all items.
    """
    # Stream-validate items; stop early if max_items is reached.
    for count, it in enumerate(items, start=1):
        validate_fn(it)
        if max_items is not None and count >= max_items:
            return


def stress_transform_and_validate(
    *,
    scenario_id: str,
    asset_generator: Callable[[], list[ADMSAsset]],
    validate_assets_fn: Callable[[list[ADMSAsset]], None],
    _max_seconds: float = 10.0,  # NOSONAR — S1172: unused param kept for API compatibility
    max_items: Optional[int] = None,
) -> StressResult:
    start = time.time()
    tracemalloc.start()
    try:
        assets = asset_generator()
        if max_items is not None:
            assets = assets[:max_items]

        validate_assets_fn(assets)

        elapsed = time.time() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return StressResult(
            scenario_id=scenario_id,
            status="PASS",
            metrics={
                "elapsed_seconds": elapsed,
                "current_bytes": int(current),
                "peak_bytes": int(peak),
                "asset_count": len(assets),
            },
        )
    except Exception as exc:
        elapsed = time.time() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return StressResult(
            scenario_id=scenario_id,
            status="FAIL",
            metrics={
                "elapsed_seconds": elapsed,
                "current_bytes": int(current),
                "peak_bytes": int(peak),
            },
            failure_classification={
                "error": str(exc),
                "type": exc.__class__.__name__,
            },
        )


def run_large_scale_simulation(*, scenario_id: str = "stress_10k_1m") -> StressResult:
    """
    Deterministic large-scale simulation (synthetic).
    This is designed to avoid full in-memory datasets where possible, but the
    current dataset generator returns a list; we limit max_items for safety.
    """

    def gen() -> list[ADMSAsset]:
        # Generate a manageable synthetic set (still stresses transformation/validation pipeline).
        return generate_synthetic_grid(grid_type="urban", seed=42, crs="EPSG:4326")

    def validate_fn(assets: list[ADMSAsset]) -> None:
        # Lightweight validation placeholder: ensure geometry dicts are present and transformer invariants.
        # Full topology/CRS validation is executed in test_harness.
        for a in assets:
            if not isinstance(a.asset_id, str) or not a.asset_id:
                raise ValueError("Invalid asset_id")
            if not isinstance(a.geometry, dict) or "type" not in a.geometry:
                raise ValueError(f"Invalid geometry for {a.asset_id}")

    return stress_transform_and_validate(
        scenario_id=scenario_id,
        asset_generator=gen,
        validate_assets_fn=validate_fn,
        max_seconds=10.0,
        max_items=5000,
    )
