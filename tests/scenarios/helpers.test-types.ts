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
  if (process.env.SKIP_LIVE_SCENARIO_TESTS === 'true') return false;

  const isValidKey = (key: string | undefined): boolean => {
    if (!key || key.trim().length < 20) return false;
    const lower = key.toLowerCase().trim();
    // Reject only exact placeholder strings
    const exactPlaceholders = ['test', 'dummy', 'placeholder', 'your-key', 'your_key', 'example', 'changeme', 'secret', 'token', 'key_here', 'your-api-key', 'api-key', 'xoxb'];
    // SonarCloud typescript:S7765: use .includes() for value existence
    if (exactPlaceholders.includes(lower)) return false;
    // Reject keys that are purely numeric or purely alphabetic (not real API keys)
    // SonarCloud typescript:S6353: \d is the concise equivalent of [0-9]
    if (/^\d+$/.test(key) || /^[a-zA-Z]+$/.test(key)) return false;
    return true;
  };

  const hasQwen = isValidKey(process.env.QWEN_API_KEY);
  const hasQwen2 = isValidKey(process.env.QWEN2_API_KEY);
  const hasGlm = isValidKey(process.env.GLM_API_KEY);
  const hasOpenAI = isValidKey(process.env.OPENAI_API_KEY);
  return hasQwen || hasQwen2 || hasGlm || hasOpenAI;
}
