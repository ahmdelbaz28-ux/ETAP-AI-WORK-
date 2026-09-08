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

export async function apiFetch<T>(path: string, init?: ApiFetchOptions): Promise<T> {
  const callerHeaders = init?.headers;
  const mergedHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
  };
  if (callerHeaders instanceof Headers) {
    callerHeaders.forEach((v, k) => {
      mergedHeaders[k] = v;
    });
  } else if (Array.isArray(callerHeaders)) {
    for (const [k, v] of callerHeaders) {
      mergedHeaders[k] = v;
    }
  } else if (callerHeaders && typeof callerHeaders === "object") {
    Object.assign(mergedHeaders, callerHeaders);
  }

  const timeoutMs = init?.timeoutMs ?? 15000;
  const maxRetries = init?.retries ?? 2;
  const method = (init?.method || "GET").toUpperCase();
  const isIdempotent = ["GET", "HEAD", "OPTIONS", "PUT", "DELETE"].includes(method);

  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const signal =
        init?.signal ??
        (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function"
          ? AbortSignal.timeout(timeoutMs)
          : undefined);
      const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: mergedHeaders, signal });
      if (!res.ok) {
        if (res.status >= 400 && res.status < 500) {
          const text = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
        }
        if (attempt < maxRetries && isIdempotent) {
          await new Promise((resolve) => setTimeout(resolve, Math.min(200 * 2 ** attempt, 2000)));
          continue;
        }
        const text = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
      }
      return (await res.json()) as T;
    } catch (err: unknown) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (err instanceof DOMException && err.name === "AbortError" && init?.signal?.aborted) {
        throw err;
      }
      if (attempt < maxRetries && isIdempotent && !(lastError.message.startsWith("HTTP 4"))) {
        await new Promise((resolve) => setTimeout(resolve, Math.min(200 * 2 ** attempt, 2000)));
        continue;
      }
      throw lastError;
    }
  }

  throw lastError ?? new Error(`Request to ${path} failed after retries`);
}
