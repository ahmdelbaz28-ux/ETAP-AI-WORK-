"""
Tests for prompt integration into agents.

Verifies:
1. All 14 Python agents + orchestrator load their prompts successfully
2. Prompt loader 3-tier fallback works correctly
3. Agents fail gracefully when prompts are missing
4. All 27 YAML prompt files are accessible via the prompt loader
5. Agent get_agent_info() returns correct prompt metadata
6. The /api/v1/agents/info endpoint would return valid data
"""

import logging
import os
import pytest
from pathlib import Path
from unittest.mock import patch

# Suppress noisy logs during tests
logging.basicConfig(level=logging.WARNING)

# Ensure we're testing from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestPromptLoader:
    """Tests for the agents.prompt_loader module."""

    def test_list_available_prompts(self):
        """All 27+ YAML prompt files should be discoverable."""
        from agents.prompt_loader import list_available_prompts

        prompts = list_available_prompts()
        assert len(prompts) >= 25, f"Expected >= 25 prompts, found {len(prompts)}"

    def test_load_existing_prompt(self):
        """Loading a known prompt handle should return non-empty content."""
        from agents.prompt_loader import get_system_prompt, clear_prompt_cache

        clear_prompt_cache()
        prompt = get_system_prompt("load_flow_agent")
        assert len(prompt) > 50, "Load flow prompt should be > 50 chars"
        assert "IEEE" in prompt or "load flow" in prompt.lower()

    def test_load_all_agent_prompts(self):
        """Every agent-specific prompt should load successfully."""
        from agents.prompt_loader import get_system_prompt, clear_prompt_cache

        agent_handles = [
            "load_flow_agent",
            "short_circuit_agent",
            "harmonic_agent",
            "opf_agent",
            "protection_agent",
            "motor_starting_agent",
            "stability_agent",
            "cable_sizing_agent",
            "earth_grid_agent",
            "renewable_agent",
            "battery_storage_agent",
            "scada_agent",
            "validation_agent",
            "report_agent",
            "etap_engineer_agent",
        ]

        for handle in agent_handles:
            clear_prompt_cache()
            prompt = get_system_prompt(handle)
            assert len(prompt) > 20, f"Prompt '{handle}' returned too-short content ({len(prompt)} chars)"

    def test_fallback_for_missing_prompt(self):
        """A non-existent prompt handle should return a fallback string, not crash."""
        from agents.prompt_loader import get_system_prompt, clear_prompt_cache

        clear_prompt_cache()
        prompt = get_system_prompt("nonexistent_agent_xyz_12345")
        assert isinstance(prompt, str)
        assert len(prompt) > 0, "Fallback prompt should not be empty"

    def test_missing_prompts_dir_graceful(self):
        """When prompts directory doesn't exist, should still return fallback."""
        from agents.prompt_loader import get_system_prompt, clear_prompt_cache

        original_dir = os.environ.get("ETAP_PROMPTS_DIR", "")
        try:
            os.environ["ETAP_PROMPTS_DIR"] = "/nonexistent/directory"
            clear_prompt_cache()
            prompt = get_system_prompt("load_flow_agent")
            assert isinstance(prompt, str)
            assert len(prompt) > 0
        finally:
            if original_dir:
                os.environ["ETAP_PROMPTS_DIR"] = original_dir
            else:
                os.environ.pop("ETAP_PROMPTS_DIR", None)
            clear_prompt_cache()

    def test_prompt_caching(self):
        """Second call to same handle should return cached result."""
        from agents.prompt_loader import get_system_prompt, clear_prompt_cache, _prompt_cache

        clear_prompt_cache()
        prompt1 = get_system_prompt("load_flow_agent")
        prompt2 = get_system_prompt("load_flow_agent")
        assert prompt1 == prompt2, "Cached prompt should match first call"
        assert "load_flow_agent" in _prompt_cache

    def test_clear_prompt_cache(self):
        """Cache clear should reset stored prompts."""
        from agents.prompt_loader import get_system_prompt, clear_prompt_cache, _prompt_cache

        clear_prompt_cache()
        get_system_prompt("load_flow_agent")
        assert "load_flow_agent" in _prompt_cache
        clear_prompt_cache()
        assert "load_flow_agent" not in _prompt_cache

    def test_get_prompt_metadata(self):
        """get_prompt_metadata should return model and temperature."""
        from agents.prompt_loader import get_prompt_metadata

        meta = get_prompt_metadata("load_flow_agent")
        assert isinstance(meta, dict)
        assert "model" in meta, "Metadata should contain 'model'"
        assert "temperature" in meta, "Metadata should contain 'temperature'"
        assert meta["model"] == "gpt-4o"
        assert isinstance(meta["temperature"], (int, float))

    def test_fallback_agent_prompt_exists(self):
        """The fallback_agent prompt should be loadable."""
        from agents.prompt_loader import get_system_prompt, clear_prompt_cache

        clear_prompt_cache()
        prompt = get_system_prompt("fallback_agent")
        assert len(prompt) > 10, "Fallback prompt should exist and be non-trivial"


