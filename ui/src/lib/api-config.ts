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
  const env = (import.meta as unknown as { env?: Record<string, string> }).env;
  if (env?.VITE_API_URL) return env.VITE_API_URL;

  // 2. On the HF Space, the UI is served from the same origin as the API.
  //    Detect this by checking if we're on *.hf.space.
  //    Use typeof window check to avoid ReferenceError during Vite build (Node.js).
  if (typeof window !== "undefined" && window.location?.hostname.endsWith(".hf.space")) {
    return ""; // same-origin — empty prefix so fetch('/api/v1/...') works
  }

  // 3. Last-resort default: the HF Space production API.
  //    Change this URL if the Space moves to a different name or host.
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

const SECRET_FIELDS = new Set([
  "API_KEY_SECRET",
  "JWT_SECRET_KEY",
  "OPENAI_API_KEY",
  "NVIDIA_API_KEY",
  "QWEN_API_KEY",
  "GLM_API_KEY",
  "ENGINEERING_SERVICE_API_KEY",
  "LANGWATCH_API_KEY",
  "SMITHERY_API_KEY",
  "HF_TOKEN",
  "GITHUB_TOKEN",
  "VERCEL_ACCESS_TOKEN",
  "VERCEL_PROJECT_ID",
  "REDIS_URL",
  "DATABASE_URL",
  "VAULT_TOKEN",
  "SMTP_USERNAME",
  "ETAP_LICENSE_PATH",
  "CUSTOM_API_KEY",
  "CUSTOM_OPENAI_API_KEY",
  "PROVIDER_OPENAI_KEY",
  "PROVIDER_ANTHROPIC_KEY",
  "PROVIDER_GEMINI_KEY",
  "PROVIDER_DEEPSEEK_KEY",
  "PROVIDER_GROQ_KEY",
  "PROVIDER_COHERE_KEY",
  "PROVIDER_HUGGINGFACE_KEY",
  "SCADA_API_KEY",
]);

/**
 * Secure encryption for sensitive settings using Web Crypto API (AES-GCM).
 * This replaces the weak XOR obfuscation with proper encryption.
 * 
 * The encryption key is derived from a user-specific salt stored in localStorage
 * combined with a device fingerprint, making it unique per user/device.
 * 
 * Note: This is client-side encryption for localStorage only. The actual API keys
 * are sent to the backend via secure HTTPS requests with proper authentication.
 */

// Generate or retrieve a persistent encryption key for this user/device
async function getEncryptionKey(): Promise<CryptoKey> {
  if (typeof window === "undefined" || !window.localStorage) {
    throw new Error("Encryption only available in browser environment");
  }

  // Get or create a salt for key derivation
  let salt = localStorage.getItem("etap-encryption-salt");
  if (!salt) {
    // Generate a new random salt
    const saltBytes = crypto.getRandomValues(new Uint8Array(16));
    salt = Array.from(saltBytes, b => b.toString(16).padStart(2, '0')).join('');
    localStorage.setItem("etap-encryption-salt", salt);
  }

  // Create a device fingerprint for additional entropy
  const fingerprint = await getDeviceFingerprint();
  
  // Derive key using PBKDF2
  const encoder = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    encoder.encode(fingerprint),
    "PBKDF2",
    false,
    ["deriveKey"]
  );

  const saltBytes = new Uint8Array(salt.match(/.{1,2}/g)!.map(byte => parseInt(byte, 16)));
  
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: saltBytes,
      iterations: 100000,
      hash: "SHA-256"
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false, // not extractable
    ["encrypt", "decrypt"]
  );
}

// Generate a device fingerprint for key derivation
async function getDeviceFingerprint(): Promise<string> {
  if (typeof window === "undefined") return "server";
  
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.textBaseline = "top";
    ctx.font = "14px Arial";
    ctx.fillText("ETAP fingerprint", 2, 2);
  }
  const canvasFingerprint = canvas.toDataURL();
  
  const components = [
    navigator.userAgent,
    navigator.language,
    screen.width + "x" + screen.height,
    new Date().getTimezoneOffset().toString(),
    canvasFingerprint,
  ];
  
  // Hash the components
  const encoder = new TextEncoder();
  const data = encoder.encode(components.join("|"));
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Encrypt a value using AES-GCM.
 * Returns a base64-encoded string containing: IV (12 bytes) + ciphertext + auth tag
 */
