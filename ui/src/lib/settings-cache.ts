/**
 * Synchronous and Asynchronous Settings Cache
 *
 * Provides an in-memory cached view of decrypted settings stored in localStorage.
 */

import {
  isSecretField,
  encryptSecret,
  decryptSecret,
  deobfuscateLegacy,
} from "./settings-crypto";

let _cachedSettings: Record<string, string> = {};
let _cacheInitialized = false;

function _initCacheSync(): Record<string, string> {
  if (typeof window === "undefined" || !window.localStorage) return {};
  try {
    const stored = localStorage.getItem("etap-settings");
    if (!stored) return {};
    const parsed = JSON.parse(stored);
    const result: Record<string, string> = {};
    for (const [k, v] of Object.entries(parsed)) {
      if (isSecretField(k)) {
        result[k] = deobfuscateLegacy(v as string);
      } else {
        result[k] = v as string;
      }
    }
    return result;
  } catch {
    return {};
  }
}

export function getCachedSettings(): Record<string, string> {
  if (!_cacheInitialized) {
    _cachedSettings = _initCacheSync();
    _cacheInitialized = true;
  }
  return _cachedSettings;
}

export async function refreshSettingsCache(): Promise<void> {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    const stored = localStorage.getItem("etap-settings");
    if (!stored) return;
    const parsed = JSON.parse(stored);
    const result: Record<string, string> = {};
    for (const [k, v] of Object.entries(parsed)) {
      if (isSecretField(k)) {
        try {
          result[k] = await decryptSecret(v as string);
        } catch {
          result[k] = deobfuscateLegacy(v as string);
        }
      } else {
        result[k] = v as string;
      }
    }
    _cachedSettings = result;
    _cacheInitialized = true;
  } catch {
    _cachedSettings = _initCacheSync();
    _cacheInitialized = true;
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
      if (isSecretField(k)) {
        try {
          deobfuscated[k] = await decryptSecret(v as string);
        } catch {
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

export async function setEncryptedSettings(settings: Record<string, string>): Promise<void> {
  if (typeof window === "undefined" || !window.localStorage) return;

  try {
    const encrypted: Record<string, string> = {};

    for (const [k, v] of Object.entries(settings)) {
      if (isSecretField(k) && v) {
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
