<<<<<<< HEAD
/*
 * Shared types for the worker.
 * Security additions: TRUSTED_ORIGINS, AUDIT_HMAC_SECRET, AUDIT_KV, IP_BLOCK_KV.
 */
export interface Env {
  // AI provider secrets
=======
/**
 * Shared types for the worker.
 * Kept in core/ so every module can import without circular deps.
 */
export interface Env {
  // AI provider secrets (only NVIDIA + OpenAI are used; see src/core/config.ts)
>>>>>>> origin/fix/scenario-tests-properly
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_MODEL?: string;
  NVIDIA_API_KEY?: string;
  NVIDIA_BASE_URL?: string;
  NVIDIA_MODEL?: string;
<<<<<<< HEAD
  RENDER_API_KEY?: string;
  RENDER_BASE_URL?: string;
  RENDER_MODEL?: string;
  ZENMUX_API_KEY?: string;
  ZENMUX_BASE_URL?: string;
  ZENMUX_MODEL?: string;
  FIREWORKS_API_KEY?: string;
  FIREWORKS_BASE_URL?: string;
  FIREWORKS_MODEL?: string;
  GITHUB_MODELS_API_KEY?: string;
  GITHUB_MODELS_BASE_URL?: string;
  GITHUB_MODELS_MODEL?: string;
  OPENMODEL_API_KEY?: string;
  OPENMODEL_BASE_URL?: string;
  OPENMODEL_MODEL?: string;
  MODAL_API_KEY?: string;
  MODAL_BASE_URL?: string;
  MODAL_MODEL?: string;
  BYNARA_API_KEY?: string;
  BYNARA_BASE_URL?: string;
  BYNARA_MODEL?: string;
  CLOUDFLARE_API_KEY?: string;
  CLOUDFLARE_ACCOUNT_ID?: string;
  CLOUDFLARE_BASE_URL?: string;
  CLOUDFLARE_MODEL?: string;
=======
>>>>>>> origin/fix/scenario-tests-properly

  // Mastra backend
  MASTRA_API_URL?: string;
  MASTRA_API_KEY?: string;

<<<<<<< HEAD
  // Engineering Service
=======
  // Engineering Service (Python computation engine)
>>>>>>> origin/fix/scenario-tests-properly
  ENGINEERING_SERVICE_URL?: string;
  ENGINEERING_SERVICE_API_KEY?: string;
  ENGINEERING_SERVICE_TIMEOUT_MS?: string;

  // Auth
  API_KEY_SECRET?: string;

<<<<<<< HEAD
  // Security — Trusted Origins (comma-separated, overrides DEFAULT_TRUSTED_ORIGINS)
  TRUSTED_ORIGINS?: string;

  // Security — HMAC secret for audit log integrity (generate: openssl rand -base64 32)
  AUDIT_HMAC_SECRET?: string;

=======
>>>>>>> origin/fix/scenario-tests-properly
  // Observability
  LANGWATCH_API_KEY?: string;
  HEALTH_CHECK_API_URL?: string;
  RATE_LIMIT_REQUESTS_PER_MINUTE?: string;

  // KV bindings
  RATE_LIMIT_KV?: KVNamespace;
  TASK_STORE_KV?: KVNamespace;
  METRICS_KV?: KVNamespace;
  API_KEYS_KV?: KVNamespace;
<<<<<<< HEAD
  AUDIT_KV?: KVNamespace;      // Dedicated audit log KV (separation of concerns)
  IP_BLOCK_KV?: KVNamespace;    // IP ban list
=======
>>>>>>> origin/fix/scenario-tests-properly

  // Queue binding
  STUDY_QUEUE?: Queue;
}

<<<<<<< HEAD
=======
// Minimal Queue interface for local testability
>>>>>>> origin/fix/scenario-tests-properly
export interface Queue {
  send(message: unknown): Promise<void>;
  sendBatch(messages: unknown[]): Promise<void>;
}

export interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

<<<<<<< HEAD
export interface KVNamespace {
  get(key: string, options?: { type?: 'text' | 'json' | 'arrayBuffer' | 'stream' }): Promise<unknown>;
=======
// Minimal KVNamespace interface for local testability
export interface KVNamespace {
  get(key: string, options?: { type?: 'text' | 'json' | 'arrayBuffer' | 'stream' }): Promise<unknown | null>;
>>>>>>> origin/fix/scenario-tests-properly
  put(
    key: string,
    value: string | ArrayBuffer | ReadableStream,
    options?: { expirationTtl?: number; expiration?: number }
  ): Promise<void>;
  delete(key: string): Promise<void>;
  list(options?: {
    prefix?: string;
    limit?: number;
    cursor?: string;
  }): Promise<{ keys: { name: string; expiration?: number }[]; list_complete: boolean; cursor?: string }>;
}
