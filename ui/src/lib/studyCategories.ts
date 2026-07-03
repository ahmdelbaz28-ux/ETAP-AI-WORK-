/**
 * Ahmed etap Platform — Study Categories & Parameter Definitions
 */

export interface StudyParam {
  name: string
  type: 'number' | 'text' | 'select'
  default: string | number
  label?: string
  description?: string
}

export interface StudyCategory {
  id: string
  name: string
  icon: string
  description: string
  standard?: string
  params: StudyParam[]
}

export const studyCategories: StudyCategory[] = [
  {
    id: 'load_flow',
    name: 'Load Flow Analysis',
    icon: '⚡',
    description: 'Newton-Raphson power flow solver with voltage regulation and power loss analysis.',
    standard: 'IEEE',
    params: [
      { name: 'method', type: 'select', default: 'newton-raphson', label: 'Solution Method' },
      { name: 'base_mva', type: 'number', default: 100, label: 'Base MVA' },
      { name: 'tolerance', type: 'number', default: 0.0001, label: 'Convergence Tolerance' },
      { name: 'max_iterations', type: 'number', default: 50, label: 'Max Iterations' },
    ],
  },
  {
    id: 'short_circuit',
    name: 'Short Circuit Analysis',
    icon: '⚠️',
    description: 'IEC 60909 compliant fault current analysis for all fault types.',
    standard: 'IEC 60909',
    params: [
      { name: 'fault_type', type: 'select', default: 'three_phase', label: 'Fault Type' },
      { name: 'fault_bus', type: 'number', default: 2, label: 'Fault Bus ID' },
      { name: 'standard', type: 'select', default: 'iec60909', label: 'Calculation Standard' },
    ],
  },
  {
    id: 'arc_flash',
    name: 'Arc Flash Analysis',
    icon: '🔥',
    description: 'IEEE 1584-2018 incident energy and PPE category calculation.',
    standard: 'IEEE 1584-2018',
    params: [
      { name: 'voltage_kv', type: 'number', default: 0.48, label: 'Voltage (kV)' },
      { name: 'bolted_fault_ka', type: 'number', default: 30, label: 'Bolted Fault Current (kA)' },
      { name: 'working_distance_mm', type: 'number', default: 610, label: 'Working Distance (mm)' },
      { name: 'gap_mm', type: 'number', default: 32, label: 'Electrode Gap (mm)' },
      { name: 'standard', type: 'select', default: 'ieee1584', label: 'Standard' },
    ],
  },
  {
    id: 'harmonic_analysis',
    name: 'Harmonic Analysis',
    icon: '📊',
    description: 'THD/TDD compliance analysis per IEEE 519-2022 standards.',
    standard: 'IEEE 519-2022',
    params: [
      { name: 'base_mva', type: 'number', default: 100, label: 'Base MVA' },
      { name: 'max_harmonic_order', type: 'number', default: 50, label: 'Max Harmonic Order' },
      { name: 'thd_limit_pct', type: 'number', default: 5, label: 'THD Limit (%)' },
    ],
  },
  {
    id: 'protection_coordination',
    name: 'Protection Coordination',
    icon: '🛡️',
    description: 'IEC 60255 relay curve coordination and selectivity analysis.',
    standard: 'IEC 60255',
    params: [
      { name: 'upstream_relay_tms', type: 'number', default: 0.1, label: 'Upstream TMS' },
      { name: 'downstream_relay_tms', type: 'number', default: 0.2, label: 'Downstream TMS' },
      { name: 'pickup_current', type: 'number', default: 1.0, label: 'Pickup Current (pu)' },  // NOSONAR — S7748: number literal trailing zero; cosmetic
    ],
  },
  {
    id: 'motor_starting',
    name: 'Motor Starting Analysis',
    icon: '⚙️',
    description: 'Motor starting voltage drop and torque analysis.',
    standard: 'IEEE',
    params: [
      { name: 'motor_hp', type: 'number', default: 500, label: 'Motor HP' },
      { name: 'starting_method', type: 'select', default: 'across_the_line', label: 'Starting Method' },
      { name: 'voltage_drop_limit_pct', type: 'number', default: 15, label: 'Voltage Drop Limit (%)' },
    ],
  },
  {
    id: 'optimal_power_flow',
    name: 'Optimal Power Flow',
    icon: '📈',
    description: 'AC/DC optimal power flow with economic dispatch.',
    params: [
      { name: 'objective', type: 'select', default: 'min_cost', label: 'Objective Function' },
      { name: 'base_mva', type: 'number', default: 100, label: 'Base MVA' },
      { name: 'max_iterations', type: 'number', default: 100, label: 'Max Iterations' },
    ],
  },
  {
    id: 'transient_stability',
    name: 'Transient Stability',
    icon: '🔄',
    description: 'Time-domain simulation of power system dynamic response.',
    params: [
      { name: 'simulation_time_s', type: 'number', default: 5, label: 'Simulation Time (s)' },
      { name: 'time_step_ms', type: 'number', default: 10, label: 'Time Step (ms)' },
      { name: 'fault_clearing_time_ms', type: 'number', default: 100, label: 'Fault Clearing Time (ms)' },
    ],
  },
]
