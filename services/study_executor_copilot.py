"""
services/study_executor_copilot.py — Explicit copilot execution wrapper.

Delegates to services.dspy_copilot.runtime.execute_with_copilot.
Provides pre-ingest and post-diagnostic hooks without monkeypatching StudyExecutor.
"""

from __future__ import annotations

from services.dspy_copilot.runtime import execute_with_copilot

__all__ = ["execute_with_copilot"]
