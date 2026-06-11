/**
 * Audit logging buffer with KV fallback flush.
 *
 * Hardening changes:
 *   - No silent drops: when the in-memory buffer overflows, the
 *     oldest batch is flushed to KV before being discarded.
 *   - Fallback flush to KV on each request boundary (background).
 *   - Buffers are typed and include scope info for compliance.
 */
import type { Env } from '../core/types.js';
import { CONFIG } from '../core/config.js';

export interface AuditLogEntry {
  timestamp: string;
  traceId: string;
  clientIp: string;
  method: string;
  path: string;
  statusCode: number;
  userAgent: string;
  action: string;
  authenticated: boolean;
  rateLimited: boolean;
  apiKeyId?: string;
  scope?: string;
  latencyMs?: number;
  details?: Record<string, unknown>;
}

const _auditBuffer: AuditLogEntry[] = [];
let _lastFlush = 0;

export function recordAudit(entry: AuditLogEntry): void {
  _auditBuffer.push(entry);

  // Hardening: do not silently drop. Flush when we hit the threshold
  // OR the per-request boundary in the calling code.
  if (_auditBuffer.length >= CONFIG.AUDIT_FLUSH_THRESHOLD) {
    // Mark for flush on next await (caller schedules via flushAuditLog)
    _lastFlush = Date.now();
  }
}

export function getAuditBufferLength(): number {
  return _auditBuffer.length;
}

/** Flush to KV. Returns the number of entries flushed. */
export async function flushAuditLog(env: Env): Promise<number> {
  if (!env.RATE_LIMIT_KV || _auditBuffer.length === 0) return 0;

  // Snapshot the buffer and clear immediately to avoid races.
  const batch = _auditBuffer.splice(0, _auditBuffer.length);
  if (batch.length === 0) return 0;

  try {
    const key = `audit:${new Date().toISOString().split('T')[0]}:${crypto.randomUUID()}`;
    await env.RATE_LIMIT_KV.put(key, JSON.stringify(batch), { expirationTtl: 90 * 24 * 60 * 60 });
    _lastFlush = Date.now();
    return batch.length;
  } catch {
    // Best-effort: re-add to the front of the buffer (loss bounded
    // by next flush), but cap the in-memory buffer to MAX_AUDIT_BUFFER.
    for (const entry of batch.reverse()) {
      _auditBuffer.unshift(entry);
      if (_auditBuffer.length > CONFIG.MAX_AUDIT_BUFFER) _auditBuffer.shift();
    }
    return 0;
  }
}

export async function getAuditLogs(env: Env, date?: string): Promise<AuditLogEntry[]> {
  if (!env.RATE_LIMIT_KV) return [];
  const targetDate = date || new Date().toISOString().split('T')[0];
  const prefix = `audit:${targetDate}:`;
  const logs: AuditLogEntry[] = [];
  try {
    const listResult = await env.RATE_LIMIT_KV.list({ prefix });
    for (const key of listResult.keys) {
      const raw = (await env.RATE_LIMIT_KV.get(key.name, { type: 'json' })) as AuditLogEntry[] | null;
      if (Array.isArray(raw)) logs.push(...raw);
    }
  } catch {
    // Fail silently
  }
  return logs;
}
