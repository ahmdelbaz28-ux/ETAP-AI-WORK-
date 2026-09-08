/**
 * Centralized API configuration facade.
 *
 * Re-exports modular subsystems:
 * - api-base-url: API endpoint resolution (API_BASE_URL, apiUrl)
 * - settings-crypto: Web Crypto encryption/decryption and secret field detection
 * - settings-cache: In-memory settings cache and localStorage persistence
 */

export {
  resolveApiBaseUrl,
  API_BASE_URL,
  apiUrl,
} from "./api-base-url";

export {
  SECRET_FIELDS,
  isSecretField,
  encryptSecret,
  decryptSecret,
  deobfuscateLegacy,
} from "./settings-crypto";

export {
  getCachedSettings,
  refreshSettingsCache,
  getDeobfuscatedSettings,
  setEncryptedSettings,
} from "./settings-cache";
