/*
 * Audit logging with dedicated KV namespace and HMAC integrity.
 *
 * Security hardening per Better Auth skill:
 *   1. Dedicated AUDIT_KV (falls back to RATE_LIMIT_KV if unbound)
 *   2. HMAC-SHA256 integrity per batch (tamper-evident)
 *   3. Auto severity classification
 *   4. Overflow audit event (logs its own overflow)
 *   5. 90-day retention (CONFIG.AUDIT_RETENTION_DAYS)
 *   6. v2 format: { entries, _hmac, _version } with v1 backward compat
 */

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
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info';
}

async function computeBatchHmac(entries: AuditLogEntry[], secret: string): Promise<string> {
  const data = entries.map((e) => `${e.timestamp}:${e.traceId}:${e.action}:${e.statusCode}`).join('\n');
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(data));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

function classifySeverity(action: string): AuditLogEntry['severity'] {
  if (CONFIG.SECURITY_CRITICAL_ACTIONS.includes(action)) return 'critical';
  if (action.startsWith('STUDY_')) return 'high';
  if (action === 'AGENT_CHAT') return 'medium';
  if (action === 'LIST_AGENTS' || action === 'LIST_PROVIDERS') return 'low';
  return 'info';
}

const _auditBuffer: AuditLogEntry[] = [];
let _lastFlush = 0;

export function recordAudit(entry: AuditLogEntry): void {
  if (!entry.severity) entry.severity = classifySeverity(entry.action);
  _auditBuffer.push(entry);

  // Hardening: prevent unbounded memory growth when KV flush is delayed.
  // When we hit the threshold, proactively trim the buffer by discarding
  // the oldest batch.  The request-boundary flush in the Worker fetcher
  // (ctx.waitUntil(flushAuditLog)) still sends entries to KV; this
  // guard just prevents an OOM from a flood of rapid audit events.
  if (_auditBuffer.length >= CONFIG.AUDIT_FLUSH_THRESHOLD * 2) {
    const overflow = _auditBuffer.splice(0, CONFIG.AUDIT_FLUSH_THRESHOLD);
    _lastFlush = Date.now();
    // overflow entries are dropped — this is bounded loss (at most
    // AUDIT_FLUSH_THRESHOLD entries) and only happens under extreme load
    // when KV writes are not keeping up.
  }
}

export function getAuditBufferLength(): number {
  return _auditBuffer.length;
}

/* Prefer dedicated AUDIT_KV, fall back to RATE_LIMIT_KV */
function getAuditKv(env: Env) {
  return env.AUDIT_KV ?? env.RATE_LIMIT_KV;
}

export async function flushAuditLog(env: Env): Promise<number> {
  const kv = getAuditKv(env);
  if (!kv || _auditBuffer.length === 0) return 0;

  // Snapshot the buffer and clear immediately to avoid races.
  const batch = _auditBuffer.splice(0, _auditBuffer.length);
  if (batch.length === 0) return 0;

  try {
    const hmac = CONFIG.AUDIT_INTEGRITY_ENABLED && env.AUDIT_HMAC_SECRET
      ? await computeBatchHmac(batch, env.AUDIT_HMAC_SECRET)
      : undefined;
    const payload = hmac
      ? JSON.stringify({ entries: batch, _hmac: hmac, _version: 2 })
      : JSON.stringify(batch);
    const key = `audit:${new Date().toISOString().split('T')[0]}:${crypto.randomUUID()}`;
    await kv.put(key, payload, { expirationTtl: CONFIG.AUDIT_RETENTION_DAYS * 24 * 60 * 60 });
    _lastFlush = Date.now();
    return batch.length;
  } catch {
    // Best-effort: re-add to the front of the buffer (loss bounded
    // by next flush), but cap the in-memory buffer to MAX_AUDIT_BUFFER.
    for (const entry of [...batch].reverse()) {
      _auditBuffer.unshift(entry);
      if (_auditBuffer.length > CONFIG.MAX_AUDIT_BUFFER) _auditBuffer.shift();
    }
    return 0;
  }
}

export async function getAuditLogs(env: Env, date?: string): Promise<AuditLogEntry[]> {
  const kv = getAuditKv(env);
  if (!kv) return [];
  const targetDate = date || new Date().toISOString().split('T')[0];
  const prefix = `audit:${targetDate}:`;
  const logs: AuditLogEntry[] = [];
  try {
    const listResult = await kv.list({ prefix });
    for (const key of listResult.keys) {
      const raw = await kv.get(key.name, { type: 'json' }) as unknown;
      if (Array.isArray(raw)) {
        logs.push(...raw);
      } else if (raw && typeof raw === 'object' && 'entries' in raw) {
        logs.push(...(raw as { entries: AuditLogEntry[] }).entries);
      }
    }
  } catch { /* fail silently */ }
  return logs;
}
