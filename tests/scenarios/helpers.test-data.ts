export interface BusData {
  id: string;
  nominal_kv: number;
  voltage_pu: number;
  angle_deg: number;
  load_mw: number;
  load_mvar: number;
  gen_mw: number;
  gen_mvar: number;
}

export interface BranchData {
  from_bus: string;
  to_bus: string;
  r_pu: number;
  x_pu: number;
  b_pu: number;
  rating_mva: number;
}

export interface PowerSystemData {
  name: string;
  base_mva: number;
  base_kv: number;
  frequency_hz: number;
  buses: BusData[];
  branches: BranchData[];
}

export function generateSimpleIndustrialSystem(): PowerSystemData {
  return {
    name: 'Industrial Plant - 13.8 kV',
    base_mva: 100,
    base_kv: 13.8,
    frequency_hz: 60,
    buses: [
      {
        id: 'UTILITY',
        nominal_kv: 115,
        voltage_pu: 1.02,
        angle_deg: 0,
        load_mw: 0,
        load_mvar: 0,
        gen_mw: 0,
        gen_mvar: 0,
      },
      {
        id: 'MAIN-SWGR',
        nominal_kv: 13.8,
        voltage_pu: 1.01,
        angle_deg: -1.5,
        load_mw: 5,
        load_mvar: 2,
        gen_mw: 0,
        gen_mvar: 0,
      },
      {
        id: 'MCC-1',
        nominal_kv: 0.48,
        voltage_pu: 0.98,
        angle_deg: -3.2,
        load_mw: 1.2,
        load_mvar: 0.5,
        gen_mw: 0,
        gen_mvar: 0,
      },
      {
        id: 'MCC-2',
        nominal_kv: 0.48,
        voltage_pu: 0.97,
        angle_deg: -3.5,
        load_mw: 0.8,
        load_mvar: 0.3,
        gen_mw: 0,
        gen_mvar: 0,
      },
      {
        id: 'PUMP-MOTOR',
        nominal_kv: 4.16,
        voltage_pu: 0.99,
        angle_deg: -2.8,
        load_mw: 0.25,
        load_mvar: 0.12,
        gen_mw: 0,
        gen_mvar: 0,
      },
    ],
    branches: [
      {
        from_bus: 'UTILITY',
        to_bus: 'MAIN-SWGR',
        r_pu: 0.01,
        x_pu: 0.1,
        b_pu: 0.02,
        rating_mva: 50,
      }, // NOSONAR — S7748: number literal trailing zero; cosmetic
      {
        from_bus: 'MAIN-SWGR',
        to_bus: 'MCC-1',
        r_pu: 0.02,
        x_pu: 0.08,
        b_pu: 0.01,
        rating_mva: 10,
      },
      {
        from_bus: 'MAIN-SWGR',
        to_bus: 'MCC-2',
        r_pu: 0.02,
        x_pu: 0.08,
        b_pu: 0.01,
        rating_mva: 10,
      },
      {
        from_bus: 'MAIN-SWGR',
        to_bus: 'PUMP-MOTOR',
        r_pu: 0.015,
        x_pu: 0.06,
        b_pu: 0.005,
        rating_mva: 5,
      },
    ],
  };
}

export function generateSimpleHarmonicSource(): Record<string, unknown>[] {
  return [
    { bus_id: 'MCC-1', harmonic_order: 5, magnitude_percent: 3.0, phase_deg: 0 }, // NOSONAR — S7748: number literal trailing zero; cosmetic
    { bus_id: 'MCC-1', harmonic_order: 7, magnitude_percent: 2.5, phase_deg: 15 },
    { bus_id: 'MCC-1', harmonic_order: 11, magnitude_percent: 1.2, phase_deg: 30 },
    { bus_id: 'MCC-2', harmonic_order: 5, magnitude_percent: 2.0, phase_deg: 0 }, // NOSONAR — S7748: number literal trailing zero; cosmetic
    { bus_id: 'MCC-2', harmonic_order: 7, magnitude_percent: 1.8, phase_deg: 20 },
  ];
}

export function generateRelayCoordinationData(): Record<string, unknown>[] {
  return [
    {
      id: 'RELAY-01',
      type: 'overcurrent',
      curve: 'IEC_VI',
      pickup_a: 100,
      time_dial: 0.15,
      ct_ratio: 200,
    },
    {
      id: 'RELAY-02',
      type: 'overcurrent',
      curve: 'IEC_VI',
      pickup_a: 80,
      time_dial: 0.1,
      ct_ratio: 150,
    }, // NOSONAR — S7748: number literal trailing zero; cosmetic
    {
      id: 'RELAY-03',
      type: 'overcurrent',
      curve: 'IEC_NI',
      pickup_a: 50,
      time_dial: 0.08,
      ct_ratio: 100,
    },
  ];
}

export function generateArcFlashStudyParams(): Record<string, unknown> {
  return {
    voltage_kv: 0.48,
    bolted_fault_current_ka: 25.0, // NOSONAR — S7748: number literal trailing zero; cosmetic
    arc_duration_sec: 0.3,
    working_distance_mm: 457,
    enclosure_type: 'box',
    electrode_config: 'VCB',
  };
}

export function generateStudyParameters(): Record<string, Record<string, unknown>> {
  return {
    loadFlow: {
      max_iterations: 100,
      tolerance: 1e-6,
      method: 'Newton-Raphson',
    },
    shortCircuit: {
      base_kv: 13.8,
      fault_buses: ['MAIN-SWGR', 'MCC-1', 'MCC-2', 'PUMP-MOTOR'],
    },
    harmonic: {
      voltage_kv: 13.8,
      fundamental_freq: 60,
      max_harmonic_order: 50,
    },
    motorStarting: {
      motor_bus: 'PUMP-MOTOR',
      starting_method: 'across_the_line',
      load_torque_percent: 80,
    },
    arcFlash: generateArcFlashStudyParams(),
  };
}
