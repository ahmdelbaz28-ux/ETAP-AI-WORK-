/**
 * Canonical utilities for LLM streaming, SSE consumption, and secret redaction.
 */

const SECRET_KEY_RE = /(api[_-]?key|secret|token|password|authorization|credential)/i;
const SECRET_STRING_RE = /(?:sk-[a-zA-Z0-9_-]{16,}|Bearer\s+[a-zA-Z0-9._-]+)/gi;

/**
 * Checks if a key name suggests sensitive content.
 */
export function isSecretKey(key: string): boolean {
  return SECRET_KEY_RE.test(key);
}

/**
 * Masks secret patterns in strings or objects.
 */
export function redactSecrets(value: string): string;
export function redactSecrets(value: unknown, depth?: number): unknown;
export function redactSecrets(value: unknown, depth = 0): unknown {
  if (typeof value === "string") {
    return value.replace(SECRET_STRING_RE, "[REDACTED]");
  }
  if (depth > 8) return "[depth-limit]";
  if (Array.isArray(value)) {
    return value.map((item) => redactSecrets(item, depth + 1));
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, child]) => [
        key,
        isSecretKey(key) ? "[REDACTED]" : redactSecrets(child, depth + 1),
      ]),
    );
  }
  return value;
}

/**
 * Builds a user-facing Error for a failed HTTP response, parsing and redacting any error body.
 */
export async function parseErrorBody(res: Response, fallback = "Request failed"): Promise<Error> {
  let text = "";
  try {
    text = await res.text();
  } catch (error) {
    console.warn("Failed to read error response body:", error);
  }

  let detail = text ? redactSecrets(text.slice(0, 300)) : fallback;
  try {
    const parsed = JSON.parse(text);
    const msg = parsed?.detail?.message ?? parsed?.detail ?? parsed?.message;
    if (msg) {
      detail = redactSecrets(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  } catch {
    /* plain text body */
  }

  if (res.status === 503) {
    return new Error(`Service temporarily unavailable. ${detail}`);
  }
  if (res.status === 401) {
    return new Error("Your session expired. Please sign in again.");
  }
  if (res.status === 429) {
    return new Error("Too many requests. Please wait a moment and retry.");
  }
  return new Error(`HTTP ${res.status}: ${detail}`);
}

/**
 * Async generator to pump and parse an SSE Response.
 * Yields event name and data string for each valid SSE line.
 */
export async function* pumpSSE(
  res: Response,
  signal?: AbortSignal,
): AsyncGenerator<{ event: string; data: string }, void, unknown> {
  const reader = res.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";

  try {
    while (true) {
      if (signal?.aborted) return;
      const readResult = await reader.read();
      if (readResult.done) break;
      buffer += decoder.decode(readResult.value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (trimmed.startsWith("event: ")) {
          currentEvent = trimmed.slice(7).trim();
        } else if (trimmed.startsWith("data: ")) {
          const data = trimmed.slice(6).trim();
          yield { event: currentEvent, data };
          currentEvent = "message";
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
