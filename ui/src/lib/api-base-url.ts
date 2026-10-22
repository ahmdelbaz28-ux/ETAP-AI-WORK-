/**
 * API Base URL and Endpoint Resolution
 *
 * Resolves the backend API base URL based on build environment,
 * origin hostname, or default production HF Space.
 */

const PROD_HF_SPACE_URL = "https://ahmdelbaz28-ahmedetap-platform.hf.space";

export function resolveApiBaseUrl(customEnv?: Record<string, string | undefined>): string {
  const metaEnv = (import.meta as unknown as { env?: Record<string, string | undefined> })?.env ?? {};
  const globalProc =
    typeof globalThis !== "undefined"
      ? (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process
      : undefined;
  const procEnv = globalProc?.env ?? {};
  const env = customEnv || { ...metaEnv, ...procEnv };
  const isStaging =
    env?.MODE === "staging" ||
    (typeof window !== "undefined" && window.location?.hostname.includes("staging"));

  // 1. Explicit env var wins (set at build time or runtime)
  if (env?.VITE_API_URL && env.VITE_API_URL.trim() !== "") {
    const rawUrl = env.VITE_API_URL.trim();
    // Fail-Closed: Guard against accidental production routing from Staging
    if (isStaging && rawUrl.includes("ahmdelbaz28-ahmedetap-platform.hf.space")) {
      console.error(
        "[API GUARD] Rejecting production API fallback in Staging deployment! VITE_API_URL must point to dedicated Staging backend."
      );
      return "";
    }
    return rawUrl;
  }

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

  // 3. Strict Staging Guard: Never silently fall back to production HF Space on Staging hostnames
  if (isStaging) {
    console.error(
      "[API GUARD] Running on Staging host without explicit VITE_API_URL. Refusing to fall back to production API."
    );
    return "";
  }

  // 4. Last-resort default: production HF Space API (for standalone prod preview only).
  return PROD_HF_SPACE_URL;
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
