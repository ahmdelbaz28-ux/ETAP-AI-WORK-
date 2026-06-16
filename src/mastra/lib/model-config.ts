/**
 * Active model configuration for Mastra agents.
 *
 * Returns a Mastra-compatible LanguageModelV1 instance. Uses the same
 * provider config pattern as mastra.config.ts (createOpenAI from
 * @ai-sdk/openai).
 *
 * Note: createOpenAI() does NOT throw if OPENAI_API_KEY is missing —
 * it only validates the key when an actual API call is made. This lets
 * the Mastra build succeed in CI environments without API keys, while
 * still failing loudly if an agent is actually invoked without
 * configuration.
 */
import { createOpenAI } from '@ai-sdk/openai';
import type { LanguageModelV1 } from 'ai';

const openai = createOpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
});

const ACTIVE_MODEL_ID =
  process.env.OPENAI_MODEL_ID ||
  process.env.OPENAI_MODEL ||
  'gpt-4o';

/**
 * Returns the active model for Mastra agents.
 *
 * Safe to call at module-load time (no API key validation happens
 * until an agent is actually invoked).
 */
export function getActiveModelConfig(): LanguageModelV1 {
  return openai(ACTIVE_MODEL_ID);
}
