export type StudyTypeStr =
  | 'LOAD_FLOW'
  | 'SHORT_CIRCUIT'
  | 'HARMONIC_ANALYSIS'
  | 'MOTOR_STARTING'
  | 'PROTECTION_COORDINATION'
  | 'ARC_FLASH';

export interface StudyResult {
  success: boolean;
  data: Record<string, unknown>;
  warnings: string[];
  errors: string[];
}

export interface ProjectInfo {
  path: string;
  isValid: boolean;
  studyTypes: StudyTypeStr[];
  lastModified: string;
}

export type FailureMode = 'none' | 'connection' | 'execution' | 'validation';

export class MockEtapProvider {
  private connectionState: 'disconnected' | 'connecting' | 'connected' = 'disconnected';
  private openProjects: Map<string, ProjectInfo> = new Map();
  private executionLog: Array<{ action: string; timestamp: number; params: unknown }> = [];
  private failureMode: FailureMode = 'none';

  setFailureMode(mode: FailureMode): void {
    this.failureMode = mode;
  }

  async connect(): Promise<void> {
    this.logAction('connect');
    if (this.failureMode === 'connection') {
      throw new Error('ETAP connection failed: ETAP application not found or license unavailable');
    }
    this.connectionState = 'connected';
  }

  async disconnect(): Promise<void> {
    this.logAction('disconnect');
    this.connectionState = 'disconnected';
    this.openProjects.clear();
  }

  isConnected(): boolean {
    return this.connectionState === 'connected';
  }

  async openProject(projectPath: string): Promise<ProjectInfo> {
    this.logAction('openProject', { projectPath });

    if (!this.isConnected()) {
      throw new Error('Not connected to ETAP');
    }

    if (this.failureMode === 'validation') {
      throw new Error(`Project not found: ${projectPath}`);
    }

    if (!projectPath.endsWith('.etap')) {
      throw new Error(`Invalid project file: ${projectPath}. Expected .etap extension`);
    }

    const projectInfo: ProjectInfo = {
      path: projectPath,
      isValid: true,
      studyTypes: [
        'LOAD_FLOW',
        'SHORT_CIRCUIT',
        'HARMONIC_ANALYSIS',
        'MOTOR_STARTING',
        'PROTECTION_COORDINATION',
        'ARC_FLASH',
      ],
      lastModified: new Date().toISOString(),
    };

    this.openProjects.set(projectPath, projectInfo);
    return projectInfo;
  }

  async executeStudy(
    projectPath: string,
    studyType: StudyTypeStr,
    parameters?: Record<string, unknown>,
  ): Promise<StudyResult> {
    this.logAction('executeStudy', { projectPath, studyType, parameters });

    if (this.failureMode === 'execution') {
      return {
        success: false,
        data: {},
        warnings: [],
        errors: [`Study execution failed: ${studyType} did not converge`],
      };
    }

    const project = this.openProjects.get(projectPath);
    if (!project) {
      throw new Error(`Project not open: ${projectPath}`);
    }

    return this.generateMockResult(studyType, parameters);
  }

  async extractResults(
    projectPath: string,
    studyType: StudyTypeStr,
  ): Promise<Record<string, unknown>> {
    this.logAction('extractResults', { projectPath, studyType });

    if (this.failureMode === 'validation') {
      return { error: 'Results extraction failed: study not completed' };
    }

    const project = this.openProjects.get(projectPath);
    if (!project) {
      throw new Error(`Project not open: ${projectPath}`);
    }

    return this.generateMockExtractedResults(studyType);
  }

  async closeProject(projectPath: string): Promise<void> {
    this.logAction('closeProject', { projectPath });
    this.openProjects.delete(projectPath);
  }

  getExecutionLog(): Array<{ action: string; timestamp: number; params: unknown }> {
    return [...this.executionLog];
  }

  clearExecutionLog(): void {
    this.executionLog = [];
  }

  private logAction(action: string, params?: unknown): void {
    this.executionLog.push({ action, timestamp: Date.now(), params });
  }

