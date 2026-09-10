/**
 * Shared API fetch helper for AhmedETAP frontend.
 *
 * Consolidates agentsFetch and dashboardFetch into a single canonical apiFetch<T>.
 */

import { API_BASE_URL } from "./api-config";
import { authHeaders } from "./admin-fetch";

export interface ApiFetchOptions extends RequestInit {
  readonly timeoutMs?: number;
  readonly retries?: number;
}

function resolveHeaders(callerHeaders?: HeadersInit): Record<string, string> {
  const merged: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
  };
  if (callerHeaders instanceof Headers) {
    callerHeaders.forEach((v, k) => {
      merged[k] = v;
    });
  } else if (Array.isArray(callerHeaders)) {
    for (const [k, v] of callerHeaders) {
      merged[k] = v;
    }
  } else if (callerHeaders && typeof callerHeaders === "object") {
    Object.assign(merged, callerHeaders);
  }
  return merged;
}

function resolveSignal(userSignal?: AbortSignal | null, timeoutMs = 15000): AbortSignal | undefined {
  if (userSignal) return userSignal;
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(timeoutMs);
  }
  return undefined;
}

function backoffDelay(attempt: number): number {
  return Math.min(200 * 2 ** attempt, 2000);
}

async function parseHttpError(res: Response): Promise<Error> {
  const text = await res.text().catch(() => "");
  return new Error(`HTTP ${res.status}: ${text || res.statusText}`);
}

type AttemptResult<T> =
  | { ok: true; data: T }
  | { ok: false; retry: boolean; error: Error };

async function executeSingleAttempt<T>(
  url: string,
  init: ApiFetchOptions | undefined,
  headers: Record<string, string>,
  timeoutMs: number,
  canRetry: boolean,
): Promise<AttemptResult<T>> {
  try {
    const signal = resolveSignal(init?.signal, timeoutMs);
    const res = await fetch(url, { ...init, headers, signal });
    if (res.ok) {
      const data = (await res.json()) as T;
      return { ok: true, data };
    }
    const shouldRetry = res.status >= 500 && canRetry;
    const error = await parseHttpError(res);
    return { ok: false, retry: shouldRetry, error };
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError" && init?.signal?.aborted) {
      throw err;
    }
    const error = err instanceof Error ? err : new Error(String(err));
    const retry = canRetry && !error.message.startsWith("HTTP 4");
    return { ok: false, retry, error };
  }
}

export async function apiFetch<T>(path: string, init?: ApiFetchOptions): Promise<T> {
  const mergedHeaders = resolveHeaders(init?.headers);
  const timeoutMs = init?.timeoutMs ?? 15000;
  const maxRetries = init?.retries ?? 2;
  const method = (init?.method || "GET").toUpperCase();
  const isIdempotent = ["GET", "HEAD", "OPTIONS", "PUT", "DELETE"].includes(method);
  const url = `${API_BASE_URL}${path}`;

  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const canRetry = attempt < maxRetries && isIdempotent;
    const result = await executeSingleAttempt<T>(url, init, mergedHeaders, timeoutMs, canRetry);
    if (result.ok) {
      return result.data;
    }
    lastError = result.error;
    if (result.retry) {
      await new Promise((resolve) => setTimeout(resolve, backoffDelay(attempt)));
      continue;
    }
    throw lastError;
  }

  throw lastError ?? new Error(`Request to ${path} failed after retries`);
}
