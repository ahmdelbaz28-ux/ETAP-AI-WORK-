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
  //    Use typeof window check to avoid ReferenceError during Vite build (Node.js).
  if (typeof window !== 'undefined' && typeof window.location !== 'undefined' && window.location.hostname.endsWith('.hf.space')) {
    return ''  // same-origin — empty prefix so fetch('/api/v1/...') works
  }

  // 3. Last-resort default: the HF Space production API.
  //    Change this URL if the Space moves to a different name or host.
  return 'https://ahmdelbaz28-ahmedetap-platform.hf.space'
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

const SECRET_FIELDS = new Set([
  'API_KEY_SECRET', 'JWT_SECRET_KEY', 'OPENAI_API_KEY', 'NVIDIA_API_KEY',
  'QWEN_API_KEY', 'GLM_API_KEY', 'ENGINEERING_SERVICE_API_KEY',
  'LANGWATCH_API_KEY', 'SMITHERY_API_KEY', 'HF_TOKEN', 'GITHUB_TOKEN',
  'VERCEL_ACCESS_TOKEN', 'VERCEL_PROJECT_ID',
  'REDIS_URL', 'DATABASE_URL', 'VAULT_TOKEN',
  'SMTP_USERNAME', 'ETAP_LICENSE_PATH',
  'CUSTOM_API_KEY', 'CUSTOM_OPENAI_API_KEY',
  'PROVIDER_OPENAI_KEY', 'PROVIDER_ANTHROPIC_KEY', 'PROVIDER_GEMINI_KEY',
  'PROVIDER_DEEPSEEK_KEY', 'PROVIDER_GROQ_KEY', 'PROVIDER_COHERE_KEY',
  'PROVIDER_HUGGINGFACE_KEY',
  'SCADA_API_KEY',
])

const OBFUSCATION_KEY = 'ETAP-SEC-2024-OBFUSCATION'

export function deobfuscate(value: string): string {
  if (!value) return ''
  try {
    const decoded = atob(value)
    let result = ''
    for (let i = 0; i < decoded.length; i++) {
      result += String.fromCodePoint(decoded.codePointAt(i)! ^ OBFUSCATION_KEY.codePointAt(i % OBFUSCATION_KEY.length)!)
    }
    return result
  } catch {
    return value
  }
}

export function getDeobfuscatedSettings(): Record<string, string> {
  if (typeof window === 'undefined' || !window.localStorage) return {}
  try {
    const stored = localStorage.getItem('etap-settings')
    if (!stored) return {}
    const parsed = JSON.parse(stored)
    const deobfuscated: Record<string, string> = {}
    for (const [k, v] of Object.entries(parsed)) {
      deobfuscated[k] = SECRET_FIELDS.has(k) ? deobfuscate(v as string) : (v as string)
    }
    return deobfuscated
  } catch (error) {
    console.error('Failed to parse settings from localStorage:', error)
    return {}
  }
}
