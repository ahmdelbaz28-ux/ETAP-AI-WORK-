import { describe, expect, it } from 'vitest';
import worker from '../src/index';
import type { Env, ExecutionContext } from '../src/index';

/**
 * Mock Engineering Service Integration Tests
 * Tests the Worker routing to Engineering Service for real computation.
 */

function mockKV() {
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
    delete: async (key: string) => { store.delete(key); },
    list: async (opts?: { prefix?: string; limit?: number; cursor?: string }) => {
      const keys: { name: string }[] = [];
      for (const key of store.keys()) {
        if (!opts?.prefix || key.startsWith(opts.prefix)) {
          keys.push({ name: key });
        }
      }
      return { keys: keys.slice(0, opts?.limit || 1000), list_complete: true };
    },
  } as unknown as Env['RATE_LIMIT_KV'];
}

function makeRequest(
  path: string,
  init?: RequestInit,
  env?: Partial<Env>
): Promise<Response> {
  const url = new URL(path, 'http://localhost');
  const kv = mockKV();
  // 44-char key — satisfies API_KEY_MIN_LENGTH (32).
  const TEST_KEY = 'test-secret-0123456789-abcdefghijklmnopqrstuvwxyz';
  const testEnv: Partial<Env> = env ?? {
    API_KEY_SECRET: TEST_KEY,
    RATE_LIMIT_KV: kv,
    TASK_STORE_KV: kv,
    METRICS_KV: kv,
    API_KEYS_KV: kv,
  };
  const testCtx: ExecutionContext = { waitUntil: () => {}, passThroughOnException: () => {} };
  return worker.fetch(new Request(url.toString(), init), testEnv as any, testCtx);
}

// 44-char key — satisfies API_KEY_MIN_LENGTH (32).
// POST requests also need a trusted origin to pass CSRF validation.
const TEST_KEY = 'test-secret-0123456789-abcdefghijklmnopqrstuvwxyz';
const TRUSTED_ORIGIN = 'https://etap-ai-work.vercel.app';
const POST_HEADERS = {
  'content-type': 'application/json',
  'x-api-key': TEST_KEY,
  'origin': TRUSTED_ORIGIN,
};

describe('Engineering Service Integration', () => {
  it('returns 503 when Engineering Service is not configured', async () => {
    const res = await makeRequest('/api/v1/studies/run', {
      method: 'POST',
      headers: POST_HEADERS,
      body: JSON.stringify({ studyType: 'load_flow', parameters: {} }),
    });
    // Note: status >= 500 responses have their message masked to
    // 'Internal server error' by errorResponse() per security hardening
    // (commit c24ae1d3 — Better Auth best practices: never leak internals).
    // We verify the status code; the original message is still in the
    // audit log, not the response body.
    expect(res.status).toBe(503);
  });

  it('returns 200 for dry-run mode even without Engineering Service', async () => {
    const res = await makeRequest('/api/v1/studies/run', {
      method: 'POST',
      headers: POST_HEADERS,
      body: JSON.stringify({ studyType: 'load_flow', parameters: {}, dryRun: true }),
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.status).toBe('dry_run');
    expect(body.message).toMatch(/Dry-run successful/i);
  });

  it('validates study type before checking Engineering Service', async () => {
    const res = await makeRequest('/api/v1/studies/run', {
      method: 'POST',
      headers: POST_HEADERS,
      body: JSON.stringify({ studyType: 'invalid_type', parameters: {} }),
    });
    expect(res.status).toBe(400);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/Invalid studyType/i);
  });

  it('requires studyType in request body', async () => {
    const res = await makeRequest('/api/v1/studies/run', {
      method: 'POST',
      headers: POST_HEADERS,
      body: JSON.stringify({ parameters: {} }),
    });
    expect(res.status).toBe(400);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.message).toMatch(/studyType is required/i);
  });

  it('health endpoint includes Engineering Service status', async () => {
    const res = await makeRequest('/health');
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body.ok).toBe(true);
    expect(body.engineeringService).toBeDefined();
    const eng = body.engineeringService as Record<string, unknown>;
    expect(eng.configured).toBe(false);
    expect(eng.healthy).toBe(false);
  });

  it('accepts all valid study types', async () => {
    const validTypes = [
      'load_flow',
      'short_circuit',
      'fault',
      'arc_flash',
      'harmonic_analysis',
      'optimal_power_flow',
      'protection_coordination',
      'coordination',
      'motor_starting',
    ];

    for (const studyType of validTypes) {
      const res = await makeRequest('/api/v1/studies/run', {
        method: 'POST',
        headers: POST_HEADERS,
        body: JSON.stringify({ studyType, parameters: {}, dryRun: true }),
      });
      expect(res.status).toBe(200);
      const body = (await res.json()) as Record<string, unknown>;
      expect(body.status).toBe('dry_run');
      expect(body.studyType).toBe(studyType);
    }
  });

  it('returns security headers on all responses', async () => {
    const res = await makeRequest('/health');
    expect(res.status).toBe(200);
    expect(res.headers.get('X-Content-Type-Options')).toBe('nosniff');
    expect(res.headers.get('X-Frame-Options')).toBe('DENY');
    expect(res.headers.get('Content-Security-Policy')).toBeTruthy();
  });

  it('persists task to KV and returns status', async () => {
    const kv = mockKV();
    const env = {
      API_KEY_SECRET: TEST_KEY,
      RATE_LIMIT_KV: kv,
      TASK_STORE_KV: kv,
      METRICS_KV: kv,
      API_KEYS_KV: kv,
    };
    const res = await makeRequest('/api/v1/studies/run', {
      method: 'POST',
      headers: POST_HEADERS,
      body: JSON.stringify({ studyType: 'load_flow', parameters: {}, dryRun: true }),
    }, env);
    expect(res.status).toBe(200);
    const body = (await res.json()) as Record<string, unknown>;
    const taskId = body.taskId as string;

    const statusRes = await makeRequest(`/api/v1/studies/status/${taskId}`, {
      headers: { 'x-api-key': TEST_KEY },
    }, env);
    expect(statusRes.status).toBe(200);
    const statusBody = (await statusRes.json()) as Record<string, unknown>;
    expect(statusBody.status).toBe('dry_run');
    expect(statusBody.studyType).toBe('load_flow');
  });
});
