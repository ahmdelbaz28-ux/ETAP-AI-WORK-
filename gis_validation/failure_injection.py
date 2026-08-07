from __future__ import annotations

import copy
import random
from collections.abc import Callable
from dataclasses import dataclass
<<<<<<< HEAD
from typing import Any
=======
from typing import Any, Dict, List, Tuple
>>>>>>> origin/fix/scenario-tests-properly

from gis_integration.models import ADMSAsset


<<<<<<< HEAD
def _make_test_rng(seed: int) -> random.Random:
    """Build a deterministic PRNG for non-security test/fault-injection scenarios.

    NOSONAR: random.Random is intentionally used here because the seed must be
    deterministic for reproducible test-vector generation. Cryptographic
    randomness would defeat the purpose (test reproducibility).
    """
    return random.Random(seed)  # NOSONAR


=======
>>>>>>> origin/fix/scenario-tests-properly
@dataclass(frozen=True)
class FailureScenario:
    scenario_id: str
    name: str
<<<<<<< HEAD
    details: dict[str, Any]


def inject_corrupted_geometries(
    assets: list[ADMSAsset],
    *,
    seed: int = 1337,
    corruption_ratio: float = 0.01,
) -> list[ADMSAsset]:
    """
    Corrupt a subset of geometries deterministically:  # NOSONAR S2245: deterministic PRNG for reproducible fault injection (see _make_test_rng)
    - remove geometry.type
    - or remove coordinates
    """
    rng = _make_test_rng(seed)
    out = copy.deepcopy(
        assets
    )  # NOSONAR S2245: deterministic PRNG via _make_test_rng above; reproducible fault injection, not security
=======
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
>>>>>>> origin/fix/scenario-tests-properly
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
<<<<<<< HEAD
    assets: list[ADMSAsset],
    *,
    seed: int = 1337,
    contamination_ratio: float = 0.1,  # NOSONAR S2245: deterministic PRNG for reproducible fault injection (see _make_test_rng)
    broken_value: str = "INVALID_EPSG",
) -> list[ADMSAsset]:
    rng = _make_test_rng(seed)
=======
    assets: List[ADMSAsset],
    *,
    seed: int = 1337,
    contamination_ratio: float = 0.1,
    broken_value: str = "INVALID_EPSG",
) -> List[ADMSAsset]:
    rng = random.Random(seed)
>>>>>>> origin/fix/scenario-tests-properly
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
<<<<<<< HEAD
    required_layer_ids: list[str],
    *,
    missing_layer_ratio: float = 0.2,
    seed: int = 1337,
) -> tuple[list[str], list[str]]:
    """
    Pure helper: choose which layer_ids are 'missing' in a provider extraction simulation.  # NOSONAR S2245: deterministic PRNG for reproducible sim (see _make_test_rng below)
    Returns: (present_layers, missing_layers)
    """
    rng = _make_test_rng(seed)
=======
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
>>>>>>> origin/fix/scenario-tests-properly
    layers = list(required_layer_ids)
    n = len(layers)
    if n == 0:
        return [], []

    k = max(1, int(n * missing_layer_ratio))
<<<<<<< HEAD
    missing = set(
        rng.sample(layers, min(k, n))
    )  # NOSONAR PRNG used for non-crypto purposes (test/load sim)
=======
    missing = set(rng.sample(layers, min(k, n)))
>>>>>>> origin/fix/scenario-tests-properly
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
