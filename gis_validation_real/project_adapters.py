from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from gis_integration.base import GISProviderInterface
from gis_integration.exceptions import GISIntegrationError
from gis_integration.models import GISFeature


@dataclass(frozen=True)
class ExtractedLayer:
    layer_id: str
    features: List[GISFeature]


def extract_layers_as_features(provider: GISProviderInterface, *, layer_ids: Optional[List[str]] = None) -> List[ExtractedLayer]:
    """
    Adapter: extract real GIS layers into normalized GISFeature lists.

    Rules:
    - No synthetic fallback
    - Deterministic ordering (sorted layer_ids)
    - Provider failures propagate as GISIntegrationError (normalized)
    """
    try:
        available = provider.list_layers()
        if layer_ids is None:
            target = sorted(available)
        else:
            target = sorted(layer_ids)

        extracted: List[ExtractedLayer] = []
        for lid in target:
            feats = list(provider.extract_features(lid))
            extracted.append(ExtractedLayer(layer_id=lid, features=feats))
        return extracted
    except GISIntegrationError:
        raise
    except Exception as exc:
        raise GISIntegrationError(f"Failed to extract layers: {exc}") from exc
