/**
 * tests/unit/routes/agents.test.ts — Unit tests for Agent Chat & Grounded Direct-AI Fallback (P3).
 *
 * Verifies:
 * 1. getGroundedSystemPrompt loads the canonical prompt from prompts.json / prompts/
 *    and appends the Engineering Grounding Directive to prevent hallucination.
 * 2. Complete elimination of the legacy ungrounded 2-line system prompt.
 * 3. Correct promptHandle mapping across all registered agents in AGENT_REGISTRY.
 * 4. Response metadata includes executionMode: "grounded_direct_ai_fallback".
 * 5. Return HTTP 503 when no AI provider is configured.
 * 6. Return HTTP 502 when AI generation fails with failover.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  handleChat,
  getGroundedSystemPrompt,
  ENGINEERING_GROUNDING_DIRECTIVE,
} from '../../../src/routes/agents.js';
import {
  AGENT_REGISTRY,
  getAgentPromptHandle,
  listAgentIds,
} from '../../../src/core/agents.js';
import * as providersModule from '../../../src/core/providers.js';
import type { Env, ExecutionContext } from '../../../src/core/types.js';

describe('P3: Agent Prompt Grounding & Fallback Elimination', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('Prompt Grounding & Anti-Hallucination Directives', () => {
    it('grounds load-flow-agent with IEEE 3002.7 and anti-hallucination directive', async () => {
      const prompt = await getGroundedSystemPrompt('load-flow-agent');
      expect(prompt).toContain('Load Flow Analysis Agent');
      expect(prompt).toContain('IEEE 3002.7');
      expect(prompt).toContain('Newton-Raphson');
      expect(prompt).toContain(ENGINEERING_GROUNDING_DIRECTIVE);
      expect(prompt).toContain('ZERO HALLUCINATION & NO GUESSING');
      expect(prompt).toContain('NO ENGINE CONNECTED');
      // Assert legacy ungrounded prompt is eliminated
      expect(prompt).not.toContain(
        'Respond with professional engineering analysis. Be concise, accurate'
      );
    });

    it('grounds short-circuit-agent with IEC 60909 and anti-hallucination directive', async () => {
      const prompt = await getGroundedSystemPrompt('short-circuit-agent');
      expect(prompt).toContain('Short Circuit Analysis Agent');
      expect(prompt).toContain('IEC 60909');
      expect(prompt).toContain(ENGINEERING_GROUNDING_DIRECTIVE);
      expect(prompt).toContain('ZERO HALLUCINATION & NO GUESSING');
    });

    it('grounds arcflash-agent with IEEE 1584 and NFPA 70E', async () => {
      const prompt = await getGroundedSystemPrompt('arcflash-agent');
      expect(prompt).toContain('Arc Flash Hazard Analysis Agent');
      expect(prompt).toContain('IEEE 1584');
      expect(prompt).toContain(ENGINEERING_GROUNDING_DIRECTIVE);
    });

    it('grounds protection-agent with IEC 60255', async () => {
      const prompt = await getGroundedSystemPrompt('protection-agent');
      expect(prompt).toContain('Protection Coordination Agent');
      expect(prompt).toContain('IEC 60255');
      expect(prompt).toContain(ENGINEERING_GROUNDING_DIRECTIVE);
    });

    it('all registered agents have promptHandle and grounded system prompts', async () => {
      const ids = listAgentIds();
      expect(ids.length).toBeGreaterThanOrEqual(10);

      for (const id of ids) {
        const handle = getAgentPromptHandle(id);
        expect(handle).toBeDefined();
        expect(handle.length).toBeGreaterThan(0);
        expect(AGENT_REGISTRY[id].promptHandle).toBe(handle);

        const prompt = await getGroundedSystemPrompt(id);
        expect(prompt).toBeDefined();
        expect(prompt.length).toBeGreaterThan(200);
        expect(prompt).toContain(ENGINEERING_GROUNDING_DIRECTIVE);
        expect(prompt).toContain('ZERO HALLUCINATION & NO GUESSING');
      }
    });
  });

  describe('Direct-AI Fallback Execution Gate & Metadata', () => {
    const mockCtx: ExecutionContext = {
      waitUntil: vi.fn(),
      passThroughOnException: vi.fn(),
    };

    it('returns HTTP 503 when no AI provider is configured', async () => {
      const emptyEnv: Env = {};
      const req = new Request('http://localhost/api/v1/agents/load-flow-agent/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: 'Calculate load flow for 3-bus network' }],
        }),
      });

      const res = await handleChat(
        req,
        emptyEnv,
        mockCtx,
        'test-key',
        'admin',
        'load-flow-agent',
        'trace-p3-503'
      );

      expect(res.status).toBe(503);
      const data = (await res.json()) as Record<string, unknown>;
      expect(data.status).toBe(503);
      expect(data.message).toMatch(/No AI provider is configured/i);
    });

    it('executes runDirectAi with grounded prompt and returns executionMode metadata', async () => {
      const envWithProvider: Env = {
        OPENAI_API_KEY: 'sk-test-mock-key',
      };

      let capturedSystemPrompt = '';
      vi.spyOn(providersModule, 'generateWithFailover').mockImplementation(
        async (_env, system, _messages) => {
          capturedSystemPrompt = system;
          return {
            text: 'Grounding directive acknowledged. Missing parameters: base MVA, line impedances.',
            provider: 'openai',
            model: 'gpt-4o',
            latencyMs: 120,
            promptTokens: 450,
            completionTokens: 25,
            finishReason: 'stop',
          };
        }
      );

      const req = new Request('http://localhost/api/v1/agents/load-flow-agent/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: 'What are the required parameters for load flow?' }],
        }),
      });

      const res = await handleChat(
        req,
        envWithProvider,
        mockCtx,
        'test-key',
        'admin',
        'load-flow-agent',
        'trace-p3-200'
      );

      expect(res.status).toBe(200);
      const data = (await res.json()) as Record<string, unknown>;

      // Check execution mode metadata
      expect(data.executionMode).toBe('grounded_direct_ai_fallback');
      expect(data.agentId).toBe('load-flow-agent');
      expect(data.provider).toBe('openai');
      expect(data.model).toBe('gpt-4o');
      expect(data.text).toContain('Missing parameters');

      // Check captured system prompt contains standards and grounding directive
      expect(capturedSystemPrompt).toContain('Load Flow Analysis Agent');
      expect(capturedSystemPrompt).toContain('IEEE 3002.7');
      expect(capturedSystemPrompt).toContain('[ENGINEERING GROUNDING & CONVERSATIONAL CONSTRAINTS]');
      expect(capturedSystemPrompt).toContain('ZERO HALLUCINATION & NO GUESSING');
      expect(capturedSystemPrompt).not.toContain(
        'Respond with professional engineering analysis. Be concise, accurate'
      );
    });

    it('returns HTTP 502 when AI generation failover fails', async () => {
      const envWithProvider: Env = {
        OPENAI_API_KEY: 'sk-test-mock-key',
      };

      vi.spyOn(providersModule, 'generateWithFailover').mockRejectedValue(
        new Error('Upstream AI provider timeout (504)')
      );

      const req = new Request('http://localhost/api/v1/agents/load-flow-agent/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: 'Run analysis' }],
        }),
      });

      const res = await handleChat(
        req,
        envWithProvider,
        mockCtx,
        'test-key',
        'admin',
        'load-flow-agent',
        'trace-p3-502'
      );

      expect(res.status).toBe(502);
      const data = (await res.json()) as Record<string, unknown>;
      expect(data.status).toBe(502);
      expect(data.message).toContain('Upstream AI provider timeout');
    });
  });
});
