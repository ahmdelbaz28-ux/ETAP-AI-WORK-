import { describe, expect, it } from 'vitest';
import worker from '../src/index';
import type { Env, ExecutionContext } from '../src/index';

// Minimal KVNamespace type for local testing (Cloudflare Workers global)
declare global {
  interface KVNamespace {
    get(key: string, opts?: { type?: string }): Promise<unknown | null>;
    put(key: string, value: string, opts?: { expirationTtl?: number }): Promise<void>;
    delete(key: string): Promise<void>;
    list(opts?: {
      prefix?: string;
      limit?: number;
      cursor?: string;
    }): Promise<{ keys: { name: string }[]; list_complete: boolean; cursor?: string }>;
  }
}

/**
 * Cloudflare Worker Integration Tests
 * Tests the src/index.ts API gateway without deploying.
 */

describe('Cloudflare Worker API Gateway', () => {
  const mockKV = () => {
    const store = new Map<string, { value: string; ttl?: number }>();
    return {
      get: async (key: string, opts?: { type?: string }) => {
        const entry = store.get(key);
        if (!entry) return null;
        if (opts?.type === 'json') return JSON.parse(entry.value);
        return entry.value;
      },
      put: async (key: string, value: string, opts?: { expirationTtl?: number }) => {
        store.set(key, { value, ttl: opts?.expirationTtl });
      },
      delete: async (key: string) => {
        store.delete(key);
      },
      list: async (opts?: { prefix?: string; limit?: number; cursor?: string }) => {
        const keys: { name: string }[] = [];
        for (const key of store.keys()) {
          if (!opts?.prefix || key.startsWith(opts.prefix)) {
            keys.push({ name: key });
          }
        }
        return { keys: keys.slice(0, opts?.limit || 1000), list_complete: true };
      },
    } as unknown as KVNamespace;
  };

  const makeRequest = (path: string, init?: RequestInit, env?: Partial<Env>): Promise<Response> => {
    const url = new URL(path, 'http://localhost');
    const kv = mockKV();
    const testEnv: Partial<Env> = env ?? {
      API_KEY_SECRET: 'test-secret',
      RATE_LIMIT_KV: kv,
      TASK_STORE_KV: kv,
      METRICS_KV: kv,
      API_KEYS_KV: kv,
    };
    const testCtx: ExecutionContext = { waitUntil: () => {}, passThroughOnException: () => {} };
    return worker.fetch(new Request(url.toString(), init), testEnv as any, testCtx);
  };

  it('returns 200 on health check', async () => {
    const res = await makeRequest('/health');
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.ok).toBe(true);
    expect(body.service).toBe('etap-ai-platform');
    expect(body.version).toBe('1.0.0');
    expect(body.traceId).toBeTruthy();
  });

  it('returns 200 on root with service info', async () => {
    const res = await makeRequest('/');
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.service).toBe('AhmedETAP');
    expect(body.health).toBe('/health');
  });

  it('returns 404 on unknown routes', async () => {
    const res = await makeRequest('/unknown-route');
    expect(res.status).toBe(404);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.error).toBe(true);
    expect(body.status).toBe(404);
  });

  it('returns 401 without API key on protected routes', async () => {
    const res = await makeRequest('/api/v1/agents');
    expect(res.status).toBe(401);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/Missing x-api-key header/i);
  });

  it('returns 401 with invalid API key', async () => {
    const res = await makeRequest('/api/v1/agents', {
      headers: { 'x-api-key': 'bad-key' },
    });
    expect(res.status).toBe(401);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/Invalid API key/i);
  });

  it('returns 401 when API_KEY_SECRET is not configured', async () => {
    const res = await makeRequest(
      '/api/v1/agents',
      {
        headers: { 'x-api-key': 'some-key' },
      },
      {},
    );
    expect(res.status).toBe(401);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/API_KEY_SECRET is not configured/i);
  });

  it('returns 200 and agent list with valid API key (legacy secret)', async () => {
    const res = await makeRequest('/api/v1/agents', {
      headers: { 'x-api-key': 'test-secret' },
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(Array.isArray(body.agents)).toBe(true);
  });

  it('returns 200 and agent list with valid API key (KV-backed)', async () => {
    const kv = mockKV();
    await kv.put(
      'api-key:kv-test-key',
      JSON.stringify({ createdAt: Date.now(), name: 'test-key' }),
    );
    const env = {
      API_KEY_SECRET: 'test-secret',
      RATE_LIMIT_KV: kv,
      TASK_STORE_KV: kv,
      METRICS_KV: kv,
      API_KEYS_KV: kv,
    };
    const res = await makeRequest(
      '/api/v1/agents',
      {
        headers: { 'x-api-key': 'kv-test-key' },
      },
      env,
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(Array.isArray(body.agents)).toBe(true);
  });

  it('returns 401 with revoked KV-backed API key', async () => {
    const kv = mockKV();
    await kv.put(
      'api-key:revoked-key',
      JSON.stringify({ createdAt: Date.now(), revoked: true, name: 'revoked' }),
    );
    const env = {
      API_KEY_SECRET: 'test-secret',
      RATE_LIMIT_KV: kv,
      TASK_STORE_KV: kv,
      METRICS_KV: kv,
      API_KEYS_KV: kv,
    };
    const res = await makeRequest(
      '/api/v1/agents',
      {
        headers: { 'x-api-key': 'revoked-key' },
      },
      env,
    );
    expect(res.status).toBe(401);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/revoked/i);
  });

  it('returns CORS headers on preflight', async () => {
    const res = await makeRequest('/api/v1/agents', {
      method: 'OPTIONS',
      headers: { origin: 'http://example.com' },
    });
    expect(res.status).toBe(204);
    expect(res.headers.get('access-control-allow-origin')).toBe('http://example.com');
    expect(res.headers.get('access-control-allow-methods')).toContain('POST');
  });

  it('returns 400 for invalid JSON on chat endpoint', async () => {
    const res = await makeRequest('/api/v1/agents/load-flow-agent/chat', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': 'test-secret',
      },
      body: 'not-json',
    });
    expect(res.status).toBe(400);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/Invalid JSON body/i);
  });

  it('returns 400 for missing messages on chat endpoint', async () => {
    const res = await makeRequest('/api/v1/agents/load-flow-agent/chat', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': 'test-secret',
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/messages array is required/i);
  });

  it('returns 404 for unknown agent on chat endpoint', async () => {
    const res = await makeRequest('/api/v1/agents/unknown-agent/chat', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': 'test-secret',
      },
      body: JSON.stringify({ messages: [{ role: 'user', content: 'hi' }] }),
    });
    expect(res.status).toBe(404);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/unknown-agent/i);
  });

  it('returns 400 for invalid study type', async () => {
    const res = await makeRequest('/api/v1/studies/run', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': 'test-secret',
      },
      body: JSON.stringify({ studyType: 'invalid_study' }),
    });
    expect(res.status).toBe(400);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/Invalid studyType/i);
  });

  it('returns 200 for valid study type (dry-run) and persists to KV', async () => {
    const kv = mockKV();
    const env = {
      API_KEY_SECRET: 'test-secret',
      RATE_LIMIT_KV: kv,
      TASK_STORE_KV: kv,
      METRICS_KV: kv,
      API_KEYS_KV: kv,
    };
    const res = await makeRequest(
      '/api/v1/studies/run',
      {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': 'test-secret',
        },
        body: JSON.stringify({ studyType: 'load_flow', parameters: {}, dryRun: true }),
      },
      env,
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.status).toBe('dry_run');
    expect(body.taskId).toBeTruthy();
    const taskId = body.taskId as string;

    // Verify task is persisted in KV
    const statusRes = await makeRequest(
      `/api/v1/studies/status/${taskId}`,
      {
        headers: { 'x-api-key': 'test-secret' },
      },
      env,
    );
    expect(statusRes.status).toBe(200);
    const statusBody = (await statusRes.json()) as Record<string, unknown>;
    expect(statusBody.status).toBe('dry_run');
    expect(statusBody.studyType).toBe('load_flow');
  });

  it('enforces rate limiting via mock KV', async () => {
    const kv = mockKV();
    const env = {
      API_KEY_SECRET: 'test-secret',
      RATE_LIMIT_KV: kv,
      RATE_LIMIT_REQUESTS_PER_MINUTE: '3',
    };
    // 3 requests within the limit should succeed
    for (let i = 0; i < 3; i++) {
      const res = await makeRequest(
        '/api/v1/agents',
        {
          headers: { 'x-api-key': 'test-secret' },
        },
        env,
      );
      expect(res.status).toBe(200);
    }
    // 4th request should be rate limited
    const blocked = await makeRequest(
      '/api/v1/agents',
      {
        headers: { 'x-api-key': 'test-secret' },
      },
      env,
    );
    expect(blocked.status).toBe(429);
    const body = (await blocked.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/Rate limit exceeded/i);
    expect(body.status).toBe(429);
  });
});
