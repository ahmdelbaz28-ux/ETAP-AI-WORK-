"""Integrations package for AhmedETAP external service connections."""

# Supabase (managed Postgres + Storage + optional Auth)
# Primary observability — Langfuse (unlimited prompts on free Hobby plan)
from integrations.langfuse_evals import (
    ci_gate_block_unsafe_prompts,
    ensure_safety_dataset,
    eval_helpfulness,
    eval_safety,
    eval_standards_compliance,
    run_safety_eval,
    score_trace,
    seed_safety_datasets,
)
from integrations.langfuse_integration import (
    LangfuseTracker,
    get_prompt_from_langfuse,
    langfuse_tracker,
    track_llm_call,
)
from integrations.langfuse_llm import (
    SafetyValidationError,
    anthropic,
    estimate_cost_usd,
    openai,
    safe_anthropic_message,
    safe_openai_chat,
)
from integrations.langfuse_llm import (
    health_check as llm_health_check,
)
from integrations.langfuse_middleware import (
    LangfuseMiddleware,
    install_langfuse_middleware,
)
from integrations.langfuse_sessions import (
    EngineeringSession,
    add_trace_comment,
    alert_on_unsafe_trace,
    end_engineering_session,
    get_trace_share_url,
    record_user_feedback,
    start_engineering_session,
)

# Legacy fallback — LangWatch (free plan capped at 3 prompts)
from integrations.langwatch_integration import (
    langwatch_tracker,
)
from integrations.langwatch_integration import (
    track_llm_call as track_llm_call_langwatch,
)

# Smithery MCP
from integrations.smithery_mcp import mcp_registry, smithery_client
from integrations.supabase_auth import (
    SupabaseAuthError,
    link_or_create_local_user,
    send_magic_link,
    verify_supabase_token,
)
from integrations.supabase_auth import (
    get_oauth_url as supabase_get_oauth_url,
)
from integrations.supabase_auth import (
    health_check as supabase_auth_health_check,
)
from integrations.supabase_integration import (
    PRIVATE_BUCKET_REPORTS,
    PRIVATE_BUCKET_SCREENSHOTS,
    PRIVATE_BUCKET_UPLOADS,
    PUBLIC_BUCKET_MANUALS,
    SupabaseUploadError,
    delete_file,
    ensure_buckets_exist,
    get_public_url,
    get_signed_url,
    list_files,
    upload_bytes,
    upload_file,
)
from integrations.supabase_integration import (
    health_check as supabase_health_check,
)

__all__ = [
    # Langfuse core (integration.py)
    "LangfuseTracker",
    "langfuse_tracker",
    "track_llm_call",
    "get_prompt_from_langfuse",
    # Langfuse LLM wrappers (langfuse_llm.py)
    "openai",
    "anthropic",
    "safe_openai_chat",
    "safe_anthropic_message",
    "estimate_cost_usd",
    "llm_health_check",
    "SafetyValidationError",
    # Langfuse evals (langfuse_evals.py)
    "ensure_safety_dataset",
    "eval_safety",
    "eval_standards_compliance",
    "eval_helpfulness",
    "run_safety_eval",
    "ci_gate_block_unsafe_prompts",
    "seed_safety_datasets",
    "score_trace",
    # Langfuse sessions/feedback/alerts (langfuse_sessions.py)
    "EngineeringSession",
    "start_engineering_session",
    "end_engineering_session",
    "record_user_feedback",
    "get_trace_share_url",
    "alert_on_unsafe_trace",
    "add_trace_comment",
    # Langfuse middleware (langfuse_middleware.py)
    "LangfuseMiddleware",
    "install_langfuse_middleware",
    # LangWatch (legacy)
    "langwatch_tracker",
    "track_llm_call_langwatch",
    # Smithery MCP
    "smithery_client",
    "mcp_registry",
    # Supabase (Postgres + Storage + Auth)
    "PUBLIC_BUCKET_MANUALS",
    "PRIVATE_BUCKET_REPORTS",
    "PRIVATE_BUCKET_SCREENSHOTS",
    "PRIVATE_BUCKET_UPLOADS",
    "SupabaseUploadError",
    "SupabaseAuthError",
    "upload_bytes",
    "upload_file",
    "get_public_url",
    "get_signed_url",
    "delete_file",
    "list_files",
    "ensure_buckets_exist",
    "supabase_health_check",
    "verify_supabase_token",
    "supabase_get_oauth_url",
    "send_magic_link",
    "link_or_create_local_user",
    "supabase_auth_health_check",
]
