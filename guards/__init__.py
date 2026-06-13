"""
ETAP AI Platform — Guard Skills Module
========================================
Surgical integration of guard-skills concepts (github.com/amElnagdy/guard-skills)
into the ETAP AI Engineering Platform as runtime code-quality validators.

This module adapts the instructional-prompt guard system into executable
Python validators that can be invoked by AI agents, the secure executor,
and the Engineering Service API.

Guards implemented:
  - CodeGuard:  Clean-code + SOLID + DRY/KISS/YAGNI + 14 AI-specific failure modes
  - TestGuard:  9 universal testing rules (with pytest-specific patterns)
  - DocsGuard:  10 documentation-accuracy rules (claim verification)

Architecture:
  Each guard follows the progressive-disclosure model from the original
  guard-skills project: a lightweight core with on-demand depth.  The
  severity framework (MUST_FIX / SHOULD_FIX / WORTH_NOTING) is preserved
  so that guard results integrate cleanly with the existing RASP and
  security-middleware severity tiers.

Integration points:
  - security/secure_executor.py  →  AI failure-mode pre-scan
  - agents/orchestrator.py       →  CodeGuardAgent
  - engineering_service.py       →  /api/v1/guards/* endpoints
  - src/mastra/agents/           →  code-guard-agent.ts
"""

from guards.base import (
    GuardSeverity,
    GuardViolation,
    GuardResult,
    BaseGuard,
    GuardMode,
)
from guards.ai_failure_modes import AIFailureModeDetector, AI_FAILURE_MODES
from guards.code_guard import CodeGuard
from guards.test_guard import TestGuard
from guards.docs_guard import DocsGuard

__all__ = [
    "GuardSeverity",
    "GuardViolation",
    "GuardResult",
    "BaseGuard",
    "GuardMode",
    "AIFailureModeDetector",
    "AI_FAILURE_MODES",
    "CodeGuard",
    "TestGuard",
    "DocsGuard",
]
