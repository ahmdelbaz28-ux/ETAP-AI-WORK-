/**
 * Provider listing and (now-disabled) dynamic registration.
 */
import type { Env, ExecutionContext } from '../core/types.js';
import { jsonResponse, errorResponse, corsHeaders } from '../utils/response.js';
import { listConfiguredProviders, getProviderLatency } from '../core/providers.js';
import { getAllCircuitHealth } from '../core/circuitBreaker.js';
import { recordAudit } from '../utils/audit.js';

export async function handleListProviders(
  request: Request,
  env: Env,
  _ctx: ExecutionContext,
  apiKeyId: string,
  scope: string,
  traceId: string,
): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
  const configured = listConfiguredProviders(env);
  const circuits = getAllCircuitHealth();
  const latency = getProviderLatency();

  const providers = configured.map((p) => {
    const circuit = circuits[p.name];
    const lat = latency[p.name];
    return {
      id: p.name,
      name: p.name === 'openai' ? 'OpenAI' : 'NVIDIA NIM',
      model: p.model,
      baseURL: p.baseURL,
      configured: true,
      healthy: circuit ? circuit.state === 'closed' || circuit.state === 'half-open' : true,
      circuit: circuit ? circuit.state : 'closed',
      avgLatencyMs: lat?.avgMs ?? 0,
      failureRate: lat?.failureRate ?? 0,
    };
  });

  providers.push({
    id: 'mastra',
    name: 'Mastra Backend',
    model: 'proxy',
    baseURL: env.MASTRA_API_URL || '',
    configured: !!env.MASTRA_API_URL,
    healthy: !!env.MASTRA_API_URL,
    circuit: 'closed',
    avgLatencyMs: 0,
    failureRate: 0,
  });

  recordAudit({
    timestamp: new Date().toISOString(),
    traceId,
    clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
    method: 'GET',
    path: '/api/v1/providers',
    statusCode: 200,
    userAgent: request.headers.get('user-agent') || 'unknown',
    action: 'LIST_PROVIDERS',
    authenticated: true,
    rateLimited: false,
    apiKeyId,
    scope,
  });

  return jsonResponse(200, { providers, traceId }, corsHeaders(origin));
}

/**
 * Hardening: dynamic provider registration is DISABLED.
 * Returns HTTP 410 Gone with an explanatory message.
 * To re-enable, restore the previous handler — see git history.
 */
export async function handleRegisterProvider(
  request: Request,
  _env: Env,
  _ctx: ExecutionContext,
  apiKeyId: string,
  scope: string,
  traceId: string,
): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
  recordAudit({
    timestamp: new Date().toISOString(),
    traceId,
    clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
    method: 'POST',
    path: '/api/v1/providers',
    statusCode: 410,
    userAgent: request.headers.get('user-agent') || 'unknown',
    action: 'PROVIDER_REGISTER_DISABLED',
    authenticated: true,
    rateLimited: false,
    apiKeyId,
    scope,
  });
  return errorResponse(
    410,
    'Dynamic provider registration is disabled in this build. Use wrangler secrets to add a provider.',
    traceId,
    corsHeaders(origin),
  );
}
