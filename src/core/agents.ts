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
  promptHandle?: string;
}

const CORE_COORDINATOR_CAPABILITIES = [
  'load_flow',
  'short_circuit',
  'protection_coordination',
  'protection',
  'harmonic_analysis',
  'harmonics',
  'arc_flash',
  'motor_starting',
];

const EXPERT_MODULE_CAPABILITIES = [
  'etap_consultation',
  'load_flow',
  'short_circuit',
  'arc_flash',
  'protection_coordination',
  'adms',
  'flisr',
  'vvo',
  'derms',
  'renewables',
  'pv',
  'wind',
  'bess',
  'cable_sizing',
  'transformer_sizing',
  'ieee_1584',
  'ieee_80',
  'ieee_519',
  'iec_60909',
  'iec_61850',
  'nec',
  'nfpa_70e',
  'format_a_complete',
  'format_b_incomplete',
  'format_c_wrong',
  'format_d_adms',
];

export const AGENT_REGISTRY: Readonly<Record<string, AgentMeta>> = Object.freeze({
  'power-system-coordinator-agent': {
    id: 'power-system-coordinator-agent',
    name: 'Power System Coordinator Agent',
    description: 'Orchestrates multi-study power system engineering workflows.',
    capabilities: [...CORE_COORDINATOR_CAPABILITIES],
    promptHandle: 'power_system_coordinator_agent',
  },
  'load-flow-agent': {
    id: 'load-flow-agent',
    name: 'Load Flow Analysis Agent',
    description: 'Performs AC load flow analysis using Newton-Raphson.',
    capabilities: ['load_flow', 'voltage_profile', 'power_balance'],
    promptHandle: 'load_flow_agent',
  },
  'short-circuit-agent': {
    id: 'short-circuit-agent',
    name: 'Short Circuit Analysis Agent',
    description: 'Calculates fault currents per IEC 60909.',
    capabilities: ['short_circuit', 'fault_analysis', 'iec_60909'],
    promptHandle: 'short_circuit_agent',
  },
  'arcflash-agent': {
    id: 'arcflash-agent',
    name: 'Arc Flash Analysis Agent',
    description: 'Computes incident energy per IEEE 1584-2018.',
    capabilities: ['arc_flash', 'incident_energy', 'ppe_level'],
    promptHandle: 'arcflash_agent',
  },
  'etap-engineer-agent': {
    id: 'etap-engineer-agent',
    name: 'ETAP Engineering Agent',
    description: 'Interfaces with ETAP for project automation.',
    capabilities: ['etap_automation', 'project_management', 'study_execution'],
    promptHandle: 'etap_engineer_agent',
  },
  'etap-expert-agent': {
    id: 'etap-expert-agent',
    name: 'ETAP Expert Skill Agent',
    description:
      'ETAP Expert skill — 6-step workflow (PARSE → SEARCH → VALIDATE → SIMULATE → FORMAT → QA) with Format A/B/C/D responses. Knowledge base: skills/etap-expert.md (4,400+ lines). Covers ALL ETAP modules: Load Flow, Short Circuit, Arc Flash, Protection, ADMS, GIS, Renewables, Transients, Industrial.',
    capabilities: [...EXPERT_MODULE_CAPABILITIES],
    promptHandle: 'etap_expert_agent',
  },
  'protection-agent': {
    id: 'protection-agent',
    name: 'Protection Coordination Agent',
    description: 'Validates relay coordination per IEC 60255.',
    capabilities: ['protection_coordination', 'relay_settings', 'tcc_curves'],
    promptHandle: 'protection_agent',
  },
  'motorstarting-agent': {
    id: 'motorstarting-agent',
    name: 'Motor Starting Agent',
    description: 'Analyzes motor starting voltage dip and acceleration.',
    capabilities: ['motor_starting', 'voltage_dip', 'acceleration_time'],
    promptHandle: 'motor_starting_agent',
  },
  'goal-planner-agent': {
    id: 'goal-planner-agent',
    name: 'Goal Planner Agent',
    description: 'Breaks down engineering goals into actionable tasks.',
    capabilities: ['task_planning', 'priority_estimation', 'workflow_design'],
    promptHandle: 'goal_planner_agent',
  },
  'weather-agent': {
    id: 'weather-agent',
    name: 'Weather Agent',
    description: 'Retrieves weather data for engineering planning.',
    capabilities: ['weather_forecast', 'temperature', 'wind_speed'],
    promptHandle: 'weather_agent',
  },
  'code-guard-agent': {
    id: 'code-guard-agent',
    name: 'Code Guard Agent',
    description:
      'Reviews AI-generated code against 14 AI failure modes, 23 clean-code rules, 9 testing rules, and 10 documentation accuracy rules. Adapted from guard-skills (github.com/amElnagdy/guard-skills).',
    capabilities: [
      'code_review',
      'ai_failure_mode_detection',
      'test_quality',
      'docs_accuracy',
      'clean_code',
    ],
    promptHandle: 'code_guard_agent',
  },
  'harmonic-agent': {
    id: 'harmonic-agent',
    name: 'Harmonic Analysis Agent',
    description: 'Performs IEEE 519 harmonic distortion and resonance analysis.',
    capabilities: ['harmonic_analysis', 'harmonics', 'ieee_519', 'thd'],
    promptHandle: 'harmonic_agent',
  },
  'optimal-power-flow-agent': {
    id: 'optimal-power-flow-agent',
    name: 'Optimal Power Flow Agent',
    description: 'Performs optimal power flow and dispatch optimization.',
    capabilities: ['optimal_power_flow', 'opf', 'dispatch_optimization'],
    promptHandle: 'opf_agent',
  },
  'transient-stability-agent': {
    id: 'transient-stability-agent',
    name: 'Transient Stability Agent',
    description: 'Performs dynamic transient stability analysis per IEEE 399.',
    capabilities: ['transient_stability', 'critical_clearing_time', 'rotor_angle'],
    promptHandle: 'stability_agent',
  },
  'cable-sizing-agent': {
    id: 'cable-sizing-agent',
    name: 'Cable Sizing Agent',
    description: 'Calculates cable ampacity and voltage drop per IEC 60364.',
    capabilities: ['cable_sizing', 'ampacity', 'voltage_drop', 'iec_60364'],
    promptHandle: 'cable_sizing_agent',
  },
  'earth-grid-agent': {
    id: 'earth-grid-agent',
    name: 'Earth Grid Agent',
    description: 'Calculates substation ground grid mesh and step voltages per IEEE 80.',
    capabilities: ['earth_grid', 'mesh_voltage', 'step_voltage', 'ieee_80'],
    promptHandle: 'earth_grid_agent',
  },
  'renewable-agent': {
    id: 'renewable-agent',
    name: 'Renewable Energy Agent',
    description: 'Performs solar PV and wind interconnection analysis per IEEE 1547.',
    capabilities: ['renewable_integration', 'solar_pv', 'wind', 'ieee_1547'],
    promptHandle: 'renewable_agent',
  },
  'battery-storage-agent': {
    id: 'battery-storage-agent',
    name: 'Battery Storage Agent',
    description: 'Sizes BESS and optimizes dispatch per IEC 62933.',
    capabilities: ['battery_storage', 'bess', 'soc', 'iec_62933'],
    promptHandle: 'battery_storage_agent',
  },
  'scada-agent': {
    id: 'scada-agent',
    name: 'SCADA Integration Agent',
    description: 'Maps real-time telemetry and state estimation per IEC 61850.',
    capabilities: ['scada', 'iec_61850', 'telemetry', 'state_estimation'],
    promptHandle: 'scada_agent',
  },
  'digital-twin-agent': {
    id: 'digital-twin-agent',
    name: 'Digital Twin Agent',
    description: 'Maintains real-time synchronized digital twin of the power grid.',
    capabilities: ['digital_twin', 'synchronization', 'state_validation'],
    promptHandle: 'digital_twin_agent',
  },
  'generative-design-agent': {
    id: 'generative-design-agent',
    name: 'Generative Design Agent',
    description: 'Synthesizes substation SLD topologies and equipment parameters.',
    capabilities: ['generative_design', 'sld_synthesis', 'substation_design'],
    promptHandle: 'design_agent',
  },
  'qgis-agent': {
    id: 'qgis-agent',
    name: 'GIS & Geospatial Agent',
    description: 'Integrates geospatial electrical network layers across ArcGIS and QGIS.',
    capabilities: ['qgis', 'gis', 'geospatial', 'network_mapping'],
    promptHandle: 'qgis_agent',
  },
  'validation-agent': {
    id: 'validation-agent',
    name: 'Engineering Validation Agent',
    description: 'Cross-checks multi-study calculation results against first principles.',
    capabilities: ['validation', 'first_principles', 'cross_validation'],
    promptHandle: 'validation_agent',
  },
  'report-agent': {
    id: 'report-agent',
    name: 'Engineering Report Agent',
    description: 'Compiles certified PDF, DOCX, and XLSX engineering study reports.',
    capabilities: ['report', 'pdf_generation', 'documentation'],
    promptHandle: 'report_agent',
  },
  'predictive-agent': {
    id: 'predictive-agent',
    name: 'Predictive Maintenance Agent',
    description: 'Evaluates equipment degradation trends and failure probability.',
    capabilities: ['predictive', 'health_index', 'maintenance_scheduling'],
    promptHandle: 'predictive_agent',
  },
  'anomaly-agent': {
    id: 'anomaly-agent',
    name: 'Anomaly Detection Agent',
    description: 'Identifies grid telemetry anomalies and transient disturbances.',
    capabilities: ['anomaly', 'disturbance_detection', 'event_classification'],
    promptHandle: 'anomaly_agent',
  },
});

export function getAgent(id: string): AgentMeta | undefined {
  return AGENT_REGISTRY[id];
}

export function listAgentIds(): string[] {
  return Object.keys(AGENT_REGISTRY);
}

export function getAgentPromptHandle(id: string): string {
  const agent = getAgent(id);
  return agent?.promptHandle || id.replace(/-/g, '_');
}
