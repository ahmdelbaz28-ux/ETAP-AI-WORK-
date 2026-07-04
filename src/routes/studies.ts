/**
 * Studies run and status routes.
 *
 * PRODUCTION CHANGE: All engineering studies now route through the Python
 * Engineering Service (real computation) instead of LLM hallucination.
 * LLM fallback is REMOVED for studies. Chat/explanation still uses LLM.
 */
import type { Env, ExecutionContext } from '../core/types.js';
import { jsonResponse, errorResponse, corsHeaders } from '../utils/response.js';
import { recordAudit } from '../utils/audit.js';
import { bumpApiMetric } from '../utils/metrics.js';
import { CONFIG } from '../core/config.js';
import {
  callEngineeringService,
  isEngineeringServiceConfigured,
  type EngineeringServiceRequest,
} from '../core/engineeringService.js';

interface TaskRecord {
  studyType: string;
  parameters: unknown;
  status: string;
  createdAt: number;
  startedAt?: number;
  completedAt?: number;
  result?: unknown;
}

export async function getTask(env: Env, taskId: string): Promise<TaskRecord | null> {
  if (!env.TASK_STORE_KV) return null;
  try {
    const raw = (await env.TASK_STORE_KV.get(`task:${taskId}`, {
      type: 'json',
    })) as TaskRecord | null;
    if (raw && typeof raw === 'object' && 'studyType' in raw) return raw;
  } catch {
    // silent
  }
  return null;
}

export async function setTask(env: Env, taskId: string, task: TaskRecord): Promise<void> {
  if (!env.TASK_STORE_KV) return;
  try {
    await env.TASK_STORE_KV.put(`task:${taskId}`, JSON.stringify(task), {
      expirationTtl: CONFIG.TASK_TTL_SECONDS,
    });
  } catch {
    // silent
  }
}

const VALID_STUDY_TYPES = [
  'load_flow',
  'short_circuit',
  'fault',
  'arc_flash',
  'harmonic_analysis',
  'optimal_power_flow',
  'protection_coordination',
  'coordination',
  'motor_starting',
  'etap_load_flow',
  'etap_short_circuit',
  'etap_arc_flash',
  'etap_harmonic_analysis',
  'etap_optimal_power_flow',
  'etap_motor_starting',
  'etap_protection_coordination',
];

