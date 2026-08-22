"""
Unit Test Suite for PromptRegistry.
"""

import pytest

from core.prompt_registry import (
    PromptRegistry,
    PromptTemplate,
    prompt_registry,
)


@pytest.fixture
def registry():
    return PromptRegistry(cache_ttl_seconds=60)


def test_prompt_template_rendering():
    tmpl = PromptTemplate(
        name="test_prompt",
        system_prompt="System instructions for {{user_name}} in {{project_name}}",
        user_template="Perform study on {target_bus}",
    )
    sys_res, user_res = tmpl.render(
        user_name="Eng. Ahmed",
        project_name="Substation Alpha",
        target_bus="BUS_101",
    )
    assert "Eng. Ahmed" in sys_res
    assert "Substation Alpha" in sys_res
    assert "BUS_101" in user_res


def test_prompt_registry_fallback_to_yaml_or_default(registry):
    # Test existing prompt
    tmpl = registry.get_prompt("load_flow_agent")
    assert isinstance(tmpl, PromptTemplate)
    assert tmpl.name == "load_flow_agent"
    assert len(tmpl.system_prompt) > 10
    assert tmpl.source in ("cloud_langfuse", "local_yaml", "default")


def test_prompt_registry_caching(registry):
    # First call
    t1 = registry.get_prompt("arcflash_agent")
    # Second call (must be fast from cache)
    t2 = registry.get_prompt("arcflash_agent")
    assert t1 is t2


def test_prompt_registry_unknown_prompt(registry):
    tmpl = registry.get_prompt("custom_unknown_agent_xyz")
    assert tmpl.name == "custom_unknown_agent_xyz"
    assert tmpl.source == "default"
    assert "custom_unknown_agent_xyz" in tmpl.system_prompt
