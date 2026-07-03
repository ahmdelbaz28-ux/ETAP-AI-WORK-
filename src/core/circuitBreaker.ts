/**
 * Per-provider circuit breaker with KV persistence.
 *
 * Rules:
 *   - Opens after N consecutive failures (default 3)
 *   - Cooldown period of 60s
 *   - Auto-recovery after cooldown (allows one trial call)
 *   - Successful trial closes the circuit
 *   - State persists to KV (METRICS_KV) for multi-region resilience
 *
 * This is a hard-isolated per-provider state — one provider's failures
 * do not affect any other.
 */
import type { Env } from './types.js';
import { CONFIG } from './config.js';

export type CircuitState = 'closed' | 'open' | 'half-open';

interface BreakerState {
  state: CircuitState;
  consecutiveFailures: number;
  openedAt: number;
  lastFailureAt: number;
  totalSuccesses: number;
  totalFailures: number;
}

const _breakers: Map<string, BreakerState> = new Map();
let _kvLoaded = false;

function _kvKey(name: string): string {
  return `circuit:${name}`;
}

function getBreaker(name: string): BreakerState {
  let s = _breakers.get(name);
  if (!s) {
    s = {
      state: 'closed',
      consecutiveFailures: 0,
      openedAt: 0,
      lastFailureAt: 0,
      totalSuccesses: 0,
      totalFailures: 0,
    };
    _breakers.set(name, s);
  }
  return s;
}

/** Load circuit breaker state from KV (best-effort). */
export async function loadCircuitBreakers(env: Env): Promise<void> {
  if (!env.METRICS_KV || _kvLoaded) return;
  try {
    const list = await env.METRICS_KV.list({ prefix: 'circuit:' });
    for (const key of list.keys) {
      const raw = await env.METRICS_KV.get(key.name, { type: 'json' }) as BreakerState | null;
      if (raw) {
        const name = key.name.replaceAll('circuit:', '');
        _breakers.set(name, raw);
      }
    }
  } catch {
    // silent
  }
  _kvLoaded = true;
}

/** Save a single breaker state to KV (best-effort). */
async function _saveBreaker(env: Env | undefined, name: string, state: BreakerState): Promise<void> {
  if (!env?.METRICS_KV) return;
  try {
    await env.METRICS_KV.put(_kvKey(name), JSON.stringify(state), { expirationTtl: 7 * 24 * 60 * 60 });
  } catch {
    // silent
  }
}

export function isCircuitOpen(name: string): boolean {
  const b = getBreaker(name);
  if (b.state === 'open') {
    if (Date.now() - b.openedAt >= CONFIG.CIRCUIT_BREAKER_COOLDOWN_MS) {
      // Cooldown elapsed — move to half-open
      b.state = 'half-open';
      return false;
    }
    return true;
  }
  return false;
}

export function recordProviderSuccess(name: string, env?: Env): void {
  const b = getBreaker(name);
  b.consecutiveFailures = 0;
  b.totalSuccesses++;
  b.state = 'closed';
  if (env) {
    // Fire-and-forget KV persistence
    _saveBreaker(env, name, b).catch(() => {});
  }
}

export function recordProviderFailure(name: string, env?: Env): void {
  const b = getBreaker(name);
  b.consecutiveFailures++;
  b.totalFailures++;
  b.lastFailureAt = Date.now();
  if (b.consecutiveFailures >= CONFIG.CIRCUIT_BREAKER_FAILURE_THRESHOLD) {
    b.state = 'open';
    b.openedAt = Date.now();
  }
  if (env) {
    _saveBreaker(env, name, b).catch(() => {});
  }
}

export function getCircuitHealth(name: string): {
  state: CircuitState;
  consecutiveFailures: number;
  totalSuccesses: number;
  totalFailures: number;
  openedAt: number;
  lastFailureAt: number;
  cooldownRemainingMs: number;
} {
  const b = getBreaker(name);
  const cooldownRemainingMs =
    b.state === 'open'
      ? Math.max(0, CONFIG.CIRCUIT_BREAKER_COOLDOWN_MS - (Date.now() - b.openedAt))
      : 0;
  return { ...b, cooldownRemainingMs };
}

export function getAllCircuitHealth(): Record<string, ReturnType<typeof getCircuitHealth>> {
  const out: Record<string, ReturnType<typeof getCircuitHealth>> = {};
  for (const name of _breakers.keys()) {
    out[name] = getCircuitHealth(name);
  }
  return out;
}

/** Test-only: reset all breakers. */
export function _resetBreakersForTest(): void {
  _breakers.clear();
  _kvLoaded = false;
}
