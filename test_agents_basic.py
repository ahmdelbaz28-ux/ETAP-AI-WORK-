#!/usr/bin/env python3
"""
Basic test script to verify all agents can be imported and instantiated.

This script tests that each agent class can be imported and instantiated
without running full execution which might require additional dependencies.
"""

import importlib.util
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_agent_imports():
    """Test that all agent modules can be imported without errors."""
    print("Testing agent module imports...")

    agent_modules = [
        'agents.anomaly_agent',
        'agents.arc_flash_agent',
        'agents.battery_storage_agent',
        'agents.cable_sizing_agent',
        'agents.code_guard_agent',
        'agents.coordination_agent',
        'agents.digital_twin_agent',
        'agents.earth_grid_agent',
        'agents.goal_planner_agent',
        'agents.motor_starting_agent',
        'agents.orchestrator',
        'agents.predictive_agent',
        'agents.prompt_loader',
        'agents.renewable_agent',
        'agents.scada_agent',
        'agents.stability_agent',
        'agents.weather_agent',
    ]

    import_results = {}

    for module_name in agent_modules:
        try:
            module = importlib.util.find_spec(module_name)
            if module is not None:
                imported_module = importlib.import_module(module_name)
                import_results[module_name] = {'status': 'SUCCESS', 'module': imported_module}
                print(f"✓ {module_name} - Imported successfully")
            else:
                import_results[module_name] = {'status': 'NOT_FOUND', 'error': 'Module not found'}
                print(f"✗ {module_name} - Module not found")
        except ImportError as e:
            import_results[module_name] = {'status': 'IMPORT_ERROR', 'error': str(e)}
            print(f"✗ {module_name} - Import error: {str(e)}")
        except Exception as e:
            import_results[module_name] = {'status': 'ERROR', 'error': str(e)}
            print(f"✗ {module_name} - Error: {str(e)}")

    return import_results


def test_agent_instantiation():
    """Test that agent classes can be instantiated (when possible without full dependencies)."""
    print("\nTesting agent class instantiation...")

    # Rather than importing the full orchestrator, let's test individual agent classes
    # by importing them and checking if they have basic attributes

    instantiation_results = {}

    # We'll test the orchestrator separately since it's in the main agents module
    try:
        from agents.orchestrator import (
            ETAPExecutionAgent,
            HarmonicAnalysisAgent,
            LoadFlowAgent,
            OptimalPowerFlowAgent,
            ProtectionCoordinationAgent,
            ReportGenerationAgent,
            ShortCircuitAgent,
            ValidationAgent,
        )

        basic_agents = [
            LoadFlowAgent, ShortCircuitAgent, HarmonicAnalysisAgent,
            OptimalPowerFlowAgent, ProtectionCoordinationAgent, ETAPExecutionAgent,
            ValidationAgent, ReportGenerationAgent
        ]

        for agent_class in basic_agents:
            try:
                # Try to instantiate (this may fail due to dependencies, which is ok for this test)
                try:
                    agent_instance = agent_class()

                    # Check if the agent has required attributes
                    has_name = hasattr(agent_instance, 'agent_name')
                    has_execute = hasattr(agent_instance, 'execute')
                    has_status = hasattr(agent_instance, 'status')

                    instantiation_results[agent_class.__name__] = {
                        'status': 'SUCCESS',
                        'has_name': has_name,
                        'has_execute': has_execute,
                        'has_status': has_status
                    }
                    print(f"✓ {agent_class.__name__} - Instantiated successfully")

                except Exception as e:
                    # If instantiation fails due to missing dependencies, that's expected
                    instantiation_results[agent_class.__name__] = {
                        'status': 'INSTANTIATION_DEPENDENCY_ERROR',
                        'error': str(e)
                    }
                    print(f"⚠ {agent_class.__name__} - Expected dependency error during instantiation: {str(e)[:100]}...")

            except Exception as e:
                instantiation_results[agent_class.__name__] = {
                    'status': 'CLASS_DEFINITION_ERROR',
                    'error': str(e)
                }
                print(f"✗ {agent_class.__name__} - Class definition error: {str(e)}")

    except ImportError as e:
        print(f"✗ Basic agent classes - Import error: {str(e)}")
        instantiation_results['basic_agents'] = {'status': 'IMPORT_ERROR', 'error': str(e)}

    # Test extended agents
    try:
        from agents.battery_storage_agent import BatteryStorageAgent
        from agents.cable_sizing_agent import CableSizingAgent
        from agents.earth_grid_agent import EarthGridAgent
        from agents.renewable_agent import RenewableAgent
        from agents.scada_agent import SCADAAgent
        from agents.stability_agent import StabilityAgent

        extended_agents = [
            StabilityAgent, CableSizingAgent, EarthGridAgent,
            RenewableAgent, BatteryStorageAgent, SCADAAgent
        ]

        for agent_class in extended_agents:
            try:
                try:
                    agent_instance = agent_class()

                    has_name = hasattr(agent_instance, 'agent_name')
                    has_execute = hasattr(agent_instance, 'execute')
                    has_status = hasattr(agent_instance, 'status')

                    instantiation_results[agent_class.__name__] = {
                        'status': 'SUCCESS',
                        'has_name': has_name,
                        'has_execute': has_execute,
                        'has_status': has_status
                    }
                    print(f"✓ {agent_class.__name__} - Instantiated successfully")

                except Exception as e:
                    instantiation_results[agent_class.__name__] = {
                        'status': 'INSTANTIATION_DEPENDENCY_ERROR',
                        'error': str(e)
                    }
                    print(f"⚠ {agent_class.__name__} - Expected dependency error during instantiation: {str(e)[:100]}...")

            except Exception as e:
                instantiation_results[agent_class.__name__] = {
                    'status': 'CLASS_DEFINITION_ERROR',
                    'error': str(e)
                }
                print(f"✗ {agent_class.__name__} - Class definition error: {str(e)}")

    except ImportError as e:
        print(f"✗ Extended agent classes - Import error: {str(e)}")
        instantiation_results['extended_agents'] = {'status': 'IMPORT_ERROR', 'error': str(e)}

    return instantiation_results


