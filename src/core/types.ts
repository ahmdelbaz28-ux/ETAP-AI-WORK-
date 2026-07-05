/**
 * Shared types for the worker.
 * Kept in core/ so every module can import without circular deps.
 */
export interface Env {
  // AI provider secrets (NVIDIA + OpenAI are used; see src/core/config.ts)
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_MODEL?: string;
  NVIDIA_API_KEY?: string;
  NVIDIA_BASE_URL?: string;
  NVIDIA_MODEL?: string;

  // Mastra backend
  MASTRA_API_URL?: string;
  MASTRA_API_KEY?: string;

  // Engineering Service (Python computation engine)
  ENGINEERING_SERVICE_URL?: string;
  ENGINEERING_SERVICE_API_KEY?: string;
  ENGINEERING_SERVICE_TIMEOUT_MS?: string;

  // Auth
  API_KEY_SECRET?: string;

  // Observability
  LANGWATCH_API_KEY?: string;
  HEALTH_CHECK_API_URL?: string;
  RATE_LIMIT_REQUESTS_PER_MINUTE?: string;

  // KV bindings
  RATE_LIMIT_KV?: KVNamespace;
  TASK_STORE_KV?: KVNamespace;
  METRICS_KV?: KVNamespace;
  API_KEYS_KV?: KVNamespace;

  // Queue binding
  STUDY_QUEUE?: Queue;
}

// Minimal Queue interface for local testability
export interface Queue {
  send(message: unknown): Promise<void>;
  sendBatch(messages: unknown[]): Promise<void>;
}

export interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

// Minimal KVNamespace interface for local testability
export interface KVNamespace {
  // NOSONAR — typescript:S6571: `unknown | null` is technically simplified
  // to `unknown`, but kept for parity with the official @cloudflare/workers-types
  // KVNamespace signature so callers can copy-paste between local + prod.
  get(key: string, options?: { type?: 'text' | 'json' | 'arrayBuffer' | 'stream' }): Promise<unknown | null>;
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
