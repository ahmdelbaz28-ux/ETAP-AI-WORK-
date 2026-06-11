/**
 * Engineering Service client
 * ==========================
 * Worker-side HTTP client for the Python Engineering Service.
 *
 * Features:
 * - Retry with exponential backoff
 * - Hard timeout via AbortController
 * - Structured error handling
 * - Trace ID propagation
 * - Circuit breaker integration (reuses existing circuit breaker)
 */

import type { Env } from './types.js';
import { CONFIG } from './config.js';
import { isCircuitOpen, recordProviderFailure, recordProviderSuccess } from './circuitBreaker.js';

export interface EngineeringServiceResult {
  success: boolean;
  data: Record<string, unknown>;
  warnings: string[];
  errors: string[];
  executionTimeSec: number;
  traceId: string;
  taskId: string | null;
  studyType: string;
  provider: string;
}

export interface EngineeringServiceRequest {
  study_type: string;
  system?: Record<string, unknown>;
  parameters?: Record<string, unknown>;
  task_id?: string;
  use_etap?: boolean;
  etap_project_path?: string;
}

function _getServiceUrl(env: Env): string | null {
  const url = env.ENGINEERING_SERVICE_URL;
  if (!url) return null;
  return url.replace(/\/$/, '');
}

function _getApiKey(env: Env): string | null {
  return env.ENGINEERING_SERVICE_API_KEY || null;
}

function _getTimeoutMs(): number {
  return CONFIG.ENGINEERING_SERVICE_TIMEOUT_MS;
}

function _getMaxRetries(): number {
  return CONFIG.ENGINEERING_SERVICE_MAX_RETRIES;
}

function _delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Check if the Engineering Service is configured.
 */
export function isEngineeringServiceConfigured(env: Env): boolean {
  return !!env.ENGINEERING_SERVICE_URL;
}

/**
 * Call the Engineering Service to run a study.
 *
 * Returns the study result on success, or throws on failure.
 * Integrates with the circuit breaker for the 'engineering-service' provider.
 */
export async function callEngineeringService(
  env: Env,
  request: EngineeringServiceRequest,
  traceId: string,
  signal?: AbortSignal
): Promise<EngineeringServiceResult> {
  const url = _getServiceUrl(env);
  if (!url) {
    throw new Error('Engineering Service is not configured (ENGINEERING_SERVICE_URL missing)');
  }

  if (isCircuitOpen('engineering-service')) {
    throw new Error('Engineering Service circuit breaker is OPEN');
  }

  const apiKey = _getApiKey(env);
  const endpoint = `${url}/api/v1/studies/run`;
  const timeoutMs = _getTimeoutMs();
  const maxRetries = _getMaxRetries();

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(new Error('engineering-service-timeout')), timeoutMs);

    if (signal) {
      if (signal.aborted) controller.abort(signal.reason);
      signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true });
    }

    try {
      const headers: Record<string, string> = {
        'content-type': 'application/json',
        'x-trace-id': traceId,
      };
      if (apiKey) {
        headers['x-api-key'] = apiKey;
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Engineering Service returned ${res.status}: ${text.slice(0, 200)}`);
      }

      const payload = (await res.json()) as EngineeringServiceResult;
      recordProviderSuccess('engineering-service', env);
      return payload;
    } catch (e) {
      clearTimeout(timeoutId);
      const err = e instanceof Error ? e : new Error(String(e));
      lastError = err;

      // Do not retry on timeouts or client disconnects — don't open circuit
      if (signal?.aborted || err.message.includes('engineering-service-timeout')) {
        throw err; // re-throw without circuit breaker impact
      }
      if (attempt < maxRetries) {
        await _delay(500 * Math.pow(2, attempt)); // 500ms, 1000ms, 2000ms
      }
    }
  }

  // All retries exhausted — open circuit
  recordProviderFailure('engineering-service', env);
  throw lastError || new Error('Engineering Service call failed after all retries');
}

/**
 * Health check the Engineering Service.
 */
export async function checkEngineeringServiceHealth(env: Env): Promise<{ healthy: boolean; latencyMs: number; error?: string }> {
  const url = _getServiceUrl(env);
  if (!url) {
    return { healthy: false, latencyMs: 0, error: 'Not configured' };
  }

  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${url}/health`, {
      method: 'GET',
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return { healthy: res.ok, latencyMs: Date.now() - start };
  } catch (e) {
    return { healthy: false, latencyMs: Date.now() - start, error: e instanceof Error ? e.message : String(e) };
  }
}
