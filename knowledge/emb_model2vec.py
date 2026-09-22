"""
knowledge/emb_model2vec.py — CPU-optimized local embedding engine via model2vec.

Implements fast static word-level embeddings on CPU without GPU overhead
for standards and technical document retrieval per Phase B requirements.
"""

from __future__ import annotations

import logging
import os
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL2VEC_MODEL = "minishlab/potion-base-8M"


class Model2VecEmbedder:
    """CPU-optimized static embedding model wrapper using model2vec."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("MODEL2VEC_MODEL_NAME", DEFAULT_MODEL2VEC_MODEL)
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load StaticModel from pretrained weights with fail-closed semantics."""
        try:
            from model2vec import StaticModel

            logger.info("Loading model2vec model: %s", self.model_name)
            self.model = StaticModel.from_pretrained(self.model_name)
            logger.info("Successfully loaded model2vec model: %s", self.model_name)
        except Exception as exc:
            logger.error("Failed to load model2vec model %s: %s", self.model_name, exc)
            raise RuntimeError(
                f"Failed to load model2vec model '{self.model_name}' under rag_model2vec feature flag: {exc}"
            ) from exc

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode a list of text strings into numpy embedding array.

        Parameters
        ----------
        texts : list[str]
            List of input texts to embed.

        Returns
        -------
        np.ndarray
            2D numpy array of shape (len(texts), embedding_dim).
        """
        if self.model is None:
            raise RuntimeError("model2vec model is not initialized")
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        raw_embeddings = self.model.encode(texts)
        return np.asarray(raw_embeddings, dtype=np.float32)
