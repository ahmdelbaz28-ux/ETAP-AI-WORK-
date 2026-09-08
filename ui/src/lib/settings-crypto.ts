/**
 * Settings Web Crypto & Obfuscation Utilities
 *
 * Provides client-side AES-GCM encryption/decryption for secrets stored in
 * localStorage, along with legacy XOR migration helpers.
 */

export const SECRET_FIELDS = new Set([
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

export function isSecretField(key: string): boolean {
  return (
    SECRET_FIELDS.has(key) ||
    key.endsWith("_KEY") ||
    key.endsWith("_TOKEN") ||
    key.endsWith("_SECRET") ||
    key.includes("API_KEY") ||
    (key.startsWith("PROVIDER_") && key.endsWith("_KEY"))
  );
}

// Generate or retrieve a persistent encryption key for this user/device
async function getEncryptionKey(): Promise<CryptoKey> {
  if (typeof window === "undefined" || !window.localStorage) {
    throw new Error("Encryption only available in browser environment");
  }

  let salt = localStorage.getItem("etap-encryption-salt");
  if (!salt) {
    const saltBytes = crypto.getRandomValues(new Uint8Array(16));
    salt = Array.from(saltBytes, (b) => b.toString(16).padStart(2, "0")).join("");
    localStorage.setItem("etap-encryption-salt", salt);
  }

  const fingerprint = await getDeviceFingerprint();

  const encoder = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    encoder.encode(fingerprint),
    "PBKDF2",
    false,
    ["deriveKey"],
  );

  const saltMatch = salt.match(/.{1,2}/g);
  if (!saltMatch) {
    throw new Error("Invalid salt format: expected hex string");
  }
  const saltBytes = new Uint8Array(saltMatch.map((byte) => Number.parseInt(byte, 16)));

  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: saltBytes,
      iterations: 100000,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

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
    `${screen.width}x${screen.height}`,
    new Date().getTimezoneOffset().toString(),
    canvasFingerprint,
  ];

  const encoder = new TextEncoder();
  const data = encoder.encode(components.join("|"));
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function encryptSecret(value: string): Promise<string> {
  if (!value) return "";

  try {
    const key = await getEncryptionKey();
    const encoder = new TextEncoder();
    const data = encoder.encode(value);

    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, data);

    const encryptedArray = new Uint8Array(encrypted);
    const combined = new Uint8Array(iv.length + encryptedArray.length);
    combined.set(iv);
    combined.set(encryptedArray, iv.length);

    return btoa(String.fromCodePoint(...combined));
  } catch (error) {
    console.error("Failed to encrypt secret:", error);
    return "";
  }
}

export async function decryptSecret(encryptedValue: string): Promise<string> {
  if (!encryptedValue) return "";

  try {
    const key = await getEncryptionKey();

    const combined = new Uint8Array(
      atob(encryptedValue)
        .split("")
        .map((c) => c.codePointAt(0) ?? 0),
    );

    const iv = combined.slice(0, 12);
    const ciphertext = combined.slice(12);

    const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ciphertext);

    const decoder = new TextDecoder();
    return decoder.decode(decrypted);
  } catch (error) {
    console.error("Failed to decrypt secret:", error);
    return "";
  }
}

function _getObfuscationKey(): string {
  const KEY_STORAGE_KEY = "etap_obf_key";
  let key = sessionStorage.getItem(KEY_STORAGE_KEY);
  if (!key) {
    const arr = new Uint8Array(32);
    crypto.getRandomValues(arr);
    key = Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
    sessionStorage.setItem(KEY_STORAGE_KEY, key);
  }
  return key;
}

const _LEGACY_OBFUSCATION_KEY = "ETAP-SEC-2024-OBFUSCATION";

export function deobfuscateLegacy(value: string): string {
  if (!value) return "";
  try {
    const newKey = _getObfuscationKey();
    const decoded = atob(value);
    let result = "";
    for (let i = 0; i < decoded.length; i++) {
      result += String.fromCodePoint(
        (decoded.codePointAt(i) ?? 0) ^ (newKey.codePointAt(i % newKey.length) ?? 0),
      );
    }
    if (result.length > 0 && /^[\x20-\x7E]+$/.test(result)) {
      return result;
    }
    let legacyResult = "";
    for (let i = 0; i < decoded.length; i++) {
      legacyResult += String.fromCodePoint(
        (decoded.codePointAt(i) ?? 0) ^
          (_LEGACY_OBFUSCATION_KEY.codePointAt(i % _LEGACY_OBFUSCATION_KEY.length) ?? 0),
      );
    }
    return legacyResult;
  } catch {
    return value;
  }
}
