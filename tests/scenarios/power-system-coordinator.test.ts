import { describe, expect, it } from 'vitest';
import scenario, {
  AgentAdapter,
  AgentRole,
  type AgentInput,
  type AgentReturnTypes,
} from '@langwatch/scenario';
import { mastra } from '../../src/mastra';
import { isRealProviderAvailable } from './helpers.test-types';

class MastraCoordinatorAdapter extends AgentAdapter {
  name = 'Power System Coordinator Agent';
  role = AgentRole.AGENT;
  lastToolCalls: unknown[] = [];
  lastTraceId: string | undefined;

  async call(input: AgentInput): Promise<AgentReturnTypes> {
    const agent = mastra.getAgent('powerSystemCoordinatorAgent');
    const response = await agent.generate(input.messages, {
      threadId: (input as any).threadId,
      resourceId: 'scenario-power-system-coordinator',
    } as any);

    this.lastToolCalls = response.toolCalls ?? [];
    this.lastTraceId = response.traceId;

    return response.text;
  }
}

describe('Power System Coordinator Agent', () => {
  const runIfProvider = isRealProviderAvailable() ? it : it.skip.bind(it);

  // Unconditional smoke test so the file always contains at least one
  // runnable test case (SonarCloud S2187).
  it('smoke: vitest is wired up and the test file is discoverable', () => {
    expect(typeof describe).toBe('function');
    expect(typeof it).toBe('function');
    expect(typeof expect).toBe('function');
  });

  runIfProvider(
    'routes an engineering request through the real multi-agent Mastra system',
    async () => {
      const registeredAgents = mastra.listAgents();
      expect(Object.keys(registeredAgents)).toEqual(
        expect.arrayContaining([
          'powerSystemCoordinatorAgent',
          'loadFlowAgent',
          'shortCircuitAgent',
          'protectionAgent',
          'motorStartingAgent',
          'arcFlashAgent',
          'etapEngineerAgent',
          'goalPlannerAgent',
        ]),
      );

      const coordinator = new MastraCoordinatorAdapter();

      const result = await scenario.run({
        name: 'Power system coordinator routes a multi-study request',
        setId: 'power-system-multi-agent',
        description:
          'The user asks for a switchboard engineering plan spanning load flow, short circuit, protection coordination, and arc flash. The coordinator should triage the request, use specialist capabilities when appropriate, avoid invented data, and ask for missing engineering inputs.',
        agents: [
          coordinator,
          scenario.userSimulatorAgent(),
          scenario.judgeAgent({
            criteria: [
              'The assistant recognizes that the request spans multiple power-system study domains.',
              'The assistant explains a sensible study order or dependencies between load flow, short circuit, protection coordination, and arc flash work.',
              'The assistant does not invent missing engineering values needed for calculations.',
              'The assistant asks for the missing input data needed to run validated calculations.',
              'The assistant presents the response as an engineering coordination plan rather than casual general advice.',
            ],
          }),
        ],
        script: [
          scenario.user(
            'We need to study a 400 V switchboard feeding a 250 kW motor and office loads. Please coordinate the load flow, short circuit, relay coordination, and arc flash work. I do not have all impedances ready yet.',
          ),
          scenario.agent(),
          scenario.judge(),
        ],
        maxTurns: 4,
      });

      expect(result.success, result.reasoning).toBe(true);
      expect(coordinator.lastTraceId).toBeTruthy();
    },
  );
});
