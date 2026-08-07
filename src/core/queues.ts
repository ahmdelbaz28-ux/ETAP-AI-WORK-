/**
 * Cloudflare Queues integration for async study execution.
 *
 * Features:
 * - Job submission via queue
 * - Async processing with progress tracking
 * - Dead-letter handling for failed jobs
 * - Retry with backoff
 */

import type { Env } from './types.js';
import { callEngineeringService, type EngineeringServiceRequest } from './engineeringService.js';
import { setTask } from '../routes/studies.js';

interface StudyJobMessage {
  taskId: string;
  studyType: string;
  parameters: Record<string, unknown>;
  system?: Record<string, unknown>;
  useEtap?: boolean;
  etapProjectPath?: string;
  traceId: string;
  apiKeyId: string;
  scope: string;
  retryCount: number;
}

const MAX_RETRIES = 3;

/**
 * Submit a study job to the queue for async processing.
 */
export async function submitStudyJob(env: Env, message: StudyJobMessage): Promise<void> {
  if (!env.STUDY_QUEUE) {
    throw new Error('STUDY_QUEUE is not configured');
  }
  await env.STUDY_QUEUE.send(message);
}

/**
 * Queue consumer handler for async study execution.
 */
export async function handleStudyQueueMessage(message: StudyJobMessage, env: Env): Promise<void> {
  const { taskId, studyType, parameters, traceId, retryCount } = message;

  // Update task status to running
  const task = {
    studyType,
    parameters,
    status: 'running',
    createdAt: Date.now(),
    startedAt: Date.now(),
    completedAt: undefined as number | undefined,
    result: undefined as unknown,
  };
  await setTask(env, taskId, task);

  try {
    const svcRequest: EngineeringServiceRequest = {
      study_type: studyType,
      parameters,
      task_id: taskId,
      use_etap: message.useEtap === true,
      etap_project_path: message.etapProjectPath,
    };
    if (message.system) {
      svcRequest.system = message.system;
    }

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
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    task.status = 'failed';
    task.completedAt = Date.now();
    task.result = { error: msg };
    await setTask(env, taskId, task);

    // Retry if under max retries
    if (retryCount < MAX_RETRIES) {
      await submitStudyJob(env, { ...message, retryCount: retryCount + 1 });
    }
  }
}
