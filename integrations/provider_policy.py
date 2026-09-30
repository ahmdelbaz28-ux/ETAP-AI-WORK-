"""
integrations/provider_policy.py — Single-point LLM provider policy loader (M4.5).

``config/llm-provider-policy.json`` is THE provider/model policy decision
point. This module is the only Python reader of that document and is
deliberately stdlib-only (``json`` + ``pathlib``) so light-weight consumers
such as ``api.chat_stream`` can import it without dragging in the OpenAI /
Langfuse stack.

Fail-closed contract
--------------------
Every read goes through :func:`load_provider_policy`, which validates the
document before returning it. A missing file, malformed JSON, duplicate
provider id, empty tier or unknown cascade tier raises
:class:`ProviderPolicyError` — consumers must surface the error, never
silently fall back to a hard-coded allow-list.

Consumers
---------
* ``integrations/model_router.py``  — re-exports ``get_provider_policy`` /
  ``resolve_model`` (the cascade decision point).
* ``api/chat_stream.py``            — provider allow-list + env mapping.
* ``src/core/providers.ts``         — same document, read at build time.
* ``src/mastra/lib/model-config.ts``— same document, read at build time.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

#: Repository-relative location of the single policy document.
DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "llm-provider-policy.json"
)

#: Environment override (used by tests and by deployments that vendor the file).
POLICY_PATH_ENV = "LLM_PROVIDER_POLICY_PATH"

#: Known surfaces a provider may be exposed on.
KNOWN_SURFACES = frozenset({"chat_stream", "edge_gateway", "mastra"})

_lock = threading.RLock()
_cache: dict[str, Any] | None = None
_cache_path: str | None = None


class ProviderPolicyError(RuntimeError):
    """Raised when the provider policy document is missing or invalid."""


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_provider_policy(doc: Any) -> list[str]:
    """Return a list of policy problems (empty ⇒ valid). Never raises."""
    problems: list[str] = []

    if not isinstance(doc, dict):
        return ["policy document must be a JSON object"]

    providers = doc.get("providers")
    if not isinstance(providers, list) or not providers:
        problems.append("'providers' must be a non-empty list")
        providers = []

    seen: set[str] = set()
    for i, entry in enumerate(providers):
        if not isinstance(entry, dict):
            problems.append(f"providers[{i}] must be an object")
            continue
        pid = entry.get("id")
        if not isinstance(pid, str) or not pid:
            problems.append(f"providers[{i}] has no 'id'")
            continue
        if pid in seen:
            problems.append(f"duplicate provider id '{pid}'")
        seen.add(pid)

        if entry.get("enabled") not in (True, False):
            problems.append(f"provider '{pid}': 'enabled' must be a boolean")

        surfaces = entry.get("surfaces")
        if not isinstance(surfaces, list) or not surfaces:
            problems.append(f"provider '{pid}': 'surfaces' must be a non-empty list")
        else:
            unknown = [s for s in surfaces if s not in KNOWN_SURFACES]
            if unknown:
                problems.append(f"provider '{pid}': unknown surface(s) {unknown}")

        env = entry.get("env")
        if not isinstance(env, dict) or not all(
            isinstance(env.get(k), str) and env.get(k)
            for k in ("api_key", "base_url", "model")
        ):
            problems.append(f"provider '{pid}': 'env' must define api_key/base_url/model")

        if not isinstance(entry.get("default_model"), str) or not entry.get("default_model"):
            problems.append(f"provider '{pid}': 'default_model' must be a non-empty string")
        if not isinstance(entry.get("base_url"), str) or not entry.get("base_url"):
            problems.append(f"provider '{pid}': 'base_url' must be a non-empty string")

    tiers = doc.get("model_tiers")
    if not isinstance(tiers, dict) or not tiers:
        problems.append("'model_tiers' must be a non-empty object")
        tiers = {}
    for tier_name, models in tiers.items():
        if not isinstance(models, list) or not models:
            problems.append(f"model_tiers['{tier_name}'] must be a non-empty list")

    cascade = doc.get("cascade")
    if not isinstance(cascade, dict):
        problems.append("'cascade' must be an object")
        cascade = {}

    default_tier = cascade.get("default_tier")
    if default_tier is not None and default_tier not in tiers:
        problems.append(f"cascade.default_tier '{default_tier}' is not a declared tier")

    escalation = cascade.get("escalation")
    if escalation is not None:
        if not isinstance(escalation, dict):
            problems.append("cascade.escalation must be an object")
        else:
            for src, dst in escalation.items():
                if src not in tiers:
                    problems.append(
                        f"cascade.escalation source '{src}' is not a declared tier"
                    )
                if dst is not None and dst not in tiers:
                    problems.append(
                        f"cascade.escalation target '{dst}' is not a declared tier"
                    )

    return problems


# ─────────────────────────────────────────────────────────────────────────────
# Loading (cached, fail-closed)
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_policy_path(path: str | os.PathLike[str] | None = None) -> Path:
    if path is not None:
        return Path(path)
    env_path = os.environ.get(POLICY_PATH_ENV)
    if env_path:
        return Path(env_path)
    return DEFAULT_POLICY_PATH


def load_provider_policy(
    path: str | os.PathLike[str] | None = None,
    *,
    reload: bool = False,
) -> dict[str, Any]:
    """Load **and validate** the provider policy document (fail-closed).

    The result is cached per resolved path; pass ``reload=True`` (or change
    ``LLM_PROVIDER_POLICY_PATH``) to re-read.
    """
    global _cache, _cache_path

    resolved = _resolve_policy_path(path)
    key = str(resolved.resolve()) if resolved.exists() else str(resolved)

    with _lock:
        if not reload and _cache is not None and _cache_path == key:
            return _cache

        if not resolved.is_file():
            raise ProviderPolicyError(
                f"LLM provider policy not found at '{resolved}'. "
                "config/llm-provider-policy.json is the single policy point "
                "and MUST ship with the deployment."
            )

        try:
            doc = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderPolicyError(
                f"LLM provider policy at '{resolved}' could not be parsed: {exc}"
            ) from exc

        problems = validate_provider_policy(doc)
        if problems:
            raise ProviderPolicyError(
                "LLM provider policy is invalid: " + "; ".join(problems)
            )

        _cache = doc
        _cache_path = key
        return doc


def get_provider_policy(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Return the validated provider policy (the single decision point)."""
    return load_provider_policy(path)