class TestAgentPromptIntegration:
    """Tests for prompt integration in the BaseAgent and all agent classes."""

    def test_base_agent_derive_prompt_handle(self):
        """BaseAgent should derive handle from class name via CamelCase conversion."""
        from agents.orchestrator import LoadFlowAgent

        agent = LoadFlowAgent()
        assert agent.prompt_handle == "load_flow_agent", \
            f"Expected 'load_flow_agent', got '{agent.prompt_handle}'"

    def test_load_flow_agent_prompt_loaded(self):
        """LoadFlowAgent should have its prompt loaded at init."""
        from agents.orchestrator import LoadFlowAgent

        agent = LoadFlowAgent()
        assert agent._system_prompt is not None
        assert len(agent._system_prompt) > 50
        assert "IEEE" in agent._system_prompt or "load flow" in agent._system_prompt.lower()

    def test_all_orchestrator_agents_have_prompts(self):
        """All agents in the orchestrator should have prompts loaded."""
        from agents.orchestrator import ChiefEngineeringOrchestrator

        orch = ChiefEngineeringOrchestrator()
        for key, agent in orch.agents.items():
            assert agent._system_prompt is not None, \
                f"Agent '{key}' ({agent.agent_name}) has no prompt loaded"
            assert len(agent._system_prompt) > 20, \
                f"Agent '{key}' prompt is too short ({len(agent._system_prompt)} chars)"

    def test_orchestrator_has_prompt(self):
        """ChiefEngineeringOrchestrator should have its own prompt loaded."""
        from agents.orchestrator import ChiefEngineeringOrchestrator

        orch = ChiefEngineeringOrchestrator()
        assert orch._system_prompt is not None
        assert orch.prompt_handle == "power_system_coordinator_agent"

    def test_get_agent_info(self):
        """get_agent_info() should return correct metadata."""
        from agents.orchestrator import LoadFlowAgent

        agent = LoadFlowAgent()
        info = agent.get_agent_info()
        assert info["agent_name"] == "LoadFlowAgent"
        assert info["prompt_handle"] == "load_flow_agent"
        assert info["prompt_loaded"] is True
        assert info["model"] == "gpt-4o"
        assert isinstance(info["temperature"], float)
        assert info["status"] == "idle"

    def test_orchestrator_get_agents_info(self):
        """Orchestrator get_agents_info() should return data for all agents."""
        from agents.orchestrator import ChiefEngineeringOrchestrator

        orch = ChiefEngineeringOrchestrator()
        info = orch.get_agents_info()
        assert "orchestrator" in info
        assert "agents" in info
        assert len(info["agents"]) == 8  # 8 core agents in orchestrator

    def test_extended_agents_have_prompts(self):
        """Extended agent classes should also load their prompts."""
        from agents.stability_agent import StabilityAgent
        from agents.cable_sizing_agent import CableSizingAgent
        from agents.earth_grid_agent import EarthGridAgent
        from agents.renewable_agent import RenewableAgent
        from agents.battery_storage_agent import BatteryStorageAgent
        from agents.scada_agent import SCADAAgent

        for cls in [StabilityAgent, CableSizingAgent, EarthGridAgent,
                     RenewableAgent, BatteryStorageAgent, SCADAAgent]:
            agent = cls()
            assert agent._system_prompt is not None, \
                f"{cls.__name__} has no prompt loaded"
            assert len(agent._system_prompt) > 50, \
                f"{cls.__name__} prompt is too short"

    def test_agent_graceful_prompt_failure(self):
        """Agent should still work when prompt loading fails."""
        from agents.orchestrator import LoadFlowAgent

        original_dir = os.environ.get("ETAP_PROMPTS_DIR", "")
        try:
            os.environ["ETAP_PROMPTS_DIR"] = "/nonexistent/directory"
            from agents.prompt_loader import clear_prompt_cache
            clear_prompt_cache()
            agent = LoadFlowAgent()
            # Agent should still have a system_prompt property (fallback)
            assert len(agent.system_prompt) > 0
            # Agent should still be functional
            assert agent.agent_name == "LoadFlowAgent"
        finally:
            if original_dir:
                os.environ["ETAP_PROMPTS_DIR"] = original_dir
            else:
                os.environ.pop("ETAP_PROMPTS_DIR", None)
            clear_prompt_cache()

    def test_explicit_prompt_handle_overrides_derived(self):
        """Explicit prompt_handle in subclass should override derived one."""
        from agents.orchestrator import ShortCircuitAgent

        agent = ShortCircuitAgent()
        assert agent.prompt_handle == "short_circuit_agent"

    def test_harmonic_agent_prompt_handle(self):
        """HarmonicAnalysisAgent should use 'harmonic_agent' handle."""
        from agents.orchestrator import HarmonicAnalysisAgent

        agent = HarmonicAnalysisAgent()
        assert agent.prompt_handle == "harmonic_agent"