  private generateMockResult(
    studyType: StudyTypeStr,
    _parameters?: Record<string, unknown>,
  ): StudyResult {
    const baseResults: Record<StudyTypeStr, StudyResult> = {
      LOAD_FLOW: {
        success: true,
        data: {
          converged: true,
          iterations: 4,
          buses: {
            BUS001: {
              voltage_magnitude_pu: 1.02,
              voltage_angle_deg: -2.1,
              active_power_mw: 50.0,
              reactive_power_mvar: 15.0,
            }, // NOSONAR — S7748: number literal trailing zero; cosmetic
            BUS002: {
              voltage_magnitude_pu: 0.98,
              voltage_angle_deg: -3.5,
              active_power_mw: -30.0,
              reactive_power_mvar: -10.0,
            }, // NOSONAR — S7748: number literal trailing zero; cosmetic
            BUS003: {
              voltage_magnitude_pu: 1.01,
              voltage_angle_deg: -1.8,
              active_power_mw: 20.0,
              reactive_power_mvar: 5.0,
            }, // NOSONAR — S7748: number literal trailing zero; cosmetic
          },
          total_generation_mw: 70.0,
          total_load_mw: 68.5,
          total_losses_mw: 1.5,
          method: 'Newton-Raphson', // NOSONAR — S7748: number literal trailing zero; cosmetic
        },
        warnings: ['Bus BUS002 voltage at 0.98 pu - within acceptable range'],
        errors: [],
      },
      SHORT_CIRCUIT: {
        success: true,
        data: {
          standard: 'IEC 60909-0:2016',
          base_mva: 100,
          base_kv: 13.8,
          faults: {
            BUS001: {
              three_phase: { fault_current_ka: 15.2, r1_x1_ratio: 0.15 },
              line_to_ground: { fault_current_ka: 12.8, r0_x0_ratio: 0.2 },
            }, // NOSONAR — S7748: number literal trailing zero; cosmetic
            BUS002: {
              three_phase: { fault_current_ka: 8.5, r1_x1_ratio: 0.12 },
              line_to_ground: { fault_current_ka: 7.1, r0_x0_ratio: 0.18 },
            },
          },
        },
        warnings: [],
        errors: [],
      },
      HARMONIC_ANALYSIS: {
        success: true,
        data: {
          standard: 'IEEE 519-2022',
          thd_voltage_percent: 3.2,
          tdd_current_percent: 5.1,
          resonance_detected: false,
          dominant_harmonics: { h5: 2.1, h7: 1.8, h11: 0.9 },
          compliance_status: 'compliant',
          violations: [],
        },
        warnings: ['THD within IEEE 519 limits for general systems'],
        errors: [],
      },
      MOTOR_STARTING: {
        success: true,
        data: {
          motor_name: 'PUMP-250kW',
          rated_power_kw: 250,
          starting_method: 'VSD',
          starting_current_pu: 3.5,
          voltage_dip_percent: 4.2,
          acceleration_time_sec: 6.5,
          thermal_limit_met: true,
        },
        warnings: [],
        errors: [],
      },
      PROTECTION_COORDINATION: {
        success: true,
        data: {
          all_coordinated: true,
          relay_count: 4,
          standard: 'IEC 60255',
          coordination_pairs: [
            { upstream: 'RELAY-01', downstream: 'RELAY-02', margin_sec: 0.35, coordinated: true },
            { upstream: 'RELAY-02', downstream: 'RELAY-03', margin_sec: 0.28, coordinated: true },
            { upstream: 'RELAY-03', downstream: 'RELAY-04', margin_sec: 0.32, coordinated: true },
          ],
        },
        warnings: [],
        errors: [],
      },
      ARC_FLASH: {
        success: true,
        data: {
          standard: 'IEEE 1584-2018',
          bus_name: 'SWBD-400V',
          voltage_kv: 0.4,
          incident_energy_cal_per_cm2: 8.2,
          arc_flash_boundary_mm: 1524,
          ppe_level: '2',
          arc_current_ka: 12.5,
          enclosure_type: 'box',
        },
        warnings: ['PPE Level 2 required for this equipment'],
        errors: [],
      },
    };
    return (
      baseResults[studyType] || {
        success: false,
        data: {},
        warnings: [],
        errors: [`Unknown study type: ${studyType}`],
      }
    );
  }

  private generateMockExtractedResults(studyType: StudyTypeStr): Record<string, unknown> {
    const extracted: Record<StudyTypeStr, Record<string, unknown>> = {
      LOAD_FLOW: {
        summary: 'Load flow converged in 4 iterations',
        voltage_profile: 'All buses within 0.95-1.05 pu range',
        critical_buses: ['BUS002 (0.98 pu)'],
        overloaded_equipment: [],
      },
      SHORT_CIRCUIT: {
        summary: 'Fault analysis completed per IEC 60909',
        max_fault_current_ka: 15.2,
        location: 'BUS001',
        equipment_rating_adequate: true,
      },
      HARMONIC_ANALYSIS: {
        summary: 'Harmonic analysis completed per IEEE 519',
        compliance: 'compliant',
        thd_voltage_percent: 3.2,
        filter_required: false,
      },
      MOTOR_STARTING: {
        summary: 'Motor starting study completed',
        voltage_dip_percent: 4.2,
        starting_time_sec: 6.5,
        successful_start: true,
      },
      PROTECTION_COORDINATION: {
        summary: 'Protection coordination verified',
        all_coordinated: true,
        recommended_settings: 'Current settings adequate',
      },
      ARC_FLASH: {
        summary: 'Arc flash study completed per IEEE 1584-2018',
        max_incident_energy_cal_per_cm2: 8.2,
        ppe_level: '2',
        label_required: true,
      },
    };
    return extracted[studyType] || { error: `No extracted results for ${studyType}` };
  }

  static createStandardProvider(): MockEtapProvider {
    return new MockEtapProvider();
  }
}

export function createMockEtapScenario(): { provider: MockEtapProvider; cleanup: () => void } {
  const provider = new MockEtapProvider();
  return {
    provider,
    cleanup: () => {
      provider.clearExecutionLog();
    },
  };
}
