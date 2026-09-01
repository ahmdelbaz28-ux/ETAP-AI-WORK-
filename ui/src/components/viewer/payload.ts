/**
 * Payload display helpers for P6 viewers.
 *
 * We never invent wire schemas. These helpers only format whatever data the
 * backend actually delivered — redacting values whose key looks secret so a
 * raw JSON pane can never leak API keys, tokens, or passwords.
 */

const SECRET_KEY_RE = /(api[_-]?key|secret|token|password|authorization|credential)/i;

export function isSecretKey(key: string): boolean {
  return SECRET_KEY_RE.test(key);
}

/** Recursively mask secret-looking values (max depth guard). */
export function redactSecrets(value: unknown, depth = 0): unknown {
  if (depth > 8) return "[depth-limit]";
  if (Array.isArray(value)) return value.map((item) => redactSecrets(item, depth + 1));
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

export function toRedactedJson(value: unknown): string {
  try {
    return JSON.stringify(redactSecrets(value), null, 2);
  } catch {
    return String(value);
  }
}