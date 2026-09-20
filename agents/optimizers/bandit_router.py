"""
agents/optimizers/bandit_router.py — Adaptive Learning Contextual Bandit Goal Router.

Replaces static heuristic routing with an online learning Contextual Bandit (LinUCB)
model that continuously learns optimal StudyType dispatching from study execution
rewards and telemetry, while maintaining 100% fail-safe fallback to canonical KEYWORD_RULES.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from agents.models import StudyType
from agents.router import DEFAULT_STUDIES, KEYWORD_RULES, GoalRouter, RouterDecision

logger = logging.getLogger(__name__)


class ContextualBanditRouter:
    """LinUCB Contextual Bandit router for engineering study dispatching.

    Maintains linear regression models per StudyType arm:
        E[reward | context x, arm a] = theta_a^T * x
    Selects arm maximizing upper confidence bound:
        a* = argmax (theta_a^T * x + alpha * sqrt(x^T * A_a^-1 * x))
    """

    def __init__(
        self,
        alpha: float = 0.5,
        feature_dim: int = 32,
        fallback_router: Optional[GoalRouter] = None,
        confidence_threshold: float = 0.65,
    ) -> None:
        self.alpha = alpha
        self.d = feature_dim
        self.confidence_threshold = confidence_threshold
        self.fallback_router = fallback_router or GoalRouter()

        self.arms: List[StudyType] = list(StudyType)
        self.arm_to_idx = {arm: i for i, arm in enumerate(self.arms)}

        # LinUCB state per arm
        # A_a: (d x d) covariance matrix initialized to Identity
        # b_a: (d x 1) reward accumulator
        self.A: Dict[StudyType, np.ndarray] = {
            arm: np.eye(self.d, dtype=np.float64) for arm in self.arms
        }
        self.b: Dict[StudyType, np.ndarray] = {
            arm: np.zeros((self.d, 1), dtype=np.float64) for arm in self.arms
        }
        self.arm_pulls: Dict[StudyType, int] = {arm: 0 for arm in self.arms}

        # Seed with canonical keywords for cold-start competence
        self._bootstrap_prior_knowledge()

    def _bootstrap_prior_knowledge(self) -> None:
        """Seed bandit models with canonical domain keyword patterns."""
        for keywords, study_type in KEYWORD_RULES:
            synth_text = " ".join(keywords)
            feat = self._extract_features(synth_text)
            self.update_reward(study_type, feat, reward=1.0)

    def _extract_features(self, text: str) -> np.ndarray:
        """Extract a deterministic normalized context feature vector from query text."""
        x = np.zeros(self.d, dtype=np.float64)
        if not text:
            x[0] = 1.0
            return x.reshape(-1, 1)

        norm_text = text.lower().strip()
        words = norm_text.split()

        # Feature 0: text length
        x[0] = min(1.0, len(words) / 20.0)

        # Feature 1-13: category keyword matching
        for i, (kws, st) in enumerate(KEYWORD_RULES[:13]):
            idx = 1 + i
            if idx < self.d:
                match_count = sum(1 for kw in kws if kw in norm_text)
                if match_count > 0:
                    x[idx] = min(1.0, match_count * 0.5)

        # Remaining dimensions: hashed character n-grams
        for i in range(len(norm_text) - 2):
            trigram = norm_text[i : i + 3]
            h = int(hashlib.md5(trigram.encode("utf-8")).hexdigest(), 16)
            slot = 14 + (h % (self.d - 14))
            x[slot] += 0.2

        # L2 normalize
        norm = np.linalg.norm(x)
        if norm > 1e-6:
            x = x / norm

        return x.reshape(-1, 1)

    def route(self, goal: Any) -> RouterDecision:
        """Analyze user goal and route to appropriate StudyType via LinUCB with fallback."""
        if not goal or (isinstance(goal, str) and not goal.strip()):
            return self.fallback_router.route(goal)

        if isinstance(goal, (list, tuple, dict)):
            return self.fallback_router.route(goal)

        goal_text = str(goal)
        x = self._extract_features(goal_text)

        best_arm: Optional[StudyType] = None
        max_p = -float("inf")
        scores: Dict[StudyType, float] = {}

        for arm in self.arms:
            A_inv = np.linalg.inv(self.A[arm])
            theta_a = A_inv.dot(self.b[arm])

            expected_reward = float(theta_a.T.dot(x)[0, 0])
            variance = float(np.sqrt(x.T.dot(A_inv).dot(x))[0, 0])
            ucb_score = expected_reward + self.alpha * variance

            scores[arm] = ucb_score
            if ucb_score > max_p:
                max_p = ucb_score
                best_arm = arm

        # Normalize confidence to [0.0, 1.0]
        confidence = 1.0 / (1.0 + math.exp(-max(0.0, max_p)))

        # Fallback check
        if confidence < self.confidence_threshold:
            fallback_res = self.fallback_router.route(goal_text)
            logger.debug(
                "Bandit confidence %.2f < threshold %.2f; delegating to fallback router: %s",
                confidence,
                self.confidence_threshold,
                fallback_res.study_types,
            )
            return fallback_res

        # If best arm is confidently found
        return RouterDecision(
            study_types=[best_arm] if best_arm else list(DEFAULT_STUDIES),
            confidence=round(confidence, 4),
            reason=f"Contextual Bandit (LinUCB) intent resolution (score={max_p:.3f})",
        )

    def update_reward(
        self,
        study_type: StudyType,
        context: Any,
        reward: float,
    ) -> None:
        """Update LinUCB covariance and reward vector from observed feedback."""
        if study_type not in self.A:
            return

        if isinstance(context, str):
            x = self._extract_features(context)
        elif isinstance(context, np.ndarray):
            x = context.reshape(-1, 1)
        else:
            return

        r = float(np.clip(reward, 0.0, 1.0))
        self.A[study_type] += x.dot(x.T)
        self.b[study_type] += r * x
        self.arm_pulls[study_type] += 1

        logger.debug(
            "Bandit updated for %s with reward=%.2f (total pulls: %d)",
            study_type.value,
            r,
            self.arm_pulls[study_type],
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for telemetry or persistence."""
        return {
            "alpha": self.alpha,
            "feature_dim": self.d,
            "arm_pulls": {arm.value: cnt for arm, cnt in self.arm_pulls.items()},
        }
