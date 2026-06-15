import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import scenario, { AgentAdapter, AgentRole, type AgentInput, type AgentReturnTypes } from '@langwatch/scenario';
import { mastra } from '../../src/mastra';
import { MockEtapProvider, createMockEtapScenario, type StudyTypeStr } from './helpers.mock-etap';
import { isRealProviderAvailable } from './helpers.test-types';

class MastraEtapAdapter extends AgentAdapter {
  name = 'ETAP Engineering Agent';
  role = AgentRole.AGENT;
  lastToolCalls: unknown[] = [];
  lastTraceId: string | undefined;

  async call(input: AgentInput): Promise<AgentReturnTypes> {
    const agent = mastra.getAgent('etapEngineerAgent');
    const response = await agent.generate(input.messages, {
      threadId: (input as any).threadId,
      resourceId: 'scenario-etap-integration',
    } as any);

    this.lastToolCalls = response.toolCalls ?? [];
    this.lastTraceId = response.traceId;

    return response.text;
  }
}

describe('ETAP Integration Scenarios', () => {
  let mockEtap: MockEtapProvider;
  const runIfProvider = isRealProviderAvailable()
    ? it
    : it.skip.bind(it);

  beforeEach(async () => {
    const setup = createMockEtapScenario();
    mockEtap = setup.provider;
    await mockEtap.connect();
  });

  afterEach(async () => {
    await mockEtap.disconnect();
  });

  runIfProvider('opens an ETAP project and validates its contents', async () => {
    const etapAgent = new MastraEtapAdapter();

    const result = await scenario.run({
      name: 'ETAP project opening and validation',
      setId: 'etap-open-validate',
      description:
        'The user asks the ETAP engineering agent to open an existing project and validate its contents before running studies.',
      agents: [
        etapAgent,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant confirms the project type and basic parameters.',
            'The assistant validates that the project contains the necessary study cases.',
            'The assistant checks for any project warnings or configuration issues.',
            'The assistant provides a summary of the project contents to the user.',
            'The assistant does not proceed with studies before validating the project.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'Please open the industrial plant ETAP project at C:\\Projects\\Industrial_Plant_v2.etap and validate it. I need to confirm all study cases are properly configured before we proceed with analysis.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 4,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(etapAgent.lastTraceId).toBeTruthy();
  });

  runIfProvider('executes a load flow study and extracts results from ETAP', async () => {
    const etapAgent = new MastraEtapAdapter();

    const result = await scenario.run({
      name: 'ETAP load flow execution and results extraction',
      setId: 'etap-loadflow-results',
      description:
        'The user requests a load flow study run in ETAP and expects structured results extraction including bus voltages, line loadings, and system summary.',
      agents: [
        etapAgent,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant understands the load flow study type and required parameters.',
            'The assistant explains the results in engineering terms (voltage profile, loading).',
            'The assistant identifies any buses with voltage deviations.',
            'The assistant provides a clear summary of the study findings.',
            'The assistant structures the output for easy interpretation.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'Run a load flow study on the Industrial_Plant project. Use Newton-Raphson method with 100 max iterations. I need to see the bus voltage profile and branch loading results.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 4,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(etapAgent.lastTraceId).toBeTruthy();
  });

  runIfProvider('handles invalid project paths with proper error reporting', async () => {
    const etapAgent = new MastraEtapAdapter();

    const result = await scenario.run({
      name: 'ETAP error handling for invalid project path',
      setId: 'etap-error-invalid-path',
      description:
        'The user provides a non-existent or invalid project path. The assistant should identify the error and provide helpful guidance.',
      agents: [
        etapAgent,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant recognizes the project file is invalid or missing.',
            'The assistant asks the user to verify the file path.',
            'The assistant suggests checking file extension (.etap) and directory location.',
            'The assistant does not attempt to proceed with a non-existent project.',
            'The assistant provides helpful troubleshooting steps.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'Open the project at C:\\Projects\\Nonexistent_Project.etap and run a short circuit study on it.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 4,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(etapAgent.lastTraceId).toBeTruthy();
  });

  runIfProvider('handles study execution failures gracefully', async () => {
    const etapAgent = new MastraEtapAdapter();
    mockEtap.setFailureMode('execution');

    const result = await scenario.run({
      name: 'ETAP study execution failure recovery',
      setId: 'etap-execution-failure',
      description:
        'A harmonic analysis study fails to converge during ETAP execution. The assistant should report the error, suggest possible causes, and recommend corrective actions.',
      agents: [
        etapAgent,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant reports the study execution failure clearly.',
            'The assistant suggests possible causes for convergence failure.',
            'The assistant recommends corrective actions (check system data, adjust settings).',
            'The assistant offers to help troubleshoot the issue.',
            'The assistant maintains a professional engineering tone.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'Run a harmonic analysis on the Industrial_Plant project to check IEEE 519 compliance. The system has several VFDs that might cause resonance issues.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 4,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(etapAgent.lastTraceId).toBeTruthy();
  });

  it('validates mock ETAP provider directly with deterministic assertions', async () => {
    const projectPath = 'C:\\Projects\\Test_Project.etap';
    const project = await mockEtap.openProject(projectPath);
    expect(project.isValid).toBe(true);
    expect(project.path).toBe(projectPath);
    expect(project.studyTypes).toContain('LOAD_FLOW');
    expect(project.studyTypes).toContain('SHORT_CIRCUIT');

    const lfResult = await mockEtap.executeStudy(projectPath, 'LOAD_FLOW' as StudyTypeStr);
    expect(lfResult.success).toBe(true);
    expect(lfResult.data.converged).toBe(true);
    expect(lfResult.errors).toHaveLength(0);

    const scResult = await mockEtap.executeStudy(projectPath, 'SHORT_CIRCUIT' as StudyTypeStr);
    expect(scResult.success).toBe(true);
    expect(scResult.data.standard).toBe('IEC 60909-0:2016');

    const extracted = await mockEtap.extractResults(projectPath, 'LOAD_FLOW' as StudyTypeStr);
    expect(extracted.summary).toBeTruthy();
    expect(extracted.voltage_profile).toBeTruthy();

    const log = mockEtap.getExecutionLog();
    expect(log.length).toBeGreaterThanOrEqual(3);

    await mockEtap.closeProject(projectPath);
  });

  it('validates error handling in mock ETAP provider', async () => {
    const projectPath = 'C:\\Projects\\Invalid.etap';

    mockEtap.setFailureMode('connection');
    await expect(mockEtap.connect()).rejects.toThrow('connection failed');

    mockEtap.setFailureMode('none');
    await mockEtap.connect();
    mockEtap.setFailureMode('validation');
    await expect(mockEtap.openProject(projectPath + '.bad')).rejects.toThrow('Project not found');

    mockEtap.setFailureMode('execution');
    const opened = await mockEtap.openProject('C:\\Projects\\Good.etap');
    expect(opened.isValid).toBe(true);
    const execResult = await mockEtap.executeStudy('C:\\Projects\\Good.etap', 'LOAD_FLOW' as StudyTypeStr);
    expect(execResult.success).toBe(false);
    expect(execResult.errors.length).toBeGreaterThan(0);

    mockEtap.setFailureMode('none');
  });
});