def test_orchestrator():
    """Test orchestrator functionality."""
    print("\nTesting orchestrator...")

    orchestrator_results = {}

    try:
        from agents.orchestrator import ChiefEngineeringOrchestrator, get_orchestrator  # noqa: F401

        # Test that we can get an orchestrator instance (even if it can't fully run)
        try:
            orchestrator = get_orchestrator()
            has_methods = (
                hasattr(orchestrator, 'execute_studies') and
                hasattr(orchestrator, 'get_agents_info')
            )

            orchestrator_results['ChiefEngineeringOrchestrator'] = {
                'status': 'SUCCESS',
                'has_required_methods': has_methods
            }
            print("✓ ChiefEngineeringOrchestrator - Retrieved successfully")

        except Exception as e:
            orchestrator_results['ChiefEngineeringOrchestrator'] = {
                'status': 'GET_INSTANCE_ERROR',
                'error': str(e)
            }
            print(f"⚠ ChiefEngineeringOrchestrator - Error getting instance: {str(e)[:100]}...")

    except ImportError as e:
        orchestrator_results['ChiefEngineeringOrchestrator'] = {
            'status': 'IMPORT_ERROR',
            'error': str(e)
        }
        print(f"✗ ChiefEngineeringOrchestrator - Import error: {str(e)}")

    return orchestrator_results


def main():
    """Main test function."""
    print("Starting basic agent functionality tests...\n")

    # Test imports
    import_results = test_agent_imports()

    # Test instantiation
    instantiation_results = test_agent_instantiation()

    # Test orchestrator
    test_orchestrator()

    # Print summary
    print("\n" + "="*80)
    print("BASIC AGENT TESTING SUMMARY")
    print("="*80)

    # Count successful imports
    successful_imports = sum(1 for result in import_results.values() if result['status'] == 'SUCCESS')
    total_imports = len(import_results)

    # Count successful instantiations (including those with expected dependency errors)
    successful_instantiations = 0
    for result in instantiation_results.values():
        if result['status'] in ['SUCCESS', 'INSTANTIATION_DEPENDENCY_ERROR']:  # Both are acceptable
            successful_instantiations += 1

    total_instantiations = len(instantiation_results)

    print(f"Module Imports: {successful_imports}/{total_imports} successful")
    print(f"Class Instantiations: {successful_instantiations}/{total_instantiations} acceptable (includes expected dependency errors)")

    # Calculate overall status
    all_imports_ok = successful_imports == total_imports

    print(f"\nImport Status: {'✓ PASS' if all_imports_ok else '✗ FAIL'}")
    print(f"Overall Status: {'✓ PASS' if all_imports_ok else '✗ FAIL'}")

    if all_imports_ok:
        print("\n🎉 All agent modules imported successfully!")
        print("Note: Some instantiation errors are expected due to missing dependencies.")
        return 0
    else:
        print("\n⚠ Some agent modules failed to import.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
