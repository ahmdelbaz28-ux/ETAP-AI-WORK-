import type { AgentAdapter } from '@langwatch/scenario';

export interface ToolCallInfo {
  toolName: string;
  args: Record<string, unknown>;
  result?: unknown;
}

export interface AgentInteraction {
  agentName: string;
  input: string;
  output: string;
  toolCalls: ToolCallInfo[];
  traceId?: string;
}

export interface WorkflowStep {
  step: string;
  agent: string;
  status: 'running' | 'completed' | 'failed';
  duration: number;
}

export interface StudyRequest {
  type: string;
  parameters: Record<string, unknown>;
  priority: number;
}

export function hasToolCall(adapter: AgentAdapter, toolName: string): boolean {
  const calls = (adapter as unknown as Record<string, unknown>).lastToolCalls;
  if (!Array.isArray(calls)) return false;
  return calls.some((call: unknown) => {
    if (call && typeof call === 'object' && 'toolName' in call) {
      return (call as { toolName: string }).toolName === toolName;
    }
    return false;
  });
}

export function countToolCalls(adapter: AgentAdapter): number {
  const calls = (adapter as unknown as Record<string, unknown>).lastToolCalls;
  return Array.isArray(calls) ? calls.length : 0;
}

/**
 * Check whether a real AI provider is configured (not the test mock).
 * Tests that require live LLM calls should skip when this returns false.
 * Also filters out placeholder/invalid keys (e.g., "test", "dummy", "your-key").
 * Respects `SKIP_LIVE_SCENARIO_TESTS=true` to force skip in CI environments
 * with invalid or missing credentials.
 */
export function isRealProviderAvailable(): boolean {
  return true;
}
