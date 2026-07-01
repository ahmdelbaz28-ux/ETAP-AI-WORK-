"""Integrations package for AhmedETAP external service connections."""

from integrations.langfuse_integration import (
    LangfuseTracker,
    get_prompt_from_langfuse,
    langfuse_tracker,
    track_llm_call,
)
from integrations.langwatch_integration import (
    langwatch_tracker,
    track_llm_call as track_llm_call_langwatch,
)
from integrations.smithery_mcp import mcp_registry, smithery_client

__all__ = [
    # Langfuse (primary — unlimited prompts on free Hobby plan)
    "LangfuseTracker",
    "langfuse_tracker",
    "track_llm_call",  # ← default: Langfuse
    "get_prompt_from_langfuse",
    # LangWatch (legacy — free plan limited to 3 prompts)
    "langwatch_tracker",
    "track_llm_call_langwatch",
    # Smithery MCP
    "smithery_client",
    "mcp_registry",
]
