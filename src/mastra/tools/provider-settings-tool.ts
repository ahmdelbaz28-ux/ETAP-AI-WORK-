import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { getProviderStatus, testProviderById, ProviderConfig } from '../lib/model-config';

export const providerSettingsTool = createTool({
  id: 'provider-settings',
  description: 'Get and test all LLM provider settings',
  inputSchema: z.object({
    action: z.enum(['list', 'test']).describe('Action to perform: list providers or test all providers'),
  }),
  execute: async ({ action }) => {
    if (action === 'list') {
      return getAllProviders();
    } else if (action === 'test') {
      return testAllProviders();
    }
    throw new Error(`Unknown action: ${action}`);
  },
});

/**
 * Get the status of all configured providers.
 * This function is exported as getAllProviders to match the expected import.
 */
export function getAllProviders(): ProviderConfig[] {
  return getProviderStatus();
}

/**
 * Test all configured providers.
 * Returns an array of test results for each provider.
 * This function is exported as testAllProviders to match the expected import.
 */
export async function testAllProviders(): Promise<Array<{ name: string; success: boolean; error?: string }>> {
  const providers = getProviderStatus();
  const results = await Promise.all(
    providers.map(async (provider) => {
      const result = await testProviderById(provider.name);
      return {
        name: provider.name,
        success: result.success,
        error: result.error,
      };
    })
  );
  return results;
}