/**
 * Surgical unit tests for Chat Pipeline (SSE + WS unification, seq dedupe, 15s timeout, kill-switch).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();
vi.mock("../lib/api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

const mockStreamChunks: string[] = [];
let mockStreamDelayMs = 0;

vi.mock("../lib/llm-chat", () => ({
  getChatSessionId: () => "surgical-session-id",
  CHAT_STREAM_TIMEOUT_MS: 15000,
  streamFromServerChat: async function* (
    _messages: unknown,
    signal?: AbortSignal,
  ): AsyncGenerator<string, void, unknown> {
    if (mockStreamDelayMs > 0) {
      await new Promise((resolve, reject) => {
        const timer = setTimeout(resolve, mockStreamDelayMs);
        if (signal) {
          signal.addEventListener(
            "abort",
            () => {
              clearTimeout(timer);
              reject(new Error("Chat stream timed out after 15s"));
            },
            { once: true },
          );
        }
      });
    }
    for (const chunk of mockStreamChunks) {
      if (signal?.aborted) {
        throw new Error("Chat stream timed out after 15s");
      }
      yield chunk;
    }
  },
}));

import { _resetWsStateForTesting, useChatStore } from "../store/chatStore";

function resetStore(): void {
  _resetWsStateForTesting();
  useChatStore.setState({
    messages: [],
    results: [],
    activity: [],
    proposedActions: [],
    approvalResults: [],
    approvals: [],
    decisions: [],
    selectedResultId: null,
    emergencyStop: { active: false, activating: false, lastResult: null, error: null },
    autoApprove: { enabled: false, loading: false, error: null },
    lastSeq: 0,
    reconnectAttempts: 0,
    wsStatus: "disconnected",
    streamStatus: "idle",
    lastAssistantId: null,
    wsError: null,
  });
  requestMock.mockReset();
  mockStreamChunks.length = 0;
  mockStreamDelayMs = 0;
}

describe("Chat Surgical — Sequence Number Deduplication", () => {
  beforeEach(resetStore);
  afterEach(resetStore);

  it("advances lastSeq on increasing sequence numbers", () => {
    const store = useChatStore.getState();
    store.handleSessionEvent({
      seq: 1,
      type: "action_proposed",
      session_id: "surgical-session-id",
      ts: "2026-09-14T08:00:00Z",
      payload: { tool: "power_flow" },
    });
    expect(useChatStore.getState().lastSeq).toBe(1);
    expect(useChatStore.getState().proposedActions).toHaveLength(1);

    store.handleSessionEvent({
      seq: 2,
      type: "action_proposed",
      session_id: "surgical-session-id",
      ts: "2026-09-14T08:00:01Z",
      payload: { tool: "short_circuit" },
    });
    expect(useChatStore.getState().lastSeq).toBe(2);
    expect(useChatStore.getState().proposedActions).toHaveLength(2);
  });

  it("discards frames with seq <= lastSeq (replay protection)", () => {
    const store = useChatStore.getState();
    store.handleSessionEvent({
      seq: 5,
      type: "action_proposed",
      session_id: "surgical-session-id",
      ts: "2026-09-14T08:00:05Z",
      payload: { tool: "arc_flash" },
    });
    expect(useChatStore.getState().lastSeq).toBe(5);

    // Duplicate seq: 5
    store.handleSessionEvent({
      seq: 5,
      type: "action_proposed",
      session_id: "surgical-session-id",
      ts: "2026-09-14T08:00:05Z",
      payload: { tool: "duplicate_action" },
    });
    // Older seq: 3
    store.handleSessionEvent({
      seq: 3,
      type: "action_proposed",
      session_id: "surgical-session-id",
      ts: "2026-09-14T08:00:03Z",
      payload: { tool: "stale_action" },
    });

    expect(useChatStore.getState().lastSeq).toBe(5);
    expect(useChatStore.getState().proposedActions).toHaveLength(1);
    expect(useChatStore.getState().proposedActions[0].payload.tool).toBe("arc_flash");
  });

  it("ignores events from other session IDs", () => {
    const store = useChatStore.getState();
    store.handleSessionEvent({
      seq: 1,
      type: "action_proposed",
      session_id: "other-foreign-session",
      ts: "2026-09-14T08:00:00Z",
      payload: { tool: "unauthorized" },
    });
    expect(useChatStore.getState().lastSeq).toBe(0);
    expect(useChatStore.getState().proposedActions).toHaveLength(0);
  });
});

describe("Chat Surgical — Approvals Synchronization", () => {
  beforeEach(resetStore);
  afterEach(resetStore);

  it("removes resolved approval from pending list upon approval_result event", () => {
    useChatStore.setState({
      approvals: [
        {
          id: "appr-123",
          session_id: "surgical-session-id",
          tool: "cable_sizing",
          risk_class: "high",
          status: "pending",
        },
        {
          id: "appr-456",
          session_id: "surgical-session-id",
          tool: "transformer_tap",
          risk_class: "medium",
          status: "pending",
        },
      ],
    });

    const store = useChatStore.getState();
    store.handleSessionEvent({
      seq: 1,
      type: "approval_result",
      session_id: "surgical-session-id",
      ts: "2026-09-14T08:00:10Z",
      payload: {
        approval_id: "appr-123",
        tool: "cable_sizing",
        decision: "approved",
        reason: "Peer reviewed",
      },
    });

    const { approvals, approvalResults } = useChatStore.getState();
    expect(approvals).toHaveLength(1);
    expect(approvals[0].id).toBe("appr-456");
    expect(approvalResults).toHaveLength(1);
    expect(approvalResults[0].decision).toBe("approved");
  });
});

describe("Chat Surgical — Fail-Closed Kill Switch & Timeout", () => {
  beforeEach(resetStore);
  afterEach(resetStore);

  it("blocks sendMessage fail-closed when emergency stop is active", async () => {
    useChatStore.setState({
      emergencyStop: { active: true, activating: false, lastResult: "success", error: null },
    });

    const store = useChatStore.getState();
    const sent = await store.sendMessage("Run short circuit study");
    expect(sent).toBe(false);

    const { messages, streamStatus } = useChatStore.getState();
    expect(streamStatus).toBe("error");
    expect(messages).toHaveLength(1);
    expect(messages[0].error).toBe("EMERGENCY_STOP_ACTIVE");
    expect(messages[0].content).toMatch(/Emergency stop is active/);
  });

  it("completes stream successfully when within timeout", async () => {
    mockStreamChunks.push("Load ", "flow ", "converged.");
    const store = useChatStore.getState();
    const sent = await store.sendMessage("Calculate load flow");
    expect(sent).toBe(true);

    const { messages, streamStatus } = useChatStore.getState();
    expect(streamStatus).toBe("completed");
    expect(messages.some((m) => m.content.includes("Load flow converged."))).toBe(true);
  });

  it("surfaces stable 15s timeout message on aborted stream", async () => {
    // Simulate stream taking too long
    mockStreamDelayMs = 20000;
    vi.useFakeTimers();
    try {
      const store = useChatStore.getState();
      const sendPromise = store.sendMessage("Long running query");
      // Fast forward 15 seconds
      await vi.advanceTimersByTimeAsync(15100);
      const sent = await sendPromise;
      expect(sent).toBe(false);

      const { messages, streamStatus } = useChatStore.getState();
      expect(streamStatus).toBe("error");
      const lastMsg = messages[messages.length - 1];
      expect(lastMsg.status).toBe("error");
      expect(lastMsg.error).toMatch(/timed out after 15s/);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("Chat Surgical — Parallel Stream / Token Deduplication", () => {
  beforeEach(resetStore);
  afterEach(resetStore);

  it("deduplicates identical trailing tokens from parallel stream sources", () => {
    const store = useChatStore.getState();
    // Simulate active assistant message
    useChatStore.setState({
      messages: [
        {
          id: "ws_token_1",
          role: "assistant",
          content: "Voltage profile within limits.",
          status: "streaming",
          createdAt: Date.now(),
        },
      ],
      lastAssistantId: "ws_token_1",
    });

    // Receive token event with redundant trailing text
    store.handleSessionEvent({
      seq: 1,
      type: "token",
      session_id: "surgical-session-id",
      ts: "2026-09-14T08:00:15Z",
      payload: { text: "limits." },
    });

    const { messages } = useChatStore.getState();
    expect(messages[0].content).toBe("Voltage profile within limits.");
  });
});

describe("Chat Surgical — Exponential Reconnection", () => {
  beforeEach(resetStore);
  afterEach(resetStore);

  it("reconnection transitions to failed after max attempts exhausted", async () => {
    vi.useFakeTimers();
    try {
      requestMock.mockResolvedValue({ ticket: "fake-ticket-123" });

      const mockSockets: Array<{
        trigger: (event: string) => void;
      }> = [];

      class MockWs {
        listeners: Record<string, Array<() => void>> = {};
        constructor() {
          mockSockets.push({
            trigger: (event: string) => {
              (this.listeners[event] || []).forEach((cb) => cb());
            },
          });
        }
        addEventListener(event: string, cb: () => void) {
          this.listeners[event] = this.listeners[event] || [];
          this.listeners[event].push(cb);
        }
        close(): void {
          // no-op: mock WebSocket
        }
      }

      const originalWs = globalThis.WebSocket;
      (globalThis as unknown as { WebSocket: unknown }).WebSocket = MockWs;

      try {
        const store = useChatStore.getState();
        store.connectSession();
        await vi.advanceTimersByTimeAsync(10);

        // Exhaust 5 reconnect attempts (initial connection + 5 reconnects = 6 closes)
        for (let i = 0; i <= 5; i++) {
          await Promise.resolve();
          const current = mockSockets.at(-1);
          if (current) current.trigger("close");
          await vi.advanceTimersByTimeAsync(20000);
          await Promise.resolve();
        }

        const state = useChatStore.getState();
        expect(state.wsStatus).toBe("failed");
        expect(state.wsError).toMatch(/reconnect attempts exhausted/);
      } finally {
        (globalThis as unknown as { WebSocket: unknown }).WebSocket = originalWs;
      }
    } finally {
      vi.useRealTimers();
    }
  });
});

