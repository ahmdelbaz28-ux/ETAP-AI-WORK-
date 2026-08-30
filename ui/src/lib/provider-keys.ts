/**
 * Provider Keys API client (P7a — Providers & API Keys)
 * ======================================================
 * Talks to the EXISTING backend settings API (api/settings.py backed by
 * services/api_key_store.py). NO new endpoints are introduced by P7a.
 *
 * Backend contract (pre-existing):
 *   GET    /api/v1/settings/keys              — list all keys (masked)
 *   POST   /api/v1/settings/keys/{provider}   — save/update a key
 *   DELETE /api/v1/settings/keys/{provider}   — delete a key
 *   POST   /api/v1/settings/keys/{provider}/test     — backend-side key test
 *   POST   /api/v1/settings/keys/{provider}/activate — enable/disable
 *
 * SECURITY (P7a requirements):
 *   - Provider API keys are stored server-side (AES-256-GCM encrypted
 *     SQLite). The browser NEVER persists them: no localStorage, no
 *     sessionStorage, no Zustand persisted state.
 *   - saveProviderKey sends the key in the JSON request BODY — never in the
 *     URL or query string (URLs are logged by proxies and access logs).
 *   - The backend only ever returns masked keys (api_key_masked) — plaintext
 *     keys never travel back to the frontend after being saved.
 *   - "Test connection" is executed by the backend against the provider —
 *     the browser never contacts provider APIs directly.
 */

import { request } from "./api";

/** Masked key configuration as returned by the backend (never plaintext). */
export interface ProviderKeyConfig {
  provider: string;
  /** Masked representation, e.g. "sk-***...xyz". */
  api_key_masked: string;
  api_key_set: boolean;
  base_url: string | null;
  model_name: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProviderKeysResponse {
  success: boolean;
  data: Record<string, ProviderKeyConfig>;
  providers: string[];
}

export interface ProviderKeyTestResult {
  success: boolean;
  message: string;
  model?: string;
}

export interface SaveProviderKeyInput {
  api_key: string;
  base_url?: string;
  model_name?: string;
  is_active?: boolean;
}

export interface SaveProviderKeyResponse {
  success: boolean;
  data: ProviderKeyConfig | null;
  message: string;
}

/** List all stored provider keys (masked — backend never returns plaintext). */
export async function listProviderKeys(): Promise<ProviderKeysResponse> {
  return request<ProviderKeysResponse>("/api/v1/settings/keys");
}

/**
 * Save/update a provider key. The key travels in the JSON body only —
 * never in the URL/query string.
 */
export async function saveProviderKey(
  provider: string,
  input: SaveProviderKeyInput,
): Promise<SaveProviderKeyResponse> {
  return request<SaveProviderKeyResponse>(
    `/api/v1/settings/keys/${encodeURIComponent(provider)}`,
    {
      method: "POST",
      body: JSON.stringify({
        api_key: input.api_key,
        ...(input.base_url ? { base_url: input.base_url } : {}),
        ...(input.model_name ? { model_name: input.model_name } : {}),
        ...(input.is_active !== undefined ? { is_active: input.is_active } : {}),
      }),
    },
  );
}

/** Delete a stored provider key permanently. */
export async function deleteProviderKey(
  provider: string,
): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(
    `/api/v1/settings/keys/${encodeURIComponent(provider)}`,
    { method: "DELETE" },
  );
}

/**
 * Test a stored key. The backend performs the minimal provider API call —
 * no provider request is made from the browser.
 */
export async function testProviderKey(
  provider: string,
): Promise<{ success: boolean; data: ProviderKeyTestResult }> {
  return request<{ success: boolean; data: ProviderKeyTestResult }>(
    `/api/v1/settings/keys/${encodeURIComponent(provider)}/test`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

/** Enable or disable a stored key without deleting it. */
export async function activateProviderKey(
  provider: string,
  isActive: boolean,
): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(
    `/api/v1/settings/keys/${encodeURIComponent(provider)}/activate`,
    {
      method: "POST",
      body: JSON.stringify({ is_active: isActive }),
    },
  );
}
