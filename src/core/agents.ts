/**
 * Single source of truth for the agent registry.
 * Both the edge gateway (src/index.ts) and the Mastra backend
 * (src/mastra/agents) MUST reference this list — no duplication.
 */
export interface AgentMeta {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
}

export const AGENT_REGISTRY: Readonly<Record<string, AgentMeta>> = Object.freeze({
  'power-system-coordinator-agent': {
    id: 'power-system-coordinator-agent',
    name: 'Power System Coordinator Agent',
    description: 'Orchestrates multi-study power system engineering workflows.',
    capabilities: ['load_flow', 'short_circuit', 'protection', 'harmonics', 'arc_flash', 'motor_starting'],
  },
  'load-flow-agent': {
    id: 'load-flow-agent',
    name: 'Load Flow Analysis Agent',
    description: 'Performs AC load flow analysis using Newton-Raphson.',
    capabilities: ['load_flow', 'voltage_profile', 'power_balance'],
  },
  'short-circuit-agent': {
    id: 'short-circuit-agent',
    name: 'Short Circuit Analysis Agent',
    description: 'Calculates fault currents per IEC 60909.',
    capabilities: ['short_circuit', 'fault_analysis', 'iec_60909'],
  },
  'arcflash-agent': {
    id: 'arcflash-agent',
    name: 'Arc Flash Analysis Agent',
    description: 'Computes incident energy per IEEE 1584-2018.',
    capabilities: ['arc_flash', 'incident_energy', 'ppe_level'],
  },
  'etap-engineer-agent': {
    id: 'etap-engineer-agent',
    name: 'ETAP Engineering Agent',
    description: 'Interfaces with ETAP for project automation.',
    capabilities: ['etap_automation', 'project_management', 'study_execution'],
  },
  'protection-agent': {
    id: 'protection-agent',
    name: 'Protection Coordination Agent',
    description: 'Validates relay coordination per IEC 60255.',
    capabilities: ['protection_coordination', 'relay_settings', 'tcc_curves'],
  },
  'motorstarting-agent': {
    id: 'motorstarting-agent',
    name: 'Motor Starting Agent',
    description: 'Analyzes motor starting voltage dip and acceleration.',
    capabilities: ['motor_starting', 'voltage_dip', 'acceleration_time'],
  },
  'goal-planner-agent': {
    id: 'goal-planner-agent',
    name: 'Goal Planner Agent',
    description: 'Breaks down engineering goals into actionable tasks.',
    capabilities: ['task_planning', 'priority_estimation', 'workflow_design'],
  },
  'weather-agent': {
    id: 'weather-agent',
    name: 'Weather Agent',
    description: 'Retrieves weather data for engineering planning.',
    capabilities: ['weather_forecast', 'temperature', 'wind_speed'],
  },
});

export function getAgent(id: string): AgentMeta | undefined {
  return AGENT_REGISTRY[id];
}

export function listAgentIds(): string[] {
  return Object.keys(AGENT_REGISTRY);
}
