/**
 * S4 — Emergency Stop call-order and failure-boundary tests.
 *
 * Three mandatory pins (S4 specification §4):
 *  A) abortStream() is called BEFORE activateEmergencyStop posts to backend.
 *  B) Server failure → no "confirmed" state; error is surfaced honestly.
 *  C) After activation (success), the button stays disabled (active=true, no toggle).
 *
 * What this stop sequence does (documented honestly per S4 §5):
 *  - LOCALLY: abortStream() cancels the active SSE/fetch stream and marks
 *    all in-progress activity entries as "failed". This is a client-side
 *    operation that takes effect immediately regardless of server state.
 *  - SERVER: POST /admin/cua/kill-switch/activate tells the CUA Loop to abort
 *    on its next action-check (file-based gate in agents/life_safety.py).
 *    This does NOT guarantee cancellation of a background Python study that
 *    is already running — api/studies.py has no cancel endpoint.
 *
 * `request` from ../../lib/api is mocked; no real network calls happen.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks must be hoisted before any import that resolves chatStore ──────────
const requestMock = vi.fn();
vi.mock("../../lib/api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));
vi.mock("../../lib/llm-chat", () => ({
  getChatSessionId: () => "test-session-id",
  streamFromServerChat: vi.fn(),
}));

import { useChatStore, _resetWsStateForTesting } from "../../store/chatStore";

function resetStore(): void {
  _resetWsStateForTesting();
  useChatStore.setState({
    streamStatus: "idle",
    activity: [],
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

// ── A) Call-order: abortStream then backend POST ─────────────────────────────

describe("S4-A — call-order: abortStream() before backend POST", () => {
  beforeEach(resetStore);
  afterEach(() => requestMock.mockReset());

  it("streamStatus becomes idle (abortStream effect) synchronously before the POST resolves", async () => {
    // Arrange: one in-progress activity entry
    useChatStore.setState({
      streamStatus: "streaming",
      activity: [{ phase: "running", pct: 50, tool: "load_flow" }],
    });

    let streamStatusAtPostTime: string | undefined;

    // Intercept the POST call to capture state at that exact moment
    requestMock.mockImplementationOnce((_url: string) => {
      // By the time we reach POST /admin/cua/kill-switch/activate,
      // abortStream() must have already set streamStatus to idle
      // (or "error" which activateEmergencyStop sets right after abortStream)
      streamStatusAtPostTime = useChatStore.getState().streamStatus;
      return Promise.resolve({ success: true });
    });

    await useChatStore.getState().activateEmergencyStop("s4-order-test");

    // streamStatus is set to "error" immediately after abortStream in activateEmergencyStop
    // then the POST fires — so by POST time it's "error" (not "streaming")
    expect(streamStatusAtPostTime).not.toBe("streaming");

    // After success the activity entries must be marked failed (abortStream effect)
    const { activity } = useChatStore.getState();
    expect(activity.every((a) => a.phase === "failed" || a.phase === "completed")).toBe(true);
  });

  it("abortStream marks in-progress activity entries as 'failed' before server is contacted", async () => {
    useChatStore.setState({
      streamStatus: "streaming",
      activity: [
        { phase: "running", pct: 30, tool: "arc_flash" },
        { phase: "completed", pct: 100, tool: "load_flow" },
      ],
    });

    let runningCountAtPost = 0;
    requestMock.mockImplementationOnce(() => {
      const { activity } = useChatStore.getState();
      runningCountAtPost = activity.filter(
        (a) => a.phase !== "failed" && a.phase !== "completed",
      ).length;
      return Promise.resolve({ success: true });
    });

    await useChatStore.getState().activateEmergencyStop("s4-order-check");

    // By POST time, all in-progress entries must already be "failed"
    expect(runningCountAtPost).toBe(0);
  });
});

// ── B) Server failure → no "confirmed" state ─────────────────────────────────

describe("S4-B — server failure: no confirmed state, honest error", () => {
  beforeEach(resetStore);
  afterEach(() => requestMock.mockReset());

  it("server 503 → active stays false, lastResult='error', error contains message", async () => {
    requestMock.mockRejectedValueOnce(new Error("503 Service Unavailable"));
    const result = await useChatStore.getState().activateEmergencyStop("s4-fail-test");

    expect(result).toBe(false);
    const { emergencyStop } = useChatStore.getState();
    expect(emergencyStop.active).toBe(false);        // NOT confirmed
    expect(emergencyStop.activating).toBe(false);    // spinner gone
    expect(emergencyStop.lastResult).toBe("error");  // honest result
    expect(emergencyStop.error).toMatch(/503 Service Unavailable/);
  });

  it("network error (TypeError) → active stays false, no fake safety claim", async () => {
    requestMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const result = await useChatStore.getState().activateEmergencyStop();

    expect(result).toBe(false);
    const { emergencyStop } = useChatStore.getState();
    expect(emergencyStop.active).toBe(false);
    expect(emergencyStop.lastResult).toBe("error");
    // Must NOT claim "Kill switch active" or "Confirmed" without backend ack
    expect(emergencyStop.error).not.toMatch(/confirmed/i);
    expect(emergencyStop.error).not.toMatch(/active/i);
  });

  it("server failure: stream is still locally aborted even if server fails", async () => {
    useChatStore.setState({
      streamStatus: "streaming",
      activity: [{ phase: "running", pct: 60, tool: "short_circuit" }],
    });
    requestMock.mockRejectedValueOnce(new Error("Backend unavailable"));

    await useChatStore.getState().activateEmergencyStop("s4-local-abort-on-fail");

    // Local stream is still aborted (abortStream runs before the POST)
    const { activity } = useChatStore.getState();
    expect(activity.every((a) => a.phase === "failed" || a.phase === "completed")).toBe(true);
    // But server is not confirmed
    expect(useChatStore.getState().emergencyStop.active).toBe(false);
  });
});

// ── C) After activation, button stays disabled (active=true, no toggle) ───────

describe("S4-C — button stays disabled after successful activation", () => {
  beforeEach(resetStore);
  afterEach(() => requestMock.mockReset());

  it("after success: active=true and cannot be re-activated (idempotent guard)", async () => {
    // First activation succeeds
    requestMock.mockResolvedValueOnce({ success: true });
    await useChatStore.getState().activateEmergencyStop("s4-disable-test");

    const state1 = useChatStore.getState().emergencyStop;
    expect(state1.active).toBe(true);
    expect(state1.activating).toBe(false);

    // A second call while active=true:
    // The button is disabled in UI when active=true — this test checks the
    // store level: even if called again, active remains true (not reset to false).
    requestMock.mockResolvedValueOnce({ success: true });
    await useChatStore.getState().activateEmergencyStop("s4-second-call");

    const state2 = useChatStore.getState().emergencyStop;
    // active must still be true — never toggled off by a second call
    expect(state2.active).toBe(true);
  });

  it("after success: activating=false (no infinite spinner)", async () => {
    requestMock.mockResolvedValueOnce({ success: true });
    await useChatStore.getState().activateEmergencyStop("s4-spinner-test");
    expect(useChatStore.getState().emergencyStop.activating).toBe(false);
  });

  it("after failure: activating=false (spinner clears even on error)", async () => {
    requestMock.mockRejectedValueOnce(new Error("timeout"));
    await useChatStore.getState().activateEmergencyStop("s4-spinner-fail");
    expect(useChatStore.getState().emergencyStop.activating).toBe(false);
  });
});

// ── D) ActivityDrawer Stop button — pre-existing behaviour (S4.1 correction) ──
//
// The Stop button in ActivityDrawer (ActivityDrawer.tsx:84-93, data-testid="stop-active-job")
// was NOT added in S4. It exists since commit 72c1024ee (feat: add ChatWorkspace UI).
// git diff HEAD -- ui/src/components/chat/ActivityDrawer.tsx  → empty (no S4 changes).
//
// The button calls:  useChatStore.getState().abortStream()
// This is the same abortStream() tested in S4-A above. This test documents and pins
// that behaviour at the store level — no component rendering required.
//
// Honest limit: abortStream() only stops the local SSE/fetch stream and marks
// activity entries as "failed" in the UI. A background Python study has no
// cancel endpoint (api/studies.py — zero cancel/abort hits); it completes naturally.

describe("S4-D — ActivityDrawer Stop button (pre-existing, no S4 change)", () => {
  beforeEach(resetStore);
  afterEach(() => requestMock.mockReset());

  it("abortStream() — called by the pre-existing Stop button — marks in-progress entries as failed", () => {
    // Arrange: replicate the state that ActivityDrawer would show a Stop button for
    // (isInProgress = phase !== "completed" && phase !== "failed")
    useChatStore.setState({
      streamStatus: "streaming",
      activity: [
        { phase: "running", pct: 40, tool: "load_flow", execution_id: "exec-drawer-1" },
        { phase: "initialising", pct: 10, tool: "arc_flash", execution_id: "exec-drawer-2" },
        { phase: "completed", pct: 100, tool: "short_circuit", execution_id: "exec-drawer-3" },
      ],
    });

    // Act: simulate what the Stop button onClick does
    //   onClick={() => useChatStore.getState().abortStream()}   (ActivityDrawer.tsx:87)
    useChatStore.getState().abortStream();

    // Assert: in-progress entries → "failed", completed entry unchanged
    const { activity, streamStatus } = useChatStore.getState();
    const inProgressAfter = activity.filter(
      (a) => a.phase !== "failed" && a.phase !== "completed",
    );
    const failedAfter = activity.filter((a) => a.phase === "failed");
    const completedAfter = activity.filter((a) => a.phase === "completed");

    expect(inProgressAfter).toHaveLength(0);        // all running entries stopped
    expect(failedAfter).toHaveLength(2);            // "running" + "initialising" → "failed"
    expect(completedAfter).toHaveLength(1);         // "completed" entry untouched
    expect(completedAfter[0].tool).toBe("short_circuit");
    expect(streamStatus).toBe("idle");              // stream locally closed
  });
});

