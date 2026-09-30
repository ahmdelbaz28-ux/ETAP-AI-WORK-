/**
 * tests/unit/core-providers-policy.test.ts — M4.5 (gate G4): Single provider policy.
 *
 * config/llm-provider-policy.json is the ONE decision point for providers.
 * This suite proves:
 *   1. The gateway derives its allow-list from that document at module load
 *      and fails closed if src/core/config.ts drifts from it.
 *   2. Changing the document changes this consumer's behaviour
 *      (the TypeScript half of the G4 propagation proof; the Python half is
 *      tests/test_llm_provider_policy.py).
 */

import { describe, expect, it } from 'vitest';
import {
  POLICY_PROVIDERS,
  PROVIDER_POLICY,
  assertPolicyConsistency,
  listConfiguredProviders,
  policyProvidersFor,
  type ProviderPolicy,
  type ProviderPolicyEntry,
} from '../../src/core/providers.js';
import type { Env } from '../../src/core/types.js';
import committedPolicy from '../../config/llm-provider-policy.json';

const EDGE_SURFACE = 'edge_gateway';

/** Env stub exposing every provider key so each policy entry is "configured". */
function envWithAllKeys(): Env {
  const env: Record<string, string> = {};
  for (const p of (committedPolicy.providers ?? []) as ProviderPolicyEntry[]) {
    env[p.env.api_key] = `key-${p.id}`;
    for (const extra of p.extra_env ?? []) env[extra] = 'acct-123';
  }
  return env as unknown as Env;
}

function clonePolicy(): ProviderPolicy {
  return JSON.parse(JSON.stringify(PROVIDER_POLICY)) as ProviderPolicy;
}

describe('M4.5: provider policy is the single decision point', () => {
  it('loads the committed policy document', () => {
    expect(PROVIDER_POLICY.policy_id).toBe('etap-llm-provider-policy');
    expect(PROVIDER_POLICY.providers.length).toBeGreaterThan(0);
    expect(PROVIDER_POLICY.model_tiers['tier_1_economy'].length).toBeGreaterThan(0);
  });

  it('passes the startup drift check against src/core/config.ts', () => {
    expect(() => assertPolicyConsistency()).not.toThrow();
  });

  it('fails the drift check when the policy declares an unknown provider', () => {
    const drifted = clonePolicy();
    drifted.providers.push({
      id: 'sneaky-new-provider',
      enabled: true,
      surfaces: [EDGE_SURFACE],
      default_model: 'x',
      base_url: 'https://example.invalid/v1',
      env: { api_key: 'X_API_KEY', base_url: 'X_BASE_URL', model: 'X_MODEL' },
    });
    expect(() => assertPolicyConsistency(drifted)).toThrowError(/provider policy drift/);
  });

  it('iterates the policy-derived allow-list, not a duplicated constant', () => {
    const expected = ((committedPolicy.providers ?? []) as ProviderPolicyEntry[])
      .filter((p) => p.enabled && p.surfaces.includes(EDGE_SURFACE))
      .map((p) => p.id);

    expect(POLICY_PROVIDERS).toEqual(expected);
    expect(policyProvidersFor(EDGE_SURFACE).map((p) => p.id)).toEqual(expected);
    expect(POLICY_PROVIDERS).toContain('openai');
    expect(POLICY_PROVIDERS).toContain('nvidia');
    // chat_stream-only providers must NOT leak into the gateway surface
    expect(POLICY_PROVIDERS).not.toContain('anthropic');
    expect(POLICY_PROVIDERS).not.toContain('gemini');
  });

  it('returns a model/base URL taken from the policy by default', () => {
    const providers = listConfiguredProviders(envWithAllKeys());
    const openai = providers.find((p) => p.name === 'openai');
    expect(openai).toBeDefined();
    expect(openai!.model).toBe(
      (committedPolicy.providers as ProviderPolicyEntry[]).find((p) => p.id === 'openai')!
        .default_model,
    );
    expect(openai!.baseURL).toBe('https://api.openai.com/v1');
    expect(providers.map((p) => p.name).sort()).toEqual([...POLICY_PROVIDERS].sort());
  });
});

describe('M4.5: changing the policy (one point) changes this consumer', () => {
  it('honours a changed default model', () => {
    const modified = clonePolicy();
    const openai = modified.providers.find((p) => p.id === 'openai')!;
    openai.default_model = 'policy-chosen-model';

    const providers = listConfiguredProviders(envWithAllKeys(), modified);
    expect(providers.find((p) => p.name === 'openai')!.model).toBe('policy-chosen-model');

    // ...while the untouched consumer still uses the committed policy
    const baseline = listConfiguredProviders(envWithAllKeys());
    expect(baseline.find((p) => p.name === 'openai')!.model).not.toBe(
      'policy-chosen-model',
    );
  });

  it('honours a changed base URL', () => {
    const modified = clonePolicy();
    const nvidia = modified.providers.find((p) => p.id === 'nvidia')!;
    nvidia.base_url = 'https://proxy.example.internal/v1';

    const providers = listConfiguredProviders(envWithAllKeys(), modified);
    expect(providers.find((p) => p.name === 'nvidia')!.baseURL).toBe(
      'https://proxy.example.internal/v1',
    );
  });

  it('drops a provider that is disabled in the policy', () => {
    const modified = clonePolicy();
    const fireworks = modified.providers.find((p) => p.id === 'fireworks')!;
    fireworks.enabled = false;

    const providers = listConfiguredProviders(envWithAllKeys(), modified);
    expect(providers.map((p) => p.name)).not.toContain('fireworks');
    expect(policyProvidersFor(EDGE_SURFACE, modified).map((p) => p.id)).not.toContain(
      'fireworks',
    );
    // the committed policy (used by the running gateway) is unchanged
    expect(POLICY_PROVIDERS).toContain('fireworks');
  });

  it('honours a re-keyed environment variable name', () => {
    const modified = clonePolicy();
    const render = modified.providers.find((p) => p.id === 'render')!;
    render.env = {
      api_key: 'RENDER_TOKEN',
      base_url: render.env.base_url,
      model: render.env.model,
    };

    const env = {
      ...envWithAllKeys(),
      RENDER_TOKEN: 'key-from-policy',
    } as unknown as Env;

    const providers = listConfiguredProviders(env, modified);
    const renderCfg = providers.find((p) => p.name === 'render');
    expect(renderCfg?.apiKey).toBe('key-from-policy');
    // the OLD key name must no longer be consulted
    expect(renderCfg?.apiKey).not.toBe('key-render');
  });
});
