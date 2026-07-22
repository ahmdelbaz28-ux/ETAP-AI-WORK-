# 3-tier prompt fallback: LangWatch → local YAML → hardcoded default

Agent prompts use a 3-tier fallback: (1) LangWatch API for remote versioned prompts, (2) local YAML files in `prompts/` for offline operation, (3) hardcoded defaults. This ensures agents always function even when network or external services are unavailable. The trade-off is that prompt drift can occur between LangWatch and local YAML, requiring a sync process. We accept this because safety-critical engineering agents must never fail due to a missing prompt — the hardcoded fallback guarantees execution continues.
