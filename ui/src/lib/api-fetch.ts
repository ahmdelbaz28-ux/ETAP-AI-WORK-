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

function shouldRetryError(err: Error, attempt: number, maxRetries: number, isIdempotent: boolean): boolean {
  if (attempt >= maxRetries || !isIdempotent) return false;
  return !err.message.startsWith("HTTP 4");
}

export async function apiFetch<T>(path: string, init?: ApiFetchOptions): Promise<T> {
  const mergedHeaders = resolveHeaders(init?.headers);
  const timeoutMs = init?.timeoutMs ?? 15000;
  const maxRetries = init?.retries ?? 2;
  const method = (init?.method || "GET").toUpperCase();
  const isIdempotent = ["GET", "HEAD", "OPTIONS", "PUT", "DELETE"].includes(method);

  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const signal = resolveSignal(init?.signal, timeoutMs);
      const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: mergedHeaders, signal });
      if (!res.ok) {
        if (res.status >= 500 && attempt < maxRetries && isIdempotent) {
          await new Promise((resolve) => setTimeout(resolve, backoffDelay(attempt)));
          continue;
        }
        throw await parseHttpError(res);
      }
      return (await res.json()) as T;
    } catch (err: unknown) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (err instanceof DOMException && err.name === "AbortError" && init?.signal?.aborted) {
        throw err;
      }
      if (shouldRetryError(lastError, attempt, maxRetries, isIdempotent)) {
        await new Promise((resolve) => setTimeout(resolve, backoffDelay(attempt)));
        continue;
      }
      throw lastError;
    }
  }

  throw lastError ?? new Error(`Request to ${path} failed after retries`);
}
