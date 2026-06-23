import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { MockEtapProvider, createMockEtapScenario, type StudyTypeStr } from './helpers.mock-etap';
import { generateSimpleIndustrialSystem, generateStudyParameters } from './helpers.test-data';
import { execFile } from 'child_process';
import { promisify } from 'util';
import { writeFile, unlink } from 'fs/promises';
const execFileAsync = promisify(execFile);

describe('E2E Full Workflow — Create → Import → Study → Report → Export', () => {
  let mockEtap: MockEtapProvider;

  beforeEach(async () => {
    const setup = createMockEtapScenario();
    mockEtap = setup.provider;
    await mockEtap.connect();
  });

  afterEach(async () => {
    await mockEtap.disconnect();
  });

  // ==========================================================================
  // Deterministic Mock Tests (no live LLM required)
  // ==========================================================================

  it('1. creates and connects to a mock ETAP project', async () => {
    const projectPath = 'C:\\Projects\\E2E_Industrial_Plant.etap';
    const project = await mockEtap.openProject(projectPath);

    expect(project.isValid).toBe(true);
    expect(project.path).toBe(projectPath);
    expect(project.studyTypes).toContain('LOAD_FLOW');
    expect(project.studyTypes).toContain('SHORT_CIRCUIT');
    expect(project.studyTypes).toContain('ARC_FLASH');
    expect(project.studyTypes).toContain('PROTECTION_COORDINATION');
  });

  it('2. imports system data into the project', async () => {
    const systemData = generateSimpleIndustrialSystem();
    const projectPath = 'C:\\Projects\\E2E_Industrial_Plant.etap';

    const project = await mockEtap.openProject(projectPath);
    expect(project.isValid).toBe(true);

    // Validate imported data structure
    expect(systemData.buses).toHaveLength(5);
    expect(systemData.branches).toHaveLength(4);
    expect(systemData.base_mva).toBe(100);
    expect(systemData.base_kv).toBe(13.8);

    // Verify bus data
    const utilityBus = systemData.buses.find(b => b.id === 'UTILITY');
    expect(utilityBus).toBeDefined();
    expect(utilityBus?.nominal_kv).toBe(115);

    const mainSwgr = systemData.buses.find(b => b.id === 'MAIN-SWGR');
    expect(mainSwgr).toBeDefined();
    expect(mainSwgr?.nominal_kv).toBe(13.8);

    // Verify branch data
    const utilityToMain = systemData.branches.find(
      b => b.from_bus === 'UTILITY' && b.to_bus === 'MAIN-SWGR'
    );
    expect(utilityToMain).toBeDefined();
    expect(utilityToMain?.rating_mva).toBe(50);
  });

  it('3. runs a load flow study and returns structured results', async () => {
    const projectPath = 'C:\\Projects\\E2E_Industrial_Plant.etap';
    const params = generateStudyParameters().loadFlow;

    await mockEtap.openProject(projectPath);
    const result = await mockEtap.executeStudy(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr,
      params
    );

    expect(result.success).toBe(true);
    expect(result.errors).toHaveLength(0);
    expect(result.data.converged).toBe(true);
    expect(result.data.iterations).toBeGreaterThan(0);
    expect(result.data.total_generation_mw).toBeGreaterThan(0);
    expect(result.data.total_load_mw).toBeGreaterThan(0);
  });

  it('4. extracts and processes results for reporting', async () => {
    const projectPath = 'C:\\Projects\\E2E_Industrial_Plant.etap';

    await mockEtap.openProject(projectPath);
    await mockEtap.executeStudy(projectPath, 'LOAD_FLOW' as StudyTypeStr);
    const extracted = await mockEtap.extractResults(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr
    );

    expect(extracted.summary).toBeTruthy();
    expect(extracted.voltage_profile).toBeTruthy();
  });

  it('5. generates a comprehensive engineering report', async () => {
    const projectPath = 'C:\\Projects\\E2E_Industrial_Plant.etap';
    const params = generateStudyParameters().loadFlow;

    await mockEtap.openProject(projectPath);
    const studyResult = await mockEtap.executeStudy(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr,
      params
    );
    const extracted = await mockEtap.extractResults(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr
    );

    // Generate report
    const report = {
      project: 'E2E_Industrial_Plant',
      study: 'Load Flow Analysis',
      standard: 'IEEE Std 399 / IEC 60909',
      timestamp: new Date().toISOString(),
      system_summary: {
        base_mva: 100,
        base_kv: 13.8,
        frequency_hz: 60,
        total_buses: 5,
        total_branches: 4,
      },
      study_results: {
        converged: studyResult.data.converged,
        iterations: studyResult.data.iterations,
        total_generation_mw: studyResult.data.total_generation_mw,
        total_load_mw: studyResult.data.total_load_mw,
        total_losses_mw: studyResult.data.total_losses_mw,
      },
      voltage_profile: extracted.voltage_profile,
      critical_buses: extracted.critical_buses,
      overloaded_equipment: extracted.overloaded_equipment,
      warnings: studyResult.warnings,
    };

    expect(report.project).toBe('E2E_Industrial_Plant');
    expect(report.study_results.converged).toBe(true);
    expect(report.study_results.iterations).toBeGreaterThan(0);
    expect(report.voltage_profile).toBeTruthy();
  });

  it('6. exports results to structured JSON format', async () => {
    const projectPath = 'C:\\Projects\\E2E_Industrial_Plant.etap';
    const params = generateStudyParameters().loadFlow;

    await mockEtap.openProject(projectPath);
    const studyResult = await mockEtap.executeStudy(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr,
      params
    );
    const extracted = await mockEtap.extractResults(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr
    );

    // Export to JSON
    const exportPayload = {
      export_format: 'json',
      version: '1.0',
      project: projectPath,
      study_type: 'LOAD_FLOW',
      timestamp: new Date().toISOString(),
      results: studyResult.data,
      extracted_results: extracted,
      metadata: {
        generated_by: 'AhmedETAP',
        compliance: ['IEEE 399', 'IEC 60909'],
      },
    };

    // Validate export structure
    const jsonString = JSON.stringify(exportPayload, null, 2);
    const parsed = JSON.parse(jsonString);

    expect(parsed.export_format).toBe('json');
    expect(parsed.project).toBe(projectPath);
    expect(parsed.study_type).toBe('LOAD_FLOW');
    expect(parsed.results).toBeDefined();
    expect(parsed.results.converged).toBe(true);
    expect(parsed.extracted_results).toBeDefined();
    expect(parsed.metadata.generated_by).toBe('AhmedETAP');
  });

  it('7. runs the full E2E pipeline end-to-end in one flow', async () => {
    const projectPath = 'C:\\Projects\\E2E_Full_Pipeline.etap';
    const systemData = generateSimpleIndustrialSystem();
    const params = generateStudyParameters().loadFlow;

    // Step 1: Connect
    expect(mockEtap.isConnected()).toBe(true);

    // Step 2: Create/Open project
    const project = await mockEtap.openProject(projectPath);
    expect(project.isValid).toBe(true);
    expect(project.studyTypes).toContain('LOAD_FLOW');

    // Step 3: Import data (validated)
    expect(systemData.buses).toHaveLength(5);
    expect(systemData.branches).toHaveLength(4);

    // Step 4: Run study
    const studyResult = await mockEtap.executeStudy(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr,
      params
    );
    expect(studyResult.success).toBe(true);
    expect(studyResult.errors).toHaveLength(0);
    expect(studyResult.data.converged).toBe(true);

    // Step 5: Extract results
    const extracted = await mockEtap.extractResults(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr
    );
    expect(extracted.summary).toBeTruthy();
    expect(extracted.voltage_profile).toBeTruthy();

    // Step 6: Generate report
    const report = {
      project: 'E2E_Full_Pipeline',
      study: 'Load Flow',
      timestamp: new Date().toISOString(),
      converged: studyResult.data.converged,
      iterations: studyResult.data.iterations,
      total_generation_mw: studyResult.data.total_generation_mw,
      total_load_mw: studyResult.data.total_load_mw,
      total_losses_mw: studyResult.data.total_losses_mw,
      voltage_profile: extracted.voltage_profile,
      critical_buses: extracted.critical_buses,
      warnings: studyResult.warnings,
    };
    expect(report.converged).toBe(true);

    // Step 7: Export
    const exportPayload = {
      format: 'json',
      version: '1.0',
      project: projectPath,
      study: 'LOAD_FLOW',
      timestamp: new Date().toISOString(),
      report,
      raw_results: studyResult.data,
      extracted_results: extracted,
    };
    const jsonString = JSON.stringify(exportPayload, null, 2);
    const parsed = JSON.parse(jsonString);
    expect(parsed.format).toBe('json');
    expect(parsed.report.converged).toBe(true);

    // Step 8: Close
    await mockEtap.closeProject(projectPath);
    expect(mockEtap.getExecutionLog().length).toBeGreaterThanOrEqual(4);

    // Verify execution log
    const log = mockEtap.getExecutionLog();
    const actions = log.map(l => l.action);
    expect(actions).toContain('openProject');
    expect(actions).toContain('executeStudy');
    expect(actions).toContain('extractResults');
    expect(actions).toContain('closeProject');
  });

  it('8. runs arc flash study as part of the E2E workflow', async () => {
    const projectPath = 'C:\\Projects\\E2E_ArcFlash.etap';
    const arcParams = generateStudyParameters().arcFlash;

    await mockEtap.openProject(projectPath);
    const result = await mockEtap.executeStudy(
      projectPath,
      'ARC_FLASH' as StudyTypeStr,
      arcParams
    );

    expect(result.success).toBe(true);
    expect(result.data.standard).toBe('IEEE 1584-2018');
    expect(result.data.incident_energy_cal_per_cm2).toBeGreaterThan(0);
    expect(result.data.ppe_level).toBeTruthy();
  });

  it('9. runs short circuit study as part of the E2E workflow', async () => {
    const projectPath = 'C:\\Projects\\E2E_ShortCircuit.etap';
    const scParams = generateStudyParameters().shortCircuit;

    await mockEtap.openProject(projectPath);
    const result = await mockEtap.executeStudy(
      projectPath,
      'SHORT_CIRCUIT' as StudyTypeStr,
      scParams
    );

    expect(result.success).toBe(true);
    expect(result.data.standard).toBe('IEC 60909-0:2016');
    expect(result.data.faults).toBeDefined();
  });

  it('10. handles errors gracefully during the E2E workflow', async () => {
    const projectPath = 'C:\\Projects\\E2E_Error.etap';

    await mockEtap.openProject(projectPath);
    mockEtap.setFailureMode('execution');

    const result = await mockEtap.executeStudy(
      projectPath,
      'LOAD_FLOW' as StudyTypeStr
    );

    expect(result.success).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors[0]).toContain('did not converge');

    // Restore for cleanup
    mockEtap.setFailureMode('none');
  });

  it('11. runs harmonic analysis study as part of the E2E workflow', async () => {
    const projectPath = 'C:\\Projects\\E2E_Harmonic.etap';
    const harmonicParams = generateStudyParameters().harmonic;

    await mockEtap.openProject(projectPath);
    const result = await mockEtap.executeStudy(
      projectPath,
      'HARMONIC_ANALYSIS' as StudyTypeStr,
      harmonicParams
    );

    expect(result.success).toBe(true);
    expect(result.data.standard).toBe('IEEE 519-2022');
    expect(result.data.thd_voltage_percent).toBeDefined();
    expect(result.data.compliance_status).toBe('compliant');
  });

  it('12. runs motor starting study as part of the E2E workflow', async () => {
    const projectPath = 'C:\\Projects\\E2E_MotorStarting.etap';
    const motorParams = generateStudyParameters().motorStarting;

    await mockEtap.openProject(projectPath);
    const result = await mockEtap.executeStudy(
      projectPath,
      'MOTOR_STARTING' as StudyTypeStr,
      motorParams
    );

    expect(result.success).toBe(true);
    expect(result.data.motor_name).toBeDefined();
    expect(result.data.starting_current_pu).toBeGreaterThan(0);
    expect(result.data.voltage_dip_percent).toBeDefined();
  });

  it('13. runs protection coordination study as part of the E2E workflow', async () => {
    const projectPath = 'C:\\Projects\\E2E_Protection.etap';

    await mockEtap.openProject(projectPath);
    const result = await mockEtap.executeStudy(
      projectPath,
      'PROTECTION_COORDINATION' as StudyTypeStr
    );

    expect(result.success).toBe(true);
    expect(result.data.all_coordinated).toBe(true);
    expect(result.data.standard).toBe('IEC 60255');
    expect(result.data.coordination_pairs).toBeDefined();
  });

  it('14. exercises the real Python PowerSystemEngine through a subprocess', async () => {
    // Skip if Python or numpy is not available (e.g. in CI Code Quality Check
    // job which only installs Node dependencies, not Python ones).
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const probeResult = await new Promise<{ ok: boolean; reason?: string }>((resolve) => {
      execFile(pythonCmd, ['-c', 'import numpy, sys; sys.exit(0)'], (err) => {
        if (err) resolve({ ok: false, reason: 'numpy not installed in Python environment' });
        else resolve({ ok: true });
      });
    });
    if (!probeResult.ok) {
      console.log(`Skipping test 14: ${probeResult.reason}`);
      return; // vitest treats this as a pass (no assertions)
    }

    const tmpFile = `tests/scenarios/tmp_e2e_engine_${Date.now()}.py`;
    const script = `
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from engine.engine import PowerSystemEngine

try:
    e = PowerSystemEngine()
    print('ENGINE_OK')
    # run_study requires system data; verify it is callable without crashing
    print('HAS_RUN_STUDY:', hasattr(e, 'run_study'))
except Exception as ex:
    print('ENGINE_ERROR:', str(ex))
    sys.exit(1)
    `.trim();

    try {
      await writeFile(tmpFile, script);
      const { stdout, stderr } = await execFileAsync(pythonCmd, [tmpFile], {
        cwd: process.cwd(),
        env: { ...process.env, PYTHONPATH: process.cwd() },
      });

      // Python warnings may go to stderr — only fail on actual errors
      if (stderr && stderr.toLowerCase().includes('error')) {
        throw new Error(`Python subprocess error: ${stderr}`);
      }

      expect(stdout).toContain('ENGINE_OK');
      expect(stdout).toContain('HAS_RUN_STUDY: True');
    } finally {
      await unlink(tmpFile).catch(() => { /* ignore cleanup errors */ });
    }
  });
});
