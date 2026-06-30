"""
tests/test_multi_vendor_vision.py — Tests for the multi-vendor vision chain

Verifies that the HybridVisionRouter correctly chains through:
  Gemini → OpenAI → Anthropic → OpenCV

Tests run on any environment without crashing. When API keys are missing,
we verify graceful fallback behavior.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. Module imports
# ---------------------------------------------------------------------------


def test_openai_vision_module_imports_cleanly():
    """integrations.openai_vision must be importable on any environment."""
    from integrations import openai_vision

    assert hasattr(openai_vision, "OpenAIVisionClient")
    assert hasattr(openai_vision, "openai_vision")


def test_anthropic_vision_module_imports_cleanly():
    """integrations.anthropic_vision must be importable on any environment."""
    from integrations import anthropic_vision

    assert hasattr(anthropic_vision, "AnthropicVisionClient")
    assert hasattr(anthropic_vision, "anthropic_vision")


# ---------------------------------------------------------------------------
# 2. Health checks
# ---------------------------------------------------------------------------


def test_openai_vision_health_check_returns_dict():
    """health_check() must return a dict, never crash."""
    from integrations.openai_vision import openai_vision

    health = openai_vision.health_check()
    assert isinstance(health, dict)
    assert "enabled" in health
    assert "model" in health
    assert "base_url" in health
    assert "api_key_set" in health


def test_anthropic_vision_health_check_returns_dict():
    """health_check() must return a dict, never crash."""
    from integrations.anthropic_vision import anthropic_vision

    health = anthropic_vision.health_check()
    assert isinstance(health, dict)
    assert "enabled" in health
    assert "model" in health
    assert "base_url" in health
    assert "api_key_set" in health


def test_openai_vision_returns_none_when_disabled():
    """When OpenAI is disabled, analyze_screenshot must return None."""
    from integrations.openai_vision import OpenAIVisionClient

    with patch.dict(os.environ, {}, clear=True):
        client = OpenAIVisionClient()
        if not client.enabled:
            result = client.analyze_screenshot(image=b"fake", objective="test")
            assert result is None
        else:
            pytest.skip("OpenAI API key set — skip disabled test")


def test_anthropic_vision_returns_none_when_disabled():
    """When Anthropic is disabled, analyze_screenshot must return None."""
    from integrations.anthropic_vision import AnthropicVisionClient

    with patch.dict(os.environ, {}, clear=True):
        client = AnthropicVisionClient()
        if not client.enabled:
            result = client.analyze_screenshot(image=b"fake", objective="test")
            assert result is None
        else:
            pytest.skip("Anthropic API key set — skip disabled test")


# ---------------------------------------------------------------------------
# 3. HybridVisionRouter multi-vendor chain
# ---------------------------------------------------------------------------


def test_hybrid_vision_router_includes_all_backends():
    """HybridVisionRouter must know about all 4 backends."""
    from integrations.resilience import hybrid_vision

    health = hybrid_vision.health_check()
    assert "gemini" in health
    assert "openai" in health
    assert "anthropic" in health
    assert "opencv" in health


def test_hybrid_vision_router_chain_built():
    """The router must build a chain of available backends."""
    from integrations.resilience import hybrid_vision

    # The chain should be a list
    assert hasattr(hybrid_vision, "chain")
    assert isinstance(hybrid_vision.chain, list)
    # Each entry should be a tuple of (name, backend)
    for entry in hybrid_vision.chain:
        assert isinstance(entry, tuple)
        assert len(entry) == 2
        name, backend = entry
        assert name in ("gemini", "openai", "anthropic", "opencv")


def test_hybrid_vision_router_health_includes_chain():
    """health_check() must report the chain and fallback_count."""
    from integrations.resilience import hybrid_vision

    health = hybrid_vision.health_check()
    assert "chain" in health
    assert "fallback_count" in health
    assert "primary" in health
    assert isinstance(health["chain"], list)
    assert isinstance(health["fallback_count"], int)


def test_hybrid_vision_router_priority_order():
    """The chain must follow priority: Gemini → OpenAI → Anthropic → OpenCV."""
    from integrations.resilience import hybrid_vision

    # Get the names in the chain
    chain_names = [name for name, _ in hybrid_vision.chain]

    # Verify priority order (each backend should come after higher-priority ones)
    # If both gemini and openai are enabled, gemini must come first
    if "gemini" in chain_names and "openai" in chain_names:
        assert chain_names.index("gemini") < chain_names.index("openai")
    if "openai" in chain_names and "anthropic" in chain_names:
        assert chain_names.index("openai") < chain_names.index("anthropic")
    if "anthropic" in chain_names and "opencv" in chain_names:
        assert chain_names.index("anthropic") < chain_names.index("opencv")
    # OpenCV should always be last if present
    if "opencv" in chain_names:
        assert chain_names[-1] == "opencv"


# ---------------------------------------------------------------------------
# 4. Integration with CUA executors
# ---------------------------------------------------------------------------


def test_cua_executor_uses_hybrid_vision_with_multi_vendor():
    """CUAExecutor must use HybridVisionRouter (which now has multi-vendor)."""
    p = Path(__file__).resolve().parent.parent / "agents" / "cua_executor.py"
    content = p.read_text(encoding="utf-8")
    assert "hybrid_vision" in content
    assert "from integrations.resilience import" in content


def test_browser_cua_executor_uses_hybrid_vision_with_multi_vendor():
    """BrowserCUAExecutor must use HybridVisionRouter (which now has multi-vendor)."""
    p = Path(__file__).resolve().parent.parent / "agents" / "browser_cua_executor.py"
    content = p.read_text(encoding="utf-8")
    assert "hybrid_vision" in content
    assert "from integrations.resilience import" in content


# ---------------------------------------------------------------------------
# 5. Configuration
# ---------------------------------------------------------------------------


def test_env_vars_documented():
    """All multi-vendor env vars must be documented in .env.example."""
    p = Path(__file__).resolve().parent.parent / ".env.example"
    content = p.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" in content
    assert "OPENAI_BASE_URL" in content
    assert "OPENAI_VISION_MODEL" in content
    assert "ANTHROPIC_API_KEY" in content
    assert "ANTHROPIC_VISION_MODEL" in content
    assert "GEMINI_API_KEY" in content


def test_requirements_include_httpx():
    """requirements.txt must include httpx for OpenAI/Anthropic clients."""
    p = Path(__file__).resolve().parent.parent / "requirements.txt"
    content = p.read_text(encoding="utf-8")
    assert "httpx" in content.lower()


def test_hf_requirements_include_httpx():
    """hf-space/requirements.hf.txt must include httpx."""
    p = Path(__file__).resolve().parent.parent / "hf-space" / "requirements.hf.txt"
    content = p.read_text(encoding="utf-8")
    assert "httpx" in content.lower()


# ---------------------------------------------------------------------------
# 6. OpenAI-compatible endpoint support
# ---------------------------------------------------------------------------


def test_openai_vision_supports_custom_base_url():
    """OpenAIVisionClient must support custom base_url (Azure, Together, etc.)."""
    from integrations.openai_vision import OpenAIVisionClient

    with patch.dict(
        os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_BASE_URL": "https://custom.api.com/v1"}
    ):
        client = OpenAIVisionClient()
        assert client.enabled is True
        assert "custom.api.com" in client.base_url


def test_openai_vision_default_base_url():
    """Default base_url must be OpenAI's official endpoint."""
    from integrations.openai_vision import OpenAIVisionClient

    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
        client = OpenAIVisionClient()
        assert "api.openai.com" in client.base_url


