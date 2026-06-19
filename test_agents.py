#!/usr/bin/env python3
"""
Test script to verify all agents return valid results.

This script tests each agent in the AhmedETAP system to ensure they
are properly initialized and can execute basic operations.
"""

import asyncio
import sys
import os
from typing import Dict, Any, List
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import (
    ALL_AGENT_CLASSES,
    ChiefEngineeringOrchestrator,
    get_orchestrator,
    EngineeringTask,
    StudyType,
    AgentStatus
)
from core_model.system import System  # We'll create a minimal system for testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_test_system() -> System:
    """
    Create a minimal test system for agent testing.
    This creates a simple power system with minimal components to allow
    agents to perform basic initialization without failing due to missing data.
    """
    # Since we're testing agent creation and basic functionality rather than
    # full computations, we'll create a minimal system
    try:
        from core_model.system import System
        system = System(name="test_system")
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
        logger.info(f"Testing {agent_name}...")
        
        try:
            # Instantiate the agent
            agent = agent_class()
            
            # Verify the agent has required properties
            assert hasattr(agent, 'agent_name'), f"{agent_name} missing agent_name"
            assert hasattr(agent, 'status'), f"{agent_name} missing status"
            assert hasattr(agent, 'execute'), f"{agent_name} missing execute method"
            
            # Create a minimal test task
            task = EngineeringTask(
                task_id=f"test_{agent_name.lower()}",
                description=f"Test task for {agent_name}",
                study_types=[StudyType.LOAD_FLOW],  # Using LOAD_FLOW as default
                parameters={'system': test_system, 'test_mode': True}
            )
            
            # Try to execute the agent (with timeout to prevent hanging)
            try:
                result = await asyncio.wait_for(agent.execute(task), timeout=10.0)
                
                # Log the result status
                logger.info(f"✓ {agent_name} executed successfully - Status: {result.status.value}")
                
                results[agent_name] = {
                    'status': 'SUCCESS',
                    'result_status': result.status.value,
                    'has_data': bool(result.data),
                    'validation_errors': result.validation_errors
                }
            except asyncio.TimeoutError:
                logger.warning(f"⚠ {agent_name} timed out during execution")
                results[agent_name] = {
                    'status': 'TIMEOUT',
                    'error': 'Execution timed out'
                }
            except Exception as e:
                logger.warning(f"⚠ {agent_name} execution failed: {str(e)}")
                results[agent_name] = {
                    'status': 'EXECUTION_ERROR',
                    'error': str(e)
                }
                
        except Exception as e:
            logger.error(f"✗ {agent_name} failed to instantiate: {str(e)}")
            results[agent_name] = {
                'status': 'INSTANTIATION_ERROR',
                'error': str(e)
            }
    
    return results


async def test_orchestrator():
    """Test the orchestrator functionality."""
    logger.info("Testing orchestrator...")
    
    try:
        # Get orchestrator instance
        orchestrator = get_orchestrator()
        
        # Verify orchestrator has required methods
        assert hasattr(orchestrator, 'execute_studies'), "Orchestrator missing execute_studies method"
        assert hasattr(orchestrator, 'get_agents_info'), "Orchestrator missing get_agents_info method"
        
        # Test getting agent info
        agent_info = orchestrator.get_agents_info()
        logger.info(f"✓ Orchestrator retrieved info for {len(agent_info.get('agents', []))} agents")
        
        # Create a minimal test task for orchestrator
        test_system = await create_test_system()
        task_params = {
            'system': test_system,
            'test_mode': True
        }
        
        # Test executing a simple study through orchestrator
        try:
            result = await asyncio.wait_for(
                orchestrator.execute_studies(
                    studies=['load_flow'],
                    parameters=task_params,
                    task_id='test_orchestrator'
                ),
                timeout=15.0
            )
            
            logger.info("✓ Orchestrator executed studies successfully")
            orchestrator_result = {
                'status': 'SUCCESS',
                'result_keys': list(result.keys()) if isinstance(result, dict) else ['non_dict_result']
            }
        except asyncio.TimeoutError:
            logger.warning("⚠ Orchestrator execution timed out")
            orchestrator_result = {
                'status': 'TIMEOUT',
                'error': 'Execution timed out'
            }
        except Exception as e:
            logger.warning(f"⚠ Orchestrator execution failed: {str(e)}")
            orchestrator_result = {
                'status': 'EXECUTION_ERROR',
                'error': str(e)
            }
        
        return orchestrator_result
        
    except Exception as e:
        logger.error(f"✗ Orchestrator test failed: {str(e)}")
        return {
            'status': 'ERROR',
            'error': str(e)
        }


async def main():
    """Main test function."""
    logger.info("Starting comprehensive agent testing...")
    
    # Test individual agents
    agent_results = await test_individual_agents()
    
    # Test orchestrator
    orchestrator_result = await test_orchestrator()
    
    # Print summary
    print("\n" + "="*80)
    print("AGENT TESTING SUMMARY")
    print("="*80)
    
    successful_agents = 0
    total_agents = len(agent_results)
    
    for agent_name, result in agent_results.items():
        status = result['status']
        if status == 'SUCCESS':
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
        logger.warning(f"⚠ {total_agents - successful_agents} agents failed basic functionality tests")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)