class TestPromptHandleMapping:
    """Verify that every YAML prompt has a corresponding agent or system consumer."""

    def test_all_prompts_mapped(self):
        """Every prompt YAML file should have a corresponding agent or documented use."""
        from agents.prompt_loader import list_available_prompts

        # Known prompt-to-consumer mapping
        prompt_consumers = {
            "load_flow_agent": "LoadFlowAgent + loadFlowAgent (TS)",
            "short_circuit_agent": "ShortCircuitAgent + shortCircuitAgent (TS)",
            "harmonic_agent": "HarmonicAnalysisAgent",
            "opf_agent": "OptimalPowerFlowAgent",
            "protection_agent": "ProtectionCoordinationAgent + protectionAgent (TS)",
            "motor_starting_agent": "motorStartingAgent (TS)",
            "stability_agent": "StabilityAgent",
            "cable_sizing_agent": "CableSizingAgent",
            "earth_grid_agent": "EarthGridAgent",
            "renewable_agent": "RenewableAgent",
            "battery_storage_agent": "BatteryStorageAgent",
            "scada_agent": "SCADAAgent",
            "validation_agent": "ValidationAgent",
            "report_agent": "ReportGenerationAgent",
            "etap_engineer_agent": "ETAPExecutionAgent + etapEngineerAgent (TS)",
            "etap_engineer_agent_v2": "Reserved for V2 agent variant",
            "arcflash_agent_prompt": "arcFlashAgent (TS)",
            "goal_planner_agent": "goalPlannerAgent (TS)",
            "weather_agent": "weatherAgent (TS)",
            "weather_activity_planner": "Weather workflow (TS)",
            "power_system_coordinator_agent": "ChiefEngineeringOrchestrator + powerSystemCoordinatorAgent (TS)",
            "fallback_agent": "Fallback prompt for missing handles",
            "generic_agent_chat": "Generic chat fallback",
            "anomaly_agent": "AnomalyAgent (future ML)",
            "coordination_agent": "CoordinationAgent (future relay)",
            "digital_twin_agent": "DigitalTwinAgent (future DT)",
            "predictive_agent": "PredictiveAgent (future ML)",
            "sample_prompt": "Template/sample only",
        }

        prompts = list_available_prompts()
        unmapped = []
        for p in prompts:
            if p not in prompt_consumers:
                unmapped.append(p)

        assert len(unmapped) == 0, \
            f"Unmapped prompts: {unmapped}. Add them to the consumer mapping."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