def invalidate_policy_cache() -> None:
    """Drop the cached document (tests / hot-reload)."""
    global _cache, _cache_path
    with _lock:
        _cache = None
        _cache_path = None


# ─────────────────────────────────────────────────────────────────────────────
# Derived views (what consumers actually use)
# ─────────────────────────────────────────────────────────────────────────────

def _enabled_on(policy: dict[str, Any], surface: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in policy.get("providers", []):
        if not entry.get("enabled", False):
            continue
        if surface is not None and surface not in entry.get("surfaces", []):
            continue
        out.append(entry)
    return out


def allowed_provider_ids(
    surface: str | None = None,
    path: str | os.PathLike[str] | None = None,
) -> tuple[str, ...]:
    """Provider ids enabled on ``surface`` — the canonical allow-list."""
    return tuple(e["id"] for e in _enabled_on(get_provider_policy(path), surface))


def provider_env_map(
    path: str | os.PathLike[str] | None = None,
) -> dict[str, dict[str, str]]:
    """``{provider_id: {"api_key": ENV, "base_url": ENV, "model": ENV}}``."""
    return {e["id"]: dict(e["env"]) for e in _enabled_on(get_provider_policy(path), None)}


def provider_defaults(
    surface: str | None = None,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, dict[str, str]]:
    """``{provider_id: {"base_url": ..., "default_model": ...}}``."""
    return {
        e["id"]: {"base_url": e["base_url"], "default_model": e["default_model"]}
        for e in _enabled_on(get_provider_policy(path), surface)
    }


def tier_models(
    tier: str,
    path: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Models declared for ``tier`` in the policy (fail-closed on unknown tier)."""
    policy = get_provider_policy(path)
    models = policy.get("model_tiers", {}).get(tier)
    if not models:
        raise ProviderPolicyError(f"tier '{tier}' is not declared in the policy")
    return list(models)


def declared_tiers(path: str | os.PathLike[str] | None = None) -> tuple[str, ...]:
    return tuple(get_provider_policy(path).get("model_tiers", {}).keys())


def cascade_enabled(path: str | os.PathLike[str] | None = None) -> bool:
    """Whether model cascading is enabled **by the policy** (not a feature flag)."""
    return bool(get_provider_policy(path).get("cascade", {}).get("enabled", False))


def escalation_target(
    tier: str,
    path: str | os.PathLike[str] | None = None,
) -> str | None:
    escalation = get_provider_policy(path).get("cascade", {}).get("escalation") or {}
    return escalation.get(tier)


def tier_of_model(
    model: str,
    path: str | os.PathLike[str] | None = None,
) -> str | None:
    """Reverse lookup: which tier declares ``model`` (first match wins)."""
    tiers = get_provider_policy(path).get("model_tiers", {})
    for tier_name, models in tiers.items():
        if model in (models or []):
            return tier_name
    return None


def iter_policy_providers(
    surface: str | None = None,
    path: str | os.PathLike[str] | None = None,
) -> Iterable[dict[str, Any]]:
    return tuple(_enabled_on(get_provider_policy(path), surface))
