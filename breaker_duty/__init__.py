"""Breaker duty evaluation package per IEC 62271-100 and IEC 60947-2."""

from __future__ import annotations

from breaker_duty.catalog import BreakerCatalogItem, load_breaker_catalog
from breaker_duty.evaluator import BreakerDutyEvaluator, BreakerDutyResult, DutyLimitCheck

__all__ = [
    "BreakerCatalogItem",
    "load_breaker_catalog",
    "BreakerDutyEvaluator",
    "BreakerDutyResult",
    "DutyLimitCheck",
]
