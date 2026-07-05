/**
 * Centralized API configuration.
 *
 * The API base URL is resolved once at module load time and shared across
 * the entire UI. This avoids duplicating the resolution logic in api.ts,
 * useAuth.tsx, and individual page components.
 *
 * Resolution order:
 *   1. VITE_API_URL environment variable (set at build time via .env or
 *      Vercel project settings). This is the primary override — use it
 *      to point the UI at a different backend without editing code.
 *   2. Same-origin when the UI is served from *.hf.space (the HF Space
 *      container serves both the API and the UI from the same origin).
 *   3. The canonical HF Space production URL as a last-resort default
 *      (used when the UI is deployed on Vercel or any other static host
 *      without VITE_API_URL set).
 *
 * To change the backend URL:
 *   - For local dev: create ui/.env.local with VITE_API_URL=http://localhost:8000
 *   - For Vercel: set VITE_API_URL in the Vercel project environment variables
 *   - For HF Space: no config needed (same-origin is detected automatically)
 */

function resolveApiBaseUrl(): string {
  // 1. Explicit env var wins (set at build time)
  const env = (import.meta as unknown as { env?: Record<string, string> }).env
  if (env?.VITE_API_URL) return env.VITE_API_URL

  // 2. On the HF Space, the UI is served from the same origin as the API.
  //    Detect this by checking if we're on *.hf.space.
  if (typeof window !== 'undefined' && window.location.hostname.endsWith('.hf.space')) {
    return ''  // same-origin — empty prefix so fetch('/api/v1/...') works
  }

  // 3. Last-resort default: the HF Space production API.
  //    Change this URL if the Space moves to a different name or host.
  return 'https://ahmdelbaz28-ahmedetap.hf.space'
}

export const API_BASE_URL = resolveApiBaseUrl()

/**
 * Build a full API URL from a path.
 * Example: apiUrl('/api/v1/auth/login') → 'https://...hf.space/api/v1/auth/login'
 *          or '/api/v1/auth/login' (same-origin)
 */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}
