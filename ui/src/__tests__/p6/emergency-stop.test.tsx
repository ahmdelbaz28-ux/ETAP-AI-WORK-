/**
 * Emergency Stop Component Integration Tests (P6 / S4).
 *
 * Verifies three mandatory requirements:
 *  (a) Call-order: abortStream is called BEFORE activateEmergencyStop when button is clicked.
 *  (b) Server failure: No "confirmed" safety state is shown; honest error appears in server-stop-error.
 *  (c) Button disabled after activation: Button is disabled and shows "Active" badge.
 */
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Ensure matchMedia polyfill for jsdom environment
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

const requestMock = vi.fn();
vi.mock("../../lib/api", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));
vi.mock("../../lib/llm-chat", () => ({
  getChatSessionId: () => "test-session-p6",
  streamFromServerChat: vi.fn(),
}));

import { EmergencyStopButton } from "../../components/chat/EmergencyStopButton";
import { useChatStore, _resetWsStateForTesting } from "../../store/chatStore";

function resetChatStore() {
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

describe("EmergencyStopButton Component (P6)", () => {
  beforeEach(() => {
    resetChatStore();
    // Default GET status check response on mount
    requestMock.mockImplementation((url: string) => {
      if (url === "/admin/cua/kill-switch") {
        return Promise.resolve({ active: false });
      }
      return Promise.resolve({ success: true });
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("(a) Call-order: abortStream is called before activateEmergencyStop", async () => {
    const callOrder: string[] = [];

    const origAbortStream = useChatStore.getState().abortStream;
    const origActivate = useChatStore.getState().activateEmergencyStop;

    useChatStore.setState({
      abortStream: () => {
        callOrder.push("abortStream");
        origAbortStream();
      },
      activateEmergencyStop: async (reason?: string) => {
        callOrder.push("activateEmergencyStop");
        return origActivate(reason);
      },
    });

    render(<EmergencyStopButton />);

    const button = screen.getByTestId("emergency-stop-button");
    fireEvent.click(button);

    await waitFor(() => {
      expect(callOrder.length).toBeGreaterThanOrEqual(2);
    });

    expect(callOrder[0]).toBe("abortStream");
    expect(callOrder[1]).toBe("activateEmergencyStop");
  });

  it("(b) Server failure: No confirmed state displayed, honest error message shown", async () => {
    requestMock.mockImplementation((url: string) => {
      if (url === "/admin/cua/kill-switch") {
        return Promise.resolve({ active: false });
      }
      if (url === "/admin/cua/kill-switch/activate") {
        return Promise.reject(new Error("503 Service Unavailable: Kill-switch backend down"));
      }
      return Promise.resolve({});
    });

    render(<EmergencyStopButton />);

    const button = screen.getByTestId("emergency-stop-button");
    fireEvent.click(button);

    // Wait for the async error to resolve in store & render
    await waitFor(() => {
      const errorElement = screen.queryByTestId("server-stop-error");
      expect(errorElement).not.toBeNull();
      expect(errorElement?.textContent).toContain("503 Service Unavailable");
    });

    // Verify no fake confirmation is shown
    expect(screen.queryByTestId("server-stop-status")).toBeNull();
    expect(screen.queryByText(/Kill-switch confirmed/i)).toBeNull();
    expect(screen.queryByText(/Backend acknowledged/i)).toBeNull();
  });

  it("(c) Button is disabled when emergency stop is active", async () => {
    useChatStore.setState({
      emergencyStop: { active: true, activating: false, lastResult: "success", error: null },
    });

    render(<EmergencyStopButton />);

    const button = screen.getByTestId("emergency-stop-button") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.textContent).toContain("Active");

    // Click should not trigger any action when disabled
    const activateSpy = vi.fn();
    act(() => {
      useChatStore.setState({ activateEmergencyStop: activateSpy });
      fireEvent.click(button);
    });
    expect(activateSpy).not.toHaveBeenCalled();
  });
});