export async function handleStudyRun(
  request: Request,
  env: Env,
  _ctx: ExecutionContext,
  apiKeyId: string,
  scope: string,
  traceId: string,
): Promise<Response> {
  const origin = request.headers.get('origin') || '*';

  let body: {
    studyType?: string;
    parameters?: Record<string, unknown>;
    dryRun?: boolean;
    system?: Record<string, unknown>;
    useEtap?: boolean;
    etapProjectPath?: string;
  } = {};
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return errorResponse(400, 'Invalid JSON body', traceId, corsHeaders(origin));
  }

  const studyType = body.studyType;
  const parameters = body.parameters || {};
  if (!studyType) {
    return errorResponse(400, 'studyType is required', traceId, corsHeaders(origin));
  }
  if (!VALID_STUDY_TYPES.includes(studyType)) {
    return errorResponse(
      400,
      `Invalid studyType. Must be one of: ${VALID_STUDY_TYPES.join(', ')}`,
      traceId,
      corsHeaders(origin),
    );
  }

  const taskId = traceId;
  const task: TaskRecord = { studyType, parameters, status: 'queued', createdAt: Date.now() };
  await setTask(env, taskId, task);

  // Dry-run: validate inputs without executing computation (no Engineering Service needed)
  if (body.dryRun === true) {
    task.status = 'dry_run';
    task.startedAt = Date.now();
    task.completedAt = Date.now();
    task.result = {
      dryRun: true,
      message: 'Dry-run mode: study parameters validated but no computation executed.',
      studyType,
      parameters,
    };
    await setTask(env, taskId, task);
    bumpApiMetric('studyCompleted');
    recordAudit({
      timestamp: new Date().toISOString(),
      traceId,
      clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
      method: 'POST',
      path: '/api/v1/studies/run',
      statusCode: 200,
      userAgent: request.headers.get('user-agent') || 'unknown',
      action: 'STUDY_RUN_DRY',
      authenticated: true,
      rateLimited: false,
      apiKeyId,
      scope,
      details: { studyType, taskId },
    });
    return jsonResponse(
      200,
      {
        studyType,
        status: 'dry_run',
        message: 'Dry-run successful. Study parameters validated.',
        taskId,
        parameters,
        statusUrl: `/api/v1/studies/status/${taskId}`,
        traceId,
      },
      corsHeaders(origin),
    );
  }

  // --- PRODUCTION PATH: Engineering Service ---
  if (!isEngineeringServiceConfigured(env)) {
    task.status = 'failed';
    await setTask(env, taskId, task);
    bumpApiMetric('studyFailed');
    bumpApiMetric('errors');
    recordAudit({
      timestamp: new Date().toISOString(),
      traceId,
      clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
      method: 'POST',
      path: '/api/v1/studies/run',
      statusCode: 503,
      userAgent: request.headers.get('user-agent') || 'unknown',
      action: 'STUDY_RUN_NO_ENGINE',
      authenticated: true,
      rateLimited: false,
      apiKeyId,
      scope,
      details: { studyType, error: 'Engineering Service not configured' },
    });
    return errorResponse(
      503,
      'Engineering Service is not configured. Set ENGINEERING_SERVICE_URL to enable real computation.',
      traceId,
      corsHeaders(origin),
    );
  }

  // Real computation via Engineering Service
  task.status = 'running';
  task.startedAt = Date.now();
  await setTask(env, taskId, task);

  const svcRequest: EngineeringServiceRequest = {
    study_type: studyType,
    parameters,
    task_id: taskId,
    use_etap: body.useEtap === true,
    etap_project_path: body.etapProjectPath || undefined,
  };
  if (body.system) {
    svcRequest.system = body.system;
  }

  try {
    const result = await callEngineeringService(env, svcRequest, traceId);

    task.status = result.success ? 'completed' : 'failed';
    task.completedAt = Date.now();
    task.result = {
      data: result.data,
      warnings: result.warnings,
      errors: result.errors,
      executionTimeSec: result.executionTimeSec,
      provider: result.provider,
      traceId: result.traceId,
    };
    await setTask(env, taskId, task);

    if (result.success) {
      bumpApiMetric('studyCompleted');
    } else {
      bumpApiMetric('studyFailed');
      bumpApiMetric('errors');
    }

    recordAudit({
      timestamp: new Date().toISOString(),
      traceId,
      clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
      method: 'POST',
      path: '/api/v1/studies/run',
      statusCode: result.success ? 200 : 502,
      userAgent: request.headers.get('user-agent') || 'unknown',
      action: 'STUDY_RUN_ENGINE',
      authenticated: true,
      rateLimited: false,
      apiKeyId,
      scope,
      latencyMs: Math.round(result.executionTimeSec * 1000),
      details: { studyType, taskId, provider: result.provider, success: result.success },
    });

    if (!result.success) {
      return errorResponse(
        502,
        `Engineering computation failed: ${result.errors.join('; ') || 'Unknown error'}`,
        traceId,
        corsHeaders(origin),
      );
    }

    return jsonResponse(
      200,
      {
        studyType,
        status: 'completed',
        message: 'Study completed via real engineering computation.',
        taskId,
        parameters,
        result: {
          data: result.data,
          warnings: result.warnings,
          executionTimeSec: result.executionTimeSec,
          provider: result.provider,
        },
        statusUrl: `/api/v1/studies/status/${taskId}`,
        traceId,
      },
      corsHeaders(origin),
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Engineering Service call failed';
    task.status = 'failed';
    task.completedAt = Date.now();
    task.result = { error: msg };
    await setTask(env, taskId, task);
    bumpApiMetric('studyFailed');
    bumpApiMetric('errors');

    recordAudit({
      timestamp: new Date().toISOString(),
      traceId,
      clientIp: request.headers.get('cf-connecting-ip') || 'unknown',
      method: 'POST',
      path: '/api/v1/studies/run',
      statusCode: 502,
      userAgent: request.headers.get('user-agent') || 'unknown',
      action: 'STUDY_RUN_ENGINE_ERROR',
      authenticated: true,
      rateLimited: false,
      apiKeyId,
      scope,
      details: { studyType, taskId, error: msg },
    });

    return errorResponse(502, `Engineering Service error: ${msg}`, traceId, corsHeaders(origin));
  }
}

export async function handleStudyStatus(
  request: Request,
  env: Env,
  _ctx: ExecutionContext,
  _apiKeyId: string,
  _scope: string,
  traceId: string,
  taskId: string,
): Promise<Response> {
  const origin = request.headers.get('origin') || '*';
  const task = await getTask(env, taskId);
  if (!task) {
    return errorResponse(404, `Task "${taskId}" not found`, traceId, corsHeaders(origin));
  }
  return jsonResponse(
    200,
    {
      studyType: task.studyType,
      parameters: task.parameters,
      status: task.status,
      createdAt: task.createdAt,
      startedAt: task.startedAt,
      completedAt: task.completedAt,
      result: task.result,
      taskId,
      traceId,
    },
    corsHeaders(origin),
  );
}
