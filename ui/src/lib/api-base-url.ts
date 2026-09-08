/**
 * API Base URL and Endpoint Resolution
 *
 * Resolves the backend API base URL based on build environment,
 * origin hostname, or default production HF Space.
 */

export function resolveApiBaseUrl(): string {
  // 1. Explicit env var wins (set at build time)
  const env = (import.meta as unknown as { env?: Record<string, string> }).env;
  if (env?.VITE_API_URL) return env.VITE_API_URL;

  // 2. On HF Space or local dev (localhost / 127.0.0.1), UI uses same-origin / Vite proxy.
  //    Use typeof window check to avoid ReferenceError during Vite build (Node.js).
  if (
    typeof window !== "undefined" &&
    (window.location?.hostname.endsWith(".hf.space") ||
      window.location?.hostname === "localhost" ||
      window.location?.hostname === "127.0.0.1" ||
      window.location?.hostname === "0.0.0.0")
  ) {
    return ""; // same-origin — empty prefix so fetch('/api/v1/...') works
  }

  // 3. Last-resort default: the HF Space production API.
  return "https://ahmdelbaz28-ahmedetap-platform.hf.space";
}

export const API_BASE_URL = resolveApiBaseUrl();

/**
 * Build a full API URL from a path.
 * Example: apiUrl('/api/v1/auth/login') → 'https://...hf.space/api/v1/auth/login'
 *          or '/api/v1/auth/login' (same-origin)
 */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
