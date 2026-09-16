/**
 * token-governance.ts — Frontend Token Budget & Governance Utilities.
 *
 * Implements client-side token counting heuristics (~4 chars/token),
 * history pruning before context dispatch to LLM, budget tracking per session,
 * and warning/exceeded state calculation for UI indicators.
 */

export interface TokenBudgetState {
  totalBudget: number;
  tokensUsed: number;
  tokensRemaining: number;
  percentUsed: number;
  isExceeded: boolean;
  isWarning: boolean;
  agentBudgets?: Record<
    string,
    {
      used: number;
      budget: number;
      remaining: number;
    }
  >;
}

export const DEFAULT_SESSION_BUDGET = 8000;
export const DEFAULT_MAX_HISTORY_TOKENS = 6000;
export const WARNING_THRESHOLD_PERCENT = 80;

const STORAGE_PREFIX = "ahmedetap_token_usage_";

/**
 * Fast, deterministic token estimation heuristic (~4 characters per token).
 */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.max(1, Math.floor(text.length / 4));
}

/**
 * Estimate cumulative token count of an array of chat messages.
 */
export function estimateMessagesTokens<T extends { content?: string }>(
  messages: readonly T[] | T[],
): number {
  if (!messages || messages.length === 0) return 0;
  let total = 0;
  for (const msg of messages) {
    total += estimateTokens(msg.content || "");
  }
  return total;
}

/**
 * Prunes messages from oldest to newest while preserving system instructions
 * and ensuring the resulting prompt fits within maxTokens.
 */
export function pruneMessagesForBudget<
  T extends { role?: string; content?: string },
>(
  messages: readonly T[] | T[],
  maxTokens: number = DEFAULT_MAX_HISTORY_TOKENS,
  keepSystem: boolean = true,
): T[] {
  if (!messages || messages.length === 0) return [];

  const systemMessages: T[] = [];
  const conversationMessages: T[] = [];

  for (const msg of messages) {
    if (keepSystem && msg.role === "system") {
      systemMessages.push(msg);
    } else {
      conversationMessages.push(msg);
    }
  }

  const sysTokens = estimateMessagesTokens(systemMessages);
  const remainingBudget = Math.max(0, maxTokens - sysTokens);

  // Traverse conversation messages backwards (from most recent to oldest)
  const retained: T[] = [];
  let accumulated = 0;

  for (let i = conversationMessages.length - 1; i >= 0; i--) {
    const msg = conversationMessages[i];
    const msgTokens = estimateTokens(msg.content || "");
    if (accumulated + msgTokens <= remainingBudget) {
      retained.unshift(msg);
      accumulated += msgTokens;
    } else {
      // Cannot fit this older message or any preceding ones
      break;
    }
  }

  return [...systemMessages, ...retained];
}

/**
 * Calculate the TokenBudgetState snapshot.
 */
export function calculateTokenBudgetState(
  tokensUsed: number,
  totalBudget: number = DEFAULT_SESSION_BUDGET,
  agentBudgets?: Record<string, { used: number; budget: number; remaining: number }>,
): TokenBudgetState {
  const safeUsed = Math.max(0, tokensUsed);
  const safeBudget = Math.max(1, totalBudget);
  const remaining = Math.max(0, safeBudget - safeUsed);
  const percentUsed = Math.min(100, Math.round((safeUsed / safeBudget) * 100));

  return {
    totalBudget: safeBudget,
    tokensUsed: safeUsed,
    tokensRemaining: remaining,
    percentUsed,
    isExceeded: safeUsed >= safeBudget,
    isWarning: percentUsed >= WARNING_THRESHOLD_PERCENT && safeUsed < safeBudget,
    agentBudgets,
  };
}

/**
 * Read stored token usage for a session from localStorage (with SSR fallback).
 */
export function loadSessionTokenUsage(sessionId: string): number {
  if (typeof window === "undefined" || !window.localStorage) {
    return 0;
  }
  try {
    const val = localStorage.getItem(STORAGE_PREFIX + sessionId);
    return val ? parseInt(val, 10) || 0 : 0;
  } catch {
    return 0;
  }
}

/**
 * Save updated token usage for a session to localStorage (with SSR fallback).
 */
export function saveSessionTokenUsage(sessionId: string, tokensUsed: number): void {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  try {
    localStorage.setItem(STORAGE_PREFIX + sessionId, String(Math.max(0, tokensUsed)));
  } catch {
    // Ignore quota or private-browsing errors
  }
}
