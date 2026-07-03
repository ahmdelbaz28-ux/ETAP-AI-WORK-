from __future__ import annotations

import random
from typing import Any

from gis_integration.models import ADMSAsset, ADMSAssetType


def _point(lon: float, lat: float) -> dict[str, Any]:
    return {"type": "Point", "coordinates": [lon, lat]}


def _linestring(coords: list[list[float]]) -> dict[str, Any]:
    return {"type": "LineString", "coordinates": coords}


def _deterministic_rng(seed: int) -> random.Random:
    return random.Random(seed)


def generate_synthetic_grid(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    *,
    grid_type: str,
    seed: int = 1337,
    crs: str = "EPSG:4326",
) -> list[ADMSAsset]:
    """
    Generate a deterministic synthetic ADMS asset list.

    grid_type:
      - "urban"
      - "rural"
      - "hybrid"
    """
    rng = _deterministic_rng(seed)

    assets: list[ADMSAsset] = []

    # Deterministic layout parameters
    if grid_type == "urban":
        n_substations = 8
        n_feeders = 10
        n_lines_per_feeder = 2
    elif grid_type == "rural":
        n_substations = 4
        n_feeders = 5
        n_lines_per_feeder = 4
    elif grid_type == "hybrid":
        n_substations = 6
        n_feeders = 8
        n_lines_per_feeder = 3
    else:
        raise ValueError(f"Unknown grid_type: {grid_type}")

    # Create substations as points on a grid.
    substations: list[tuple[float, float]] = []
    for i in range(n_substations):
        lon = -122.0 + (i % 4) * 0.01
        lat = 37.0 + (i // 4) * 0.01
        substations.append((lon, lat))
        sid = f"SUB__{grid_type}__{seed}__{i}"
        assets.append(
            ADMSAsset(
                asset_id=sid,
                asset_type=ADMSAssetType.SUBSTATION,
                geometry=_point(lon, lat),
                metadata={"source_crs": crs, "source_layer": "substations"},
            ),
        )

    # Create feeders/lines connecting substations deterministically with exact endpoint matches.
    #
    # Topology validator builds edges only when LineString endpoints match exact substations'
    # Point coordinates. Therefore, every LineString must start/end at existing substation points.
    # We'll create a chain of substation-to-substation LineStrings.
    for feeder_idx in range(n_feeders):
        # deterministic endpoints
        a = rng.randrange(0, n_substations)
        b = rng.randrange(0, n_substations)
        if b == a:
            b = (b + 1) % n_substations

        # Build a deterministic chain: a -> m1 -> m2 -> ... -> b
        chain_len = max(2, n_lines_per_feeder + 1)  # number of substation nodes in chain
        # choose intermediate substations (excluding ends where possible)
        chain: list[int] = [a]
        for _ in range(chain_len - 2):
            mid = rng.randrange(0, n_substations)
            if mid == chain[-1]:
                mid = (mid + 1) % n_substations
            chain.append(mid)
        chain.append(b)

        for seg in range(n_lines_per_feeder):
            u = chain[seg]
            v = chain[seg + 1]

            lon_u, lat_u = substations[u]
            lon_v, lat_v = substations[v]

            # Single segment between two substations with exact endpoints.
            coords = [
                [lon_u, lat_u],
                [lon_v, lat_v],
            ]

            lid = f"LINE__{grid_type}__{seed}__{feeder_idx}__{seg}"
            # alternate feeder/line types
            a_type = ADMSAssetType.FEEDER if seg == 0 else ADMSAssetType.LINE
            assets.append(
                ADMSAsset(
                    asset_id=lid,
                    asset_type=a_type,
                    geometry=_linestring(coords),
                    metadata={
                        "source_crs": crs,
                        "source_layer": "feeders",
                        "line_kind": "feeder" if a_type == ADMSAssetType.FEEDER else "line",
                        # Explicit hint used by transformer; harmless in validation.
                        "asset_role": "switch" if a_type == ADMSAssetType.SWITCH else None,
                    },
                ),
            )

    return assets


def generate_mixed_crs_assets(
    *,
    seed: int = 1337,
    crs_a: str = "EPSG:4326",
    crs_b: str = "EPSG:3857",
) -> list[ADMSAsset]:
    """
    Generate assets with mixed CRS contamination to exercise CRS validator.
    """
    assets = generate_synthetic_grid(grid_type="hybrid", seed=seed, crs=crs_a)
    # contaminate half of lines
    for i, a in enumerate(list(assets)):
        if a.asset_type in (ADMSAssetType.LINE, ADMSAssetType.FEEDER) and i % 2 == 0:
            assets[i] = ADMSAsset(
                asset_id=a.asset_id,
                asset_type=a.asset_type,
                geometry=a.geometry,
                metadata={**a.metadata, "source_crs": crs_b},
            )
    return assets
