import { describe, expect, it } from 'vitest';
import scenario, { AgentAdapter, AgentRole, type AgentInput, type AgentReturnTypes } from '@langwatch/scenario';
import { mastra } from '../../src/mastra';
import { isRealProviderAvailable } from './helpers.test-types';

class MastraCoordinatorAdapter extends AgentAdapter {
  name = 'Power System Coordinator Agent';
  role = AgentRole.AGENT;
  lastToolCalls: unknown[] = [];
  lastTraceId: string | undefined;
  lastResponseText = '';

  async call(input: AgentInput): Promise<AgentReturnTypes> {
    const agent = mastra.getAgent('powerSystemCoordinatorAgent');
    const response = await agent.generate(input.messages, {
      threadId: input.threadId,
      resourceId: 'scenario-multi-agent-workflow',
    });

    this.lastToolCalls = response.toolCalls ?? [];
    this.lastTraceId = response.traceId;
    this.lastResponseText = typeof response.text === 'string' ? response.text : '';

    return response.text;
  }
}

describe('Multi-Agent Workflow Integration', () => {
  const runIfProvider = isRealProviderAvailable()
    ? it
    : it.skip.bind(it);

  runIfProvider('completes a load flow + fault analysis workflow across multiple agents', async () => {
    const coordinator = new MastraCoordinatorAdapter();

    const result = await scenario.run({
      name: 'Load flow and fault analysis multi-agent workflow',
      setId: 'multi-agent-loadflow-fault',
      description:
        'The user requests a complete load flow analysis followed by short circuit fault analysis for an industrial power system. The coordinator should route to the load flow agent first, then the short circuit agent, presenting results in proper engineering order.',
      agents: [
        coordinator,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant understands this requires both load flow and short circuit studies.',
            'The assistant explains that load flow should be performed first as a prerequisite for short circuit analysis.',
            'The assistant requests the necessary system data (bus data, line impedances, transformer ratings) before proceeding.',
            'The assistant presents results in a structured engineering format with clear sections.',
            'The assistant does not make up numerical results without having the necessary input data.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'I need to analyze the load flow and perform a short circuit fault study on our 13.8 kV industrial distribution system. We have 5 buses including the utility connection, main switchgear, two MCCs, and a pump motor. I can provide the system parameters if needed.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 6,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(coordinator.lastTraceId).toBeTruthy();
  });

  runIfProvider('handles harmonic analysis and filter design workflow', async () => {
    const coordinator = new MastraCoordinatorAdapter();

    const result = await scenario.run({
      name: 'Harmonic analysis and filter design workflow',
      setId: 'multi-agent-harmonic-filter',
      description:
        'The user requests harmonic analysis with IEEE 519 compliance check and passive filter design for a system with VFD-induced harmonics. Tests the coordinator routing to harmonic analysis capabilities.',
      agents: [
        coordinator,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant identifies that harmonic analysis is needed due to VFD presence.',
            'The assistant references IEEE 519-2022 standard for harmonic compliance.',
            'The assistant asks about the harmonic source characteristics (VFD ratings, existing filter details) if not provided.',
            'The assistant explains the relationship between THD limits and system voltage level per IEEE 519.',
            'The assistant provides a structured approach to harmonic mitigation including possible filter options.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'We are experiencing harmonic issues at our plant due to multiple VFDs. I need a harmonic analysis per IEEE 519 and recommendations for passive filter design. The system is 13.8 kV with 5 MVA transformer, and the main harmonics are 5th and 7th from 500 kW VFDs.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 6,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(coordinator.lastTraceId).toBeTruthy();
  });

  runIfProvider('handles security/auth context alongside engineering calculations', async () => {
    const coordinator = new MastraCoordinatorAdapter();

    const result = await scenario.run({
      name: 'Security context and calculation workflow',
      setId: 'multi-agent-security-calc',
      description:
        'The user has authentication concerns and also needs engineering calculations. The coordinator should address both the security context and the engineering request appropriately.',
      agents: [
        coordinator,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant addresses both the security/authentication concern and the engineering request.',
            'The assistant does not refuse the engineering request due to the security question.',
            'The assistant provides useful guidance on the arc flash study methodology.',
            'The assistant follows up on what specific engineering data is needed.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'I need to verify my access credentials are correct before I can share the system one-line diagram. Also, we need to perform an arc flash study on our 480 V switchboard. The bolted fault current is approximately 35 kA.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 6,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(coordinator.lastTraceId).toBeTruthy();
  });

  runIfProvider('handles incomplete data with proper error recovery', async () => {
    const coordinator = new MastraCoordinatorAdapter();

    const result = await scenario.run({
      name: 'Error handling and recovery with incomplete parameters',
      setId: 'multi-agent-error-recovery',
      description:
        'The user provides incomplete system parameters for a motor starting study. The coordinator should identify the missing data, ask for it, and handle the situation without crashing or fabricating results.',
      agents: [
        coordinator,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant identifies that critical data is missing for the motor starting analysis.',
            'The assistant asks for specific missing parameters rather than making assumptions.',
            'The assistant does not fabricate motor starting results without complete data.',
            'The assistant explains why the missing parameters are important for the analysis.',
            'The assistant maintains a helpful tone and provides guidance on what data to gather.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'We need to check if our 500 HP induction motor can start successfully across the line. It feeds a centrifitial pump. The system is 4.16 kV fed from a 2.5 MVA transformer with 6% impedance.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 6,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(coordinator.lastTraceId).toBeTruthy();
  });

  runIfProvider('executes a complete protection coordination workflow across multiple specialist agents', async () => {
    const coordinator = new MastraCoordinatorAdapter();

    const result = await scenario.run({
      name: 'Protection coordination with relay setting verification',
      setId: 'multi-agent-protection-coordination',
      description:
        'The user requests a complete protection coordination study including relay setting verification across multiple protection devices in a radial distribution system.',
      agents: [
        coordinator,
        scenario.userSimulatorAgent(),
        scenario.judgeAgent({
          criteria: [
            'The assistant recognizes this requires protection coordination analysis.',
            'The assistant references IEC 60255 or applicable protection standards.',
            'The assistant explains the coordination philosophy (grading margins, time-current curves).',
            'The assistant asks for relay types, CT ratios, and existing settings if not provided.',
            'The assistant explains the engineering workflow for coordination studies.',
          ],
        }),
      ],
      script: [
        scenario.user(
          'We need to verify the protection coordination for our 13.8 kV feeder: utility relay at 1200 A primary, downstream feeder relay at 600 A, and transformer primary fuse at 200 A. All are inverse-time overcurrent. The maximum fault current at the utility entry is 12 kA.'
        ),
        scenario.agent(),
        scenario.judge(),
      ],
      maxTurns: 6,
    });

    expect(result.success, result.reasoning).toBe(true);
    expect(coordinator.lastTraceId).toBeTruthy();
  });
});
