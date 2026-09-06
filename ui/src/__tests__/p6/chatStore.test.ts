/**
 * P6 chatStore behavior tests.
 *
 * Pins P6 wire contract and safety semantics:
 *  1. SessionStream `result_ready` (P3 snake_case `result_id`) is translated
 *     at the store boundary to the P5 public `resultId` (camelCase).
 *  2. Emergency stop activation NEVER claims "active" before the backend
 *     acknowledges, returns false on failure, surfaces a stable error.
 *  3. Auto-approve is a backend policy mirror — no client-side authority.
 *
 * `request` (from ../lib/api) is mocked so no real network calls happen.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();
vi.mock("../../lib/api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

vi.mock("../../lib/llm-chat", () => ({
  getChatSessionId: () => "test-session-id",
  streamFromServerChat: vi.fn(),
}));

import { useChatStore } from "../../store/chatStore";

const originalState = () => useChatStore.getState();

function resetStore(): void {
  useChatStore.setState({
    results: [],
    selectedResultId: null,
    emergencyStop: { active: false, activating: false, lastResult: null, error: null },
    autoApprove: { enabled: false, loading: false, error: null },
    approvals: [],
    lastSeq: 0,
    wsStatus: "disconnected",
  });
  requestMock.mockReset();
}

describe("P6 chatStore — resultId wire contract", () => {
  beforeEach(resetStore);
  afterEach(() => requestMock.mockReset());

  it("translates SessionStream result_ready snake_case → frontend resultId", () => {
    const store = originalState();
    store.handleSessionEvent({
      seq: 1,
      type: "result_ready",
      session_id: "test-session-id",
      ts: "2026-08-29T10:00:00Z",
      payload: {
        result_id: "res-abc-123",
        execution_id: "exec-1",
        tool: "load_flow",
        plan_id: "plan-1",
        summary: { ok: true },
      },
    });
    const { results, selectedResultId } = useChatStore.getState();
    expect(results).toHaveLength(1);
    expect(results[0].resultId).toBe("res-abc-123");
    expect(results[0].execution_id).toBe("exec-1");
    expect(results[0].tool).toBe("load_flow");
    expect(results[0].loading).toBe(true);
    expect((results[0] as unknown as Record<string, unknown>).result_id).toBeUndefined();
    expect(selectedResultId).toBe("res-abc-123");
  });

  it("falls back to execution_id when result_id is absent (replay tolerance)", () => {
    const store = originalState();
    store.handleSessionEvent({
      seq: 2,
      type: "result_ready",
      session_id: "test-session-id",
      ts: "2026-08-29T10:00:01Z",
      payload: { execution_id: "exec-only" },
    });
    const { results } = useChatStore.getState();
    expect(results).toHaveLength(1);
    expect(results[0].resultId).toBe("exec-only");
  });

  it("ignores result_ready events without an id-like field", () => {
    const store = originalState();
    store.handleSessionEvent({
      seq: 3,
      type: "result_ready",
      session_id: "test-session-id",
      ts: "2026-08-29T10:00:02Z",
      payload: { tool: "load_flow" },
    });
    expect(useChatStore.getState().results).toHaveLength(0);
  });

  it("deduplicates by resultId — same id twice keeps one entry", () => {
    const store = originalState();
    const evt = {
      type: "result_ready",
      session_id: "test-session-id",
      ts: "2026-08-29T10:00:03Z",
      payload: { result_id: "res-dup" },
    } as const;
    store.handleSessionEvent({ ...evt, seq: 4 });
    store.handleSessionEvent({ ...evt, seq: 5 });
    const { results } = useChatStore.getState();
    expect(results).toHaveLength(1);
    expect(results[0].resultId).toBe("res-dup");
  });
});

describe("P6 chatStore — emergency stop safety semantics", () => {
  beforeEach(resetStore);
  afterEach(() => requestMock.mockReset());

  it("activation success → active=true ONLY after backend resolves", async () => {
    requestMock.mockResolvedValueOnce({ success: true });
    const store = originalState();
    const result = await store.activateEmergencyStop("test_reason");
    expect(requestMock).toHaveBeenCalledWith(
      "/admin/cua/kill-switch/activate",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toBe(true);
    const { emergencyStop } = useChatStore.getState();
    expect(emergencyStop.active).toBe(true);
    expect(emergencyStop.activating).toBe(false);
    expect(emergencyStop.lastResult).toBe("success");
    expect(emergencyStop.error).toBeNull();
  });

  it("activation failure (HTTP error) → active stays false, lastResult=error", async () => {
    requestMock.mockRejectedValueOnce(new Error("API 503: kill switch unavailable"));
    const store = originalState();
    const result = await store.activateEmergencyStop("test_reason");
    expect(result).toBe(false);
    const { emergencyStop } = useChatStore.getState();
    expect(emergencyStop.active).toBe(false);
    expect(emergencyStop.activating).toBe(false);
    expect(emergencyStop.lastResult).toBe("error");
    expect(emergencyStop.error).toMatch(/kill switch unavailable/);
  });

  it("activation network failure → active remains false (no fake local safety)", async () => {
    requestMock.mockRejectedValueOnce(new TypeError("NetworkError: failed to fetch"));
    const store = originalState();
    const result = await store.activateEmergencyStop();
    expect(result).toBe(false);
    const { emergencyStop } = useChatStore.getState();
    expect(emergencyStop.active).toBe(false);
    expect(emergencyStop.activating).toBe(false);
    expect(emergencyStop.lastResult).toBe("error");
  });

  it("checkEmergencyStop on backend success → reflects state, no error", async () => {
    requestMock.mockResolvedValueOnce({ active: true, reason: "ops_test" });
    const store = originalState();
    await store.checkEmergencyStop();
    const { emergencyStop } = useChatStore.getState();
    expect(emergencyStop.active).toBe(true);
    expect(emergencyStop.error).toBeNull();
  });

  it("checkEmergencyStop on backend error → active unchanged, error recorded (fallback msg)", async () => {
    const store = originalState();
    // Non-Error / empty error exercises the toErrorMessage fallback used for the
    // fail-closed "unknown" state (error is preserved, active never flips).
    requestMock.mockRejectedValueOnce({});
    await store.checkEmergencyStop();
    const { emergencyStop } = useChatStore.getState();
    expect(emergencyStop.active).toBe(false);
    expect(emergencyStop.error).toMatch(/Failed to read kill-switch state/);

    // Sanity: a real backend error message is passed through verbatim.
    requestMock.mockReset();
    requestMock.mockRejectedValueOnce(new Error("503 Upstream down"));
    await store.checkEmergencyStop();
    expect(useChatStore.getState().emergencyStop.error).toBe("503 Upstream down");
  });
});
