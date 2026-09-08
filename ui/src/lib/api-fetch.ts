/**
 * Shared API fetch helper for AhmedETAP frontend.
 *
 * Consolidates agentsFetch and dashboardFetch into a single canonical apiFetch<T>.
 */

import { API_BASE_URL } from "./api-config";
import { authHeaders } from "./admin-fetch";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
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

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: mergedHeaders });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}