export async function encryptSecret(value: string): Promise<string> {
  if (!value) return "";
  
  try {
    const key = await getEncryptionKey();
    const encoder = new TextEncoder();
    const data = encoder.encode(value);
    
    // Generate a random IV (12 bytes for AES-GCM)
    const iv = crypto.getRandomValues(new Uint8Array(12));
    
    // Encrypt
    const encrypted = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv },
      key,
      data
    );
    
    // Combine IV + ciphertext
    const encryptedArray = new Uint8Array(encrypted);
    const combined = new Uint8Array(iv.length + encryptedArray.length);
    combined.set(iv);
    combined.set(encryptedArray, iv.length);
    
    // Return as base64
    return btoa(String.fromCharCode(...combined));
  } catch (error) {
    console.error("Failed to encrypt secret:", error);
    // Fallback: return original value (will be stored in plaintext but logged)
    return value;
  }
}

/**
 * Decrypt a value encrypted with encryptSecret.
 */
export async function decryptSecret(encryptedValue: string): Promise<string> {
  if (!encryptedValue) return "";
  
  try {
    const key = await getEncryptionKey();
    
    // Decode from base64
    const combined = new Uint8Array(
      atob(encryptedValue).split("").map(c => c.charCodeAt(0))
    );
    
    // Extract IV (first 12 bytes) and ciphertext
    const iv = combined.slice(0, 12);
    const ciphertext = combined.slice(12);
    
    // Decrypt
    const decrypted = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv },
      key,
      ciphertext
    );
    
    const decoder = new TextDecoder();
    return decoder.decode(decrypted);
  } catch (error) {
    console.error("Failed to decrypt secret:", error);
    // If decryption fails (e.g., key changed, corrupted data), return empty
    return "";
  }
}

/**
 * Synchronous fallback for backward compatibility with existing stored values.
 * This handles the old XOR-obfuscated values during migration.
 * @deprecated Use encryptSecret/decryptSecret instead
 */
function deobfuscateLegacy(value: string): string {
  if (!value) return "";
  try {
    const OBFUSCATION_KEY = "ETAP-SEC-2024-OBFUSCATION";
    const decoded = atob(value);
    let result = "";
    for (let i = 0; i < decoded.length; i++) {
      result += String.fromCodePoint(
        decoded.codePointAt(i)! ^ OBFUSCATION_KEY.codePointAt(i % OBFUSCATION_KEY.length)!,
      );
    }
    return result;
  } catch {
    return value;
  }
}

export async function getDeobfuscatedSettings(): Promise<Record<string, string>> {
  if (typeof window === "undefined" || !window.localStorage) return {};
  try {
    const stored = localStorage.getItem("etap-settings");
    if (!stored) return {};
    const parsed = JSON.parse(stored);
    const deobfuscated: Record<string, string> = {};
    
    for (const [k, v] of Object.entries(parsed)) {
      if (SECRET_FIELDS.has(k)) {
        // Try new AES-GCM decryption first
        try {
          deobfuscated[k] = await decryptSecret(v as string);
        } catch {
          // Fallback to legacy XOR deobfuscation for migration
          deobfuscated[k] = deobfuscateLegacy(v as string);
        }
      } else {
        deobfuscated[k] = v as string;
      }
    }
    return deobfuscated;
  } catch (error) {
    console.error("Failed to parse settings from localStorage:", error);
    return {};
  }
}

/**
 * Store settings with encryption for secret fields.
 * This should be used instead of directly writing to localStorage.
 */
export async function setEncryptedSettings(settings: Record<string, string>): Promise<void> {
  if (typeof window === "undefined" || !window.localStorage) return;
  
  try {
    const encrypted: Record<string, string> = {};
    
    for (const [k, v] of Object.entries(settings)) {
      if (SECRET_FIELDS.has(k) && v) {
        encrypted[k] = await encryptSecret(v);
      } else {
        encrypted[k] = v;
      }
    }
    
    localStorage.setItem("etap-settings", JSON.stringify(encrypted));
  } catch (error) {
    console.error("Failed to store encrypted settings:", error);
    throw error;
  }
}