/**
 * Unit tests for Frontend Token Governance (heuristics, pruning, and chatStore integration).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  calculateTokenBudgetState,
  DEFAULT_SESSION_BUDGET,
  estimateMessagesTokens,
  estimateTokens,
  loadSessionTokenUsage,
  pruneMessagesForBudget,
  saveSessionTokenUsage,
} from "../lib/token-governance";
import { useChatStore } from "../store/chatStore";

describe("Token Governance - Heuristics & Pruning", () => {
  it("estimateTokens accurately calculates token counts", () => {
    expect(estimateTokens("")).toBe(0);
    expect(estimateTokens("hi")).toBe(1);
    const chars400 = "a".repeat(400);
    expect(estimateTokens(chars400)).toBe(100);
  });

  it("estimateMessagesTokens sums messages correctly", () => {
    expect(estimateMessagesTokens([])).toBe(0);
    const messages = [
      { role: "user", content: "a".repeat(40) }, // 10 tokens
      { role: "assistant", content: "b".repeat(80) }, // 20 tokens
    ];
    expect(estimateMessagesTokens(messages)).toBe(30);
  });

  it("pruneMessagesForBudget retains system instructions and recent turns", () => {
    const messages = [
      { role: "system", content: "System instructions for ETAP" },
      { role: "user", content: "Old message 1: " + "x".repeat(200) }, // ~50 tokens
      { role: "assistant", content: "Old message 2: " + "y".repeat(200) }, // ~50 tokens
      { role: "user", content: "Recent question" }, // ~3 tokens
      { role: "assistant", content: "Recent answer" }, // ~3 tokens
    ];

    // Budget allowed: 30 tokens
    const pruned = pruneMessagesForBudget(messages, 30);

    // First message must be system
    expect(pruned[0].role).toBe("system");
    expect(pruned[0].content).toBe("System instructions for ETAP");

    // Most recent messages must be retained
    expect(pruned[pruned.length - 1].content).toBe("Recent answer");
    expect(pruned[pruned.length - 2].content).toBe("Recent question");

    // Oldest messages should be discarded
    expect(pruned.some((m) => m.content.startsWith("Old message 1"))).toBe(false);
  });

  it("calculateTokenBudgetState computes warning and exceeded flags", () => {
    const normal = calculateTokenBudgetState(2000, 10000);
    expect(normal.percentUsed).toBe(20);
    expect(normal.isWarning).toBe(false);
    expect(normal.isExceeded).toBe(false);
    expect(normal.tokensRemaining).toBe(8000);

    const warning = calculateTokenBudgetState(8500, 10000);
    expect(warning.percentUsed).toBe(85);
    expect(warning.isWarning).toBe(true);
    expect(warning.isExceeded).toBe(false);

    const exceeded = calculateTokenBudgetState(10000, 10000);
    expect(exceeded.percentUsed).toBe(100);
    expect(exceeded.isWarning).toBe(false);
    expect(exceeded.isExceeded).toBe(true);
  });

  it("persists and reads session token usage in localStorage", () => {
    const sessionId = "test-session-storage";
    saveSessionTokenUsage(sessionId, 3420);
    expect(loadSessionTokenUsage(sessionId)).toBe(3420);
    localStorage.removeItem("ahmedetap_token_usage_" + sessionId);
  });
});

describe("Token Governance - ChatStore Integration", () => {
  beforeEach(() => {
    useChatStore.getState().clearSessionData();
  });

  afterEach(() => {
    useChatStore.getState().clearSessionData();
  });

  it("initializes chatStore with default tokenBudget", () => {
    const budget = useChatStore.getState().tokenBudget;
    expect(budget.totalBudget).toBe(DEFAULT_SESSION_BUDGET);
    expect(budget.tokensUsed).toBe(0);
    expect(budget.isExceeded).toBe(false);
  });

  it("updates tokenBudget upon receiving token_usage event from session stream", () => {
    const store = useChatStore.getState();
    const sessionId = store.sessionId;

    store.handleSessionEvent({
      seq: 1,
      type: "token_usage",
      session_id: sessionId,
      ts: new Date().toISOString(),
      payload: {
        total_used: 4500,
        budget: 8000,
      },
    });

    const updated = useChatStore.getState().tokenBudget;
    expect(updated.tokensUsed).toBe(4500);
    expect(updated.totalBudget).toBe(8000);
    expect(updated.tokensRemaining).toBe(3500);
    expect(updated.percentUsed).toBe(56);
  });

  it("clearSessionData resets tokenBudget back to zero", () => {
    const store = useChatStore.getState();
    store.updateTokenBudget({ tokensUsed: 5000, percentUsed: 62 });
    expect(useChatStore.getState().tokenBudget.tokensUsed).toBe(5000);

    store.clearSessionData();
    expect(useChatStore.getState().tokenBudget.tokensUsed).toBe(0);
  });
});
