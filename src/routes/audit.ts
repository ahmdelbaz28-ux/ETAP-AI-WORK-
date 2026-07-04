/**
 * Audit logs route.
 */
import type { Env, ExecutionContext } from '../core/types.js';
import { jsonResponse, corsHeaders } from '../utils/response.js';
import { getAuditLogs } from '../utils/audit.js';

export async function handleAuditLogs(
  request: Request,
  env: Env,
  _ctx: ExecutionContext,
  _apiKeyId: string,
  _scope: string,
  traceId: string,
): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
  const date = new URL(request.url).searchParams.get('date') || undefined;
  const logs = await getAuditLogs(env, date);
  return jsonResponse(
    200,
    {
      logs: logs.slice(-100),
      count: logs.length,
      date: date || new Date().toISOString().split('T')[0],
      traceId,
    },
    corsHeaders(origin),
  );
}
