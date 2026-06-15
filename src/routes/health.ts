/**
 * Health, root, and metrics routes.
 */
import type { Env, ExecutionContext } from '../core/types.js';
import { jsonResponse, corsHeaders } from '../utils/response.js';
import { listConfiguredProviders, getProviderLatency } from '../core/providers.js';
import { getAllCircuitHealth } from '../core/circuitBreaker.js';
import { composeMetrics, getApiMetrics, getPerKeyMetrics, getPerRouteMetrics, getTaskCount } from '../utils/metrics.js';
import { getAuditBufferLength } from '../utils/audit.js';
import { checkEngineeringServiceHealth } from '../core/engineeringService.js';

export async function handleRoot(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
  return jsonResponse(
    200,
    {
      service: 'ETAP AI Platform',
      version: '1.0.0',
      documentation: '/api/v1/docs',
      health: '/health',
      traceId: crypto.randomUUID(),
    },
    corsHeaders(origin)
  );
}

export async function handleHealth(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
  const providers = listConfiguredProviders(env).map((p) => p.name);
  const circuits = getAllCircuitHealth();
  const anyHealthy = providers.length > 0;

  const engHealth = await checkEngineeringServiceHealth(env);

  return jsonResponse(
    200,
    {
      ok: true,
      service: 'etap-ai-platform',
      version: '1.0.0',
      traceId: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      providers,
      circuits,
      anyProviderHealthy: anyHealthy,
      engineeringService: {
        configured: !!env.ENGINEERING_SERVICE_URL,
        healthy: engHealth.healthy,
        latencyMs: engHealth.latencyMs,
        error: engHealth.error,
      },
    },
    corsHeaders(origin)
  );
}

export async function handleMetrics(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
  return jsonResponse(
    200,
    {
      service: 'etap-ai-platform',
      version: '1.0.0',
      traceId: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      metrics: await composeMetrics(env),
      audit: { bufferSize: getAuditBufferLength() },
    },
    corsHeaders(origin)
  );
}
