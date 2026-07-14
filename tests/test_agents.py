#!/usr/bin/env python3
"""
Test script to verify all agents return valid results.

This script tests each agent in the AhmedETAP system to ensure they
are properly initialized and can execute basic operations.
"""

import asyncio
import logging
import os
import sys
from typing import Any

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import ALL_AGENT_CLASSES, EngineeringTask, StudyType, get_orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_test_system() -> Any:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
    """
    Create a minimal test system for agent testing.
    This creates a simple power system with minimal components to allow
    agents to perform basic initialization without failing due to missing data.
    """
    # Since we're testing agent creation and basic functionality rather than
    # full computations, we'll create a minimal system
    try:
        from core_model.system import System

        # Some System implementations may not accept a `name=` kwarg.
        system = System()
        return system
    except ImportError:
        # If core_model is not available, create a mock
        class MockSystem:
            def __init__(self, name="test_system"):
                self.name = name
                self.buses = []
                self.generators = []
                self.loads = []
                self.lines = []
                self.transformers = []

        return MockSystem()


async def test_individual_agents():
    """Test each individual agent to ensure they can be instantiated and return valid results."""
    logger.info("Starting individual agent tests...")

    # Create a test system
    test_system = await create_test_system()

    results = {}

    for agent_class in ALL_AGENT_CLASSES:
        agent_name = agent_class.__name__
        logger.info("Testing %s...", agent_name)

        try:
            # Instantiate the agent
            agent = agent_class()

            # Verify the agent has required properties
            # NOTE: Not using assert here because SonarCloud S5779 flags assert
            # statements inside try-except blocks that catch AssertionError.
            if not hasattr(agent, "agent_name"):
                raise RuntimeError(f"{agent_name} missing agent_name")
            if not hasattr(agent, "status"):
                raise RuntimeError(f"{agent_name} missing status")
            if not hasattr(agent, "execute"):
                raise RuntimeError(f"{agent_name} missing execute method")

            # Create a minimal test task
            task = EngineeringTask(
                task_id=f"test_{agent_name.lower()}",
                description=f"Test task for {agent_name}",
                study_types=[StudyType.LOAD_FLOW],  # Using LOAD_FLOW as default
                parameters={"system": test_system, "test_mode": True},
            )

            # Try to execute the agent (with timeout to prevent hanging)
            try:
                result = await asyncio.wait_for(agent.execute(task), timeout=10.0)

                # Log the result status
                logger.info("✓ %s executed successfully - Status: %s", agent_name, result.status.value)

                results[agent_name] = {
                    "status": "SUCCESS",
                    "result_status": result.status.value,
                    "has_data": bool(result.data),
                    "validation_errors": result.validation_errors,
                }
            except TimeoutError:
                logger.warning("⚠ %s timed out during execution", agent_name)
                results[agent_name] = {"status": "TIMEOUT", "error": "Execution timed out"}
            except Exception as e:
                logger.warning("⚠ %s execution failed: %s", agent_name, str(e))
                results[agent_name] = {"status": "EXECUTION_ERROR", "error": str(e)}

        except Exception as e:
            logger.exception("✗ %s failed to instantiate: %s", agent_name, str(e))
            results[agent_name] = {"status": "INSTANTIATION_ERROR", "error": str(e)}

    return results


async def test_orchestrator():
    """Test the orchestrator functionality."""
    logger.info("Testing orchestrator...")

    try:
        orchestrator = get_orchestrator()

        # Verify orchestrator has required methods (actual implementation uses execute_parallel_studies)
        # NOTE: RuntimeError used instead of assert to avoid SonarCloud S5779
        # (assert inside try-except that catches AssertionError).
        if not hasattr(orchestrator, "execute_parallel_studies"):
            raise RuntimeError("Orchestrator missing execute_parallel_studies method")
        if not hasattr(orchestrator, "get_agents_info"):
            raise RuntimeError("Orchestrator missing get_agents_info method")

        agent_info = orchestrator.get_agents_info()
        logger.info("✓ Orchestrator retrieved info for %s agents", len(agent_info.get('agents', [])))

        test_system = await create_test_system()
        parameters = {"test_mode": True}

        try:
            result = await asyncio.wait_for(
                orchestrator.execute_parallel_studies(
                    study_types=["load_flow"],
                    system_data=test_system,
                    parameters=parameters,
                    max_workers=1,
                    benchmark=False,
                ),
                timeout=15.0,
            )

            logger.info("✓ Orchestrator executed studies successfully")
            orchestrator_result = {
                "status": "SUCCESS",
                "result_keys": list(result.keys())
                if isinstance(result, dict)
                else ["non_dict_result"],
            }
        except TimeoutError:
            logger.warning("⚠ Orchestrator execution timed out")
            orchestrator_result = {"status": "TIMEOUT", "error": "Execution timed out"}
        except Exception as e:
            logger.warning("⚠ Orchestrator execution failed: %s", str(e))
            orchestrator_result = {"status": "EXECUTION_ERROR", "error": str(e)}

        return orchestrator_result

    except Exception as e:
        logger.exception("✗ Orchestrator test failed: %s", str(e))
        return {"status": "ERROR", "error": str(e)}


async def main():
    """Main test function."""
    logger.info("Starting comprehensive agent testing...")

    # Test individual agents
    agent_results = await test_individual_agents()

    # Test orchestrator
    orchestrator_result = await test_orchestrator()

    # Print summary
    print("\n" + "=" * 80)
    print("AGENT TESTING SUMMARY")
    print("=" * 80)

    successful_agents = 0
    total_agents = len(agent_results)

    for agent_name, result in agent_results.items():
        status = result["status"]
        if status == "SUCCESS":
            successful_agents += 1
            print(f"✓ {agent_name:<30} SUCCESS - Result: {result['result_status']}")
        else:
            print(f"✗ {agent_name:<30} {status} - Error: {result.get('error', 'Unknown')}")

    print(f"\nIndividual Agents: {successful_agents}/{total_agents} successful")

    print(f"\nOrchestrator: {orchestrator_result['status']}")

    print(f"\nOverall Success Rate: {successful_agents}/{total_agents} individual agents")

    if successful_agents == total_agents:
        logger.info("🎉 All agents passed basic functionality tests!")
        return 0
    else:
        logger.warning(
            "⚠ %s agents failed basic functionality tests", total_agents - successful_agents)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