# ---------------------------------------------------------------------------
# 7. Smoke test: full chain import
# ---------------------------------------------------------------------------


def test_full_multi_vendor_chain_imports_cleanly():
    """All vision modules must import without crashing."""
    from integrations.anthropic_vision import anthropic_vision
    from integrations.gemini_vision import gemini_vision
    from integrations.openai_vision import openai_vision
    from integrations.opencv_vision import opencv_vision
    from integrations.resilience import hybrid_vision

    assert gemini_vision is not None
    assert openai_vision is not None
    assert anthropic_vision is not None
    assert opencv_vision is not None
    assert hybrid_vision is not None

    # The hybrid router must have checked all backends
    health = hybrid_vision.health_check()
    assert "gemini" in health
    assert "openai" in health
    assert "anthropic" in health
    assert "opencv" in health


# ---------------------------------------------------------------------------
# 8. Fallback behavior simulation
# ---------------------------------------------------------------------------


def test_fallback_chain_continues_on_backend_failure():
    """If the primary backend fails, the router must try the next one."""
    from integrations.resilience import HybridVisionRouter

    # Create a router with mocked backends
    router = HybridVisionRouter()

    # Mock the backends
    router.gemini = MagicMock()
    router.gemini.enabled = True
    router.gemini.analyze_screenshot = MagicMock(return_value={"error": "geo_blocked"})

    router.openai = MagicMock()
    router.openai.enabled = True
    router.openai.analyze_screenshot = MagicMock(
        return_value={
            "description": "test",
            "next_action": {"type": "done", "summary": "ok"},
            "source": "openai",
        }
    )

    router.anthropic = MagicMock()
    router.anthropic.enabled = False

    router.opencv = MagicMock()
    router.opencv.enabled = True

    # Rebuild the chain
    router.chain = []
    if router.gemini.enabled:
        router.chain.append(("gemini", router.gemini))
    if router.openai.enabled:
        router.chain.append(("openai", router.openai))
    if router.anthropic.enabled:
        router.chain.append(("anthropic", router.anthropic))
    if router.opencv.enabled:
        router.chain.append(("opencv", router.opencv))

    # Call analyze_screenshot — should fall back from Gemini to OpenAI
    result = router.analyze_screenshot(image=b"fake", objective="test")

    # OpenAI should have been called (Gemini failed)
    assert router.gemini.analyze_screenshot.called
    assert router.openai.analyze_screenshot.called
    # Result should be from OpenAI
    assert result is not None
    assert result.get("source") == "openai"
    assert "error" not in result
