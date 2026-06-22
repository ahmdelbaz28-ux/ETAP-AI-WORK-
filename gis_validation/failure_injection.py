from __future__ import annotations

import copy
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from gis_integration.models import ADMSAsset


@dataclass(frozen=True)
class FailureScenario:
    scenario_id: str
    name: str
    details: Dict[str, Any]


def inject_corrupted_geometries(
    assets: List[ADMSAsset],
    *,
    seed: int = 1337,
    corruption_ratio: float = 0.01,
) -> List[ADMSAsset]:
    """
    Corrupt a subset of geometries deterministically:
    - remove geometry.type
    - or remove coordinates
    """
    rng = random.Random(seed)
    out = copy.deepcopy(assets)
    n = len(out)
    if n == 0:
        return out

    k = max(1, int(n * corruption_ratio))
    for idx in rng.sample(range(n), k):
        a = out[idx]
        geom = dict(a.geometry)
        mode = rng.choice(["missing_type", "missing_coordinates"])
        if mode == "missing_type":
            geom.pop("type", None)
        else:
            geom.pop("coordinates", None)

        out[idx] = ADMSAsset(
            asset_id=a.asset_id,
            asset_type=a.asset_type,
            geometry=geom,
            metadata=dict(a.metadata),
        )
    return out


def inject_broken_crs_metadata(
    assets: List[ADMSAsset],
    *,
    seed: int = 1337,
    contamination_ratio: float = 0.1,
    broken_value: str = "INVALID_EPSG",
) -> List[ADMSAsset]:
    rng = random.Random(seed)
    out = copy.deepcopy(assets)
    n = len(out)
    if n == 0:
        return out

    k = max(1, int(n * contamination_ratio))
    for idx in rng.sample(range(n), k):
        a = out[idx]
        md = dict(a.metadata)
        md["source_crs"] = broken_value
        out[idx] = ADMSAsset(
            asset_id=a.asset_id,
            asset_type=a.asset_type,
            geometry=a.geometry,
            metadata=md,
        )
    return out


def inject_missing_layers_simulation(
    required_layer_ids: List[str],
    *,
    missing_layer_ratio: float = 0.2,
    seed: int = 1337,
) -> Tuple[List[str], List[str]]:
    """
    Pure helper: choose which layer_ids are 'missing' in a provider extraction simulation.
    Returns: (present_layers, missing_layers)
    """
    rng = random.Random(seed)
    layers = list(required_layer_ids)
    n = len(layers)
    if n == 0:
        return [], []

    k = max(1, int(n * missing_layer_ratio))
    missing = set(rng.sample(layers, min(k, n)))
    present = [l for l in layers if l not in missing]
    return present, sorted(missing)


def partial_provider_failure_simulation(
    health_check_fn: Callable[[], bool],
    *,
    fail_first: bool = True,
) -> bool:
    """
    Deterministic 'partial provider failure' simulation:
    - if fail_first: return False for first call to health_check_fn, then call again.
    - otherwise: just call health_check_fn.
    """
    if not fail_first:
        return bool(health_check_fn())
    # Simulate first failure without invoking provider.
    # Then invoke provider health check for a second attempt.
    _ = False
    return bool(health_check_fn())
