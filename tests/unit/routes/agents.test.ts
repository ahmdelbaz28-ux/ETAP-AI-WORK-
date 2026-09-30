/**
 * tests/unit/routes/agents.test.ts — M4.3: Fail-Closed Agent Chat Pipeline.
 *
 * Verifies:
 * 1. The raw direct-AI fallback is GONE (no runDirectAi / grounding directive /
 *    getGroundedSystemPrompt exports) — capability unavailable ⇒
 *    SPECIALIZED_EXECUTION_UNAVAILABLE (HTTP 503), never a raw LLM answer.
 * 2. The capability-preserving Mastra proxy remains the only downstream path
 *    and returns 200 when reachable.
 * 3. Prompt-handle mapping stays intact across all registered agents.
 * 4. Request validation (400 invalid JSON) and agent lookup (404) unchanged.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { handleChat } from '../../../src/routes/agents.js';
import * as routesAgents from '../../../src/routes/agents.js';
import {
  AGENT_REGISTRY,
  getAgentPromptHandle,
  listAgentIds,
} from '../../../src/core/agents.js';
import type { Env, ExecutionContext } from '../../../src/core/types.js';

describe('P3: Agent Prompt Grounding & Fallback Elimination', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function chatRequest(body: unknown): Request {
    return new Request('http://localhost/api/v1/agents/load-flow-agent/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  const VALID_BODY = {
    messages: [{ role: 'user', content: 'What are the required parameters for load flow?' }],
  };

  const mockCtx: ExecutionContext = {
    waitUntil: vi.fn(),
    passThroughOnException: vi.fn(),
  };

  describe('Fallback elimination (module surface)', () => {
    it('no longer exports the raw fallback surface', () => {
      const mod = routesAgents as Record<string, unknown>;
      expect(mod.getGroundedSystemPrompt).toBeUndefined();
      expect(mod.ENGINEERING_GROUNDING_DIRECTIVE).toBeUndefined();
      expect(mod.runDirectAi).toBeUndefined();
    });

    it('all registered agents still have a promptHandle mapping', () => {
      const ids = listAgentIds();
      expect(ids.length).toBeGreaterThanOrEqual(10);
      for (const id of ids) {
        const handle = getAgentPromptHandle(id);
        expect(handle).toBeDefined();
        expect(handle.length).toBeGreaterThan(0);
        expect(AGENT_REGISTRY[id].promptHandle).toBe(handle);
      }
    });
  });

  describe('SPECIALIZED_EXECUTION_UNAVAILABLE fail-closed path', () => {
    it('returns HTTP 503 with the unified code when Mastra is not configured', async () => {
      const res = await handleChat(chatRequest(VALID_BODY), {}, mockCtx, 'k1', 'admin', 'load-flow-agent', 'trace-m4-503a');
      expect(res.status).toBe(503);
      const data = (await res.json()) as Record<string, unknown>;
      expect(data.status).toBe(503);
      expect(data.code).toBe('SPECIALIZED_EXECUTION_UNAVAILABLE');
      expect(String(data.message)).toMatch(/fail-closed/i);
      expect(data.agentId).toBe('load-flow-agent');
    });

    it('returns HTTP 503 when the Mastra proxy is unreachable (fetch throws)', async () => {
      const env: Env = { MASTRA_API_URL: 'https://mastra.invalid' };
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')));

      const res = await handleChat(chatRequest(VALID_BODY), env, mockCtx, 'k1', 'admin', 'load-flow-agent', 'trace-m4-503b');

      expect(res.status).toBe(503);
      const data = (await res.json()) as Record<string, unknown>;
      expect(data.code).toBe('SPECIALIZED_EXECUTION_UNAVAILABLE');
    });

    it('returns HTTP 503 when the Mastra proxy responds with an error status', async () => {
      const env: Env = { MASTRA_API_URL: 'https://mastra.invalid' };
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 502 })));

      const res = await handleChat(chatRequest(VALID_BODY), env, mockCtx, 'k1', 'admin', 'load-flow-agent', 'trace-m4-503c');

      expect(res.status).toBe(503);
      const data = (await res.json()) as Record<string, unknown>;
      expect(data.code).toBe('SPECIALIZED_EXECUTION_UNAVAILABLE');
    });
  });

  describe('Capability-preserving proxy path', () => {
    it('proxies successful Mastra responses and stamps the traceId', async () => {
      const env: Env = { MASTRA_API_URL: 'https://mastra.example', MASTRA_API_KEY: 'mk' };
      const proxyBody = { text: 'Engine-backed answer', provider: 'mastra' };
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(proxyBody), { status: 200, headers: { 'content-type': 'application/json' } }),
      );
      vi.stubGlobal('fetch', fetchMock);

      const res = await handleChat(chatRequest(VALID_BODY), env, mockCtx, 'k1', 'admin', 'load-flow-agent', 'trace-m4-200');

      expect(res.status).toBe(200);
      const data = (await res.json()) as Record<string, unknown>;
      expect(data.text).toBe('Engine-backed answer');
      expect(data.traceId).toBe('trace-m4-200');
      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe('https://mastra.example/api/agents/load-flow-agent/generate');
      expect((init.headers as Record<string, string>)['x-api-key']).toBe('mk');
    });
  });

  describe('Unchanged request validation', () => {
    it('returns HTTP 400 for an invalid JSON body', async () => {
      const req = new Request('http://localhost/api/v1/agents/load-flow-agent/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: '{not-json',
      });

      const res = await handleChat(req, {}, mockCtx, 'k1', 'admin', 'load-flow-agent', 'trace-m4-400');
      expect(res.status).toBe(400);
    });

    it('returns HTTP 404 for an unknown agent', async () => {
      const res = await handleChat(chatRequest(VALID_BODY), {}, mockCtx, 'k1', 'admin', 'does-not-exist', 'trace-m4-404');
      expect(res.status).toBe(404);
    });
  });
});
