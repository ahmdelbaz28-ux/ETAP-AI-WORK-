"""
Prompt Registry Module for AhmedETAP
====================================
Unified, deep prompt resolution and caching seam across TypeScript & Python runtimes.

Capabilities:
- 3-tier fallback resolution:
    1. Langfuse / LangWatch Cloud Prompt Management API
    2. Local YAML files (`prompts/<agent>.yaml`)
    3. Built-in hardcoded engineering prompt defaults
- In-memory caching with TTL to minimize network overhead and ensure zero-latency routing.
- Variable template interpolation for both `{{input}}` and `{input}` syntax.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Represents a resolved, versioned prompt template."""

    name: str
    system_prompt: str
    user_template: str = "{{input}}"
    model: str = "gpt-4o"
    temperature: float = 0.2
    version: str = "1.0.0"
    source: str = "default"  # "cloud_langfuse", "cloud_langwatch", "local_yaml", "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def render(self, **kwargs) -> tuple[str, str]:
        """Render (system_prompt, user_prompt) with kwargs substituted."""
        rendered_user = self.user_template
        rendered_system = self.system_prompt

        for key, val in kwargs.items():
            str_val = str(val)
            # Support {{key}} and {key}
            rendered_user = rendered_user.replace(f"{{{{{key}}}}}", str_val).replace(
                f"{{{key}}}", str_val
            )
            rendered_system = rendered_system.replace(f"{{{{{key}}}}}", str_val).replace(
                f"{{{key}}}", str_val
            )

        return rendered_system, rendered_user


class PromptRegistry:
    """
    Central repository for engineering agent prompts with transparent cloud sync and offline fallbacks.
    """

    DEFAULT_PROMPTS = {
        "load_flow_agent": (
            "You are the Load Flow Specialist for AhmedETAP. You perform Newton-Raphson power flow analysis per IEEE 3002.7.",
            "{{input}}",
        ),
        "short_circuit_agent": (
            "You are the Short Circuit Specialist for AhmedETAP. You calculate fault currents and equipment ratings per IEC 60909.",
            "{{input}}",
        ),
        "arcflash_agent": (
            "You are the Arc Flash Hazard Specialist for AhmedETAP. You calculate incident energy and PPE category per IEEE 1584.",
            "{{input}}",
        ),
        "protection_agent": (
            "You are the Protection Coordination Specialist for AhmedETAP. You analyze relay coordination and time-current curves per IEC 60255.",
            "{{input}}",
        ),
        "etap_expert_agent": (
            "You are the senior ETAP Expert Engineer for AhmedETAP. You provide deterministic, standards-validated power systems advice.",
            "{{input}}",
        ),
    }

    def __init__(self, cache_ttl_seconds: int = 3600):
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[PromptTemplate, float]] = {}
        self.prompts_dir = Path(__file__).resolve().parent.parent / "prompts"

    def get_prompt(self, prompt_name: str, force_refresh: bool = False) -> PromptTemplate:
        """
        Retrieve a prompt template using 3-tier fallback resolution.
        """
        now = time.time()

        # Check in-memory cache
        if not force_refresh and prompt_name in self._cache:
            template, cached_at = self._cache[prompt_name]
            if now - cached_at < self.cache_ttl_seconds:
                return template

        # Tier 1: Cloud Resolution (Langfuse / LangWatch)
        cloud_template = self._fetch_from_cloud(prompt_name)
        if cloud_template:
            self._cache[prompt_name] = (cloud_template, now)
            return cloud_template

        # Tier 2: Local YAML
        yaml_template = self._fetch_from_local_yaml(prompt_name)
        if yaml_template:
            self._cache[prompt_name] = (yaml_template, now)
            return yaml_template

        # Tier 3: Built-in Default
        default_template = self._fetch_default(prompt_name)
        self._cache[prompt_name] = (default_template, now)
        return default_template

    def _fetch_from_cloud(self, prompt_name: str) -> Optional[PromptTemplate]:
        """Fetch prompt from Langfuse or LangWatch API if available."""
        # Try Langfuse
        lf_public = os.environ.get("LANGFUSE_PUBLIC_KEY")
        lf_secret = os.environ.get("LANGFUSE_SECRET_KEY")
        if lf_public and lf_secret:
            try:
                import httpx

                b64 = base64.b64encode(f"{lf_public}:{lf_secret}".encode()).decode()
                r = httpx.get(
                    f"https://cloud.langfuse.com/api/public/v2/prompts/{prompt_name}",
                    headers={"Authorization": f"Basic {b64}"},
                    timeout=3.0,
                )
                if r.status_code == 200:
                    data = r.json()
                    prompt_data = data.get("prompt", "")
                    if isinstance(prompt_data, list):
                        sys_prompt = next(
                            (m.get("content") for m in prompt_data if m.get("role") == "system"), ""
                        )
                        user_prompt = next(
                            (m.get("content") for m in prompt_data if m.get("role") == "user"),
                            "{{input}}",
                        )
                    else:
                        sys_prompt = str(prompt_data)
                        user_prompt = "{{input}}"

                    return PromptTemplate(
                        name=prompt_name,
                        system_prompt=sys_prompt,
                        user_template=user_prompt,
                        version=str(data.get("version", "cloud")),
                        source="cloud_langfuse",
                    )
            except Exception as e:
                logger.debug("Langfuse cloud prompt fetch skipped for %s: %s", prompt_name, e)

        return None

    def _fetch_from_local_yaml(self, prompt_name: str) -> Optional[PromptTemplate]:
        """Fetch prompt from local prompts/ directory."""
        if not YAML_AVAILABLE or not self.prompts_dir.exists():
            return None

        candidates = [
            self.prompts_dir / f"{prompt_name}.prompt.yaml",
            self.prompts_dir / f"{prompt_name}.yaml",
            self.prompts_dir / f"{prompt_name}_prompt.yaml",
        ]

        for filepath in candidates:
            if filepath.exists():
                try:
                    with open(filepath, encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        messages = data.get("messages", [])
                        sys_msg = next(
                            (m.get("content", "") for m in messages if m.get("role") == "system"),
                            "",
                        )
                        user_msg = next(
                            (m.get("content", "") for m in messages if m.get("role") == "user"),
                            "{{input}}",
                        )
                        return PromptTemplate(
                            name=prompt_name,
                            system_prompt=sys_msg or data.get("prompt", ""),
                            user_template=user_msg or "{{input}}",
                            model=data.get("model", "gpt-4o"),
                            temperature=float(data.get("temperature", 0.2)),
                            version="local_yaml",
                            source="local_yaml",
                        )
                except Exception as e:
                    logger.debug("Failed parsing YAML prompt %s: %s", filepath, e)

        return None

    def _fetch_default(self, prompt_name: str) -> PromptTemplate:
        """Return fallback engineering prompt."""
        if prompt_name in self.DEFAULT_PROMPTS:
            sys_p, user_p = self.DEFAULT_PROMPTS[prompt_name]
        else:
            sys_p = f"You are the {prompt_name} specialist for AhmedETAP power system engineering platform."
            user_p = "{{input}}"

        return PromptTemplate(
            name=prompt_name,
            system_prompt=sys_p,
            user_template=user_p,
            source="default",
        )


# Global singleton instance
prompt_registry = PromptRegistry()
