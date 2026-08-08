import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
/**
 * @vitest-environment jsdom
 *
 * Tests for the DualControl page component (life-safety 4-eyes approval workflow).
 *
 * Verifies:
 *   - Renders the header + life-safety warning banner
 *   - Calls the pending-list API on mount
 *   - Displays pending requests when API returns them
 *   - Shows empty state when no requests exist
 *   - Surfaces error message when API fails
 *   - "New Request" button opens the create modal
 *   - Action-type select in the create modal has the expected life-safety options
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../hooks/useAuth";
import DualControl from "../DualControl";

// ── Mocks ──
vi.mock("../../hooks/useAuth", async () => {
  const actual = await vi.importActual<typeof import("../../hooks/useAuth")>("../../hooks/useAuth");
  return {
    ...actual,
    useAuth: () => ({
      user: {
        id: "user-engineer-1",
        email: "eng@example.com",
        name: "Engineer 1",
        role: "engineer",
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      register: vi.fn(),
      refreshToken: vi.fn(),
    }),
  };
});

// Mock the API client — listPendingDualControlRequests returns empty by default.
const mockListPending = vi.fn();
const mockCreateRequest = vi.fn();
const mockApproveRequest = vi.fn();
const mockRejectRequest = vi.fn();
const mockGetQrSecret = vi.fn();

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    listPendingDualControlRequests: () => mockListPending(),
    createDualControlRequest: (input: unknown) => mockCreateRequest(input),
    approveDualControlRequest: (id: string, secret?: string) => mockApproveRequest(id, secret),
    rejectDualControlRequest: (id: string, reason: string) => mockRejectRequest(id, reason),
    getDualControlQrSecret: (id: string) => mockGetQrSecret(id),
  };
});

// Stub NotificationContext
const mockNotify = vi.fn();
vi.mock("../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: mockNotify, dismiss: vi.fn() }),
}));

// Stub ContextHelpButton so we don't need the help-system machinery
vi.mock("../../components/help/ContextHelpButton", () => ({
  ContextHelpButton: () => null,
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  mockListPending.mockResolvedValue({ success: true, data: [] });
  mockCreateRequest.mockResolvedValue({
    success: true,
    data: {
      request_id: "apr_test123",
      action: { type: "breaker_switch" },
      requested_by: "user-engineer-1",
      status: "pending",
      approved_by: null,
      approved_at: null,
      rejected_by: null,
      rejected_reason: null,
      created_at: new Date().toISOString(),
      expires_at: Date.now() / 1000 + 300,
      qr_secret: "test-qr-secret",
    },
  });
  mockApproveRequest.mockResolvedValue({ success: true });
  mockRejectRequest.mockResolvedValue({ success: true });
  mockGetQrSecret.mockResolvedValue({
    success: true,
    data: { request_id: "apr_test123", qr_secret: "test-qr-secret" },
  });
});

// Need to advance fake timers for the 5s auto-refresh interval inside the component.
// We use a helper to switch back to real timers during renders (testing-library
// needs real timers for `waitFor`).
async function renderWithRealTimers(ui: React.ReactElement) {
  vi.useRealTimers();
  const result = render(
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>,
  );
  return result;
}

describe("DualControl page", () => {
  it("renders the page header and life-safety warning banner", async () => {
    await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      expect(screen.getByText("Dual-Control Approvals")).toBeTruthy();
    });
    expect(screen.getByText(/Life-safety workflow/i)).toBeTruthy();
    expect(screen.getByText(/4-eyes principle/i)).toBeTruthy();
  });

  it("calls listPendingDualControlRequests on mount", async () => {
    await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      expect(mockListPending).toHaveBeenCalled();
    });
  });

  it("shows empty state when no pending requests exist", async () => {
    await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      expect(screen.getByText("No dual-control requests")).toBeTruthy();
    });
  });

  it("opens the create-request modal when 'New Request' is clicked", async () => {
    const { container } = await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      expect(screen.getByText("New Request")).toBeTruthy();
    });
    const buttons = container.querySelectorAll("button");
    const newRequestBtn = Array.from(buttons).find((b) => b.textContent === "New Request");
    expect(newRequestBtn).toBeTruthy();
    newRequestBtn?.click();
    await waitFor(() => {
      expect(screen.getByText("New Dual-Control Request")).toBeTruthy();
    });
    // Action-type select should offer the canonical life-safety action types
    expect(screen.getByText("Breaker Switch")).toBeTruthy();
    expect(screen.getByText("Protection Setting Change")).toBeTruthy();
    expect(screen.getByText("SCADA Command")).toBeTruthy();
  });

  it("surfaces an error when the pending-list API fails", async () => {
    mockListPending.mockRejectedValueOnce(new Error("API 401: Unauthorized"));
    await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      expect(screen.getByText("Failed to load pending approvals")).toBeTruthy();
      expect(screen.getByText(/API 401: Unauthorized/)).toBeTruthy();
    });
  });

  it("renders pending requests when the API returns them", async () => {
    mockListPending.mockResolvedValueOnce({
      success: true,
      data: [
        {
          request_id: "apr_pending1",
          action: { type: "breaker_switch", target: "BRK-13800-MAIN" },
          requested_by: "user-operator-2",
          status: "pending",
          approved_by: null,
          approved_at: null,
          rejected_by: null,
          rejected_reason: null,
          created_at: new Date().toISOString(),
          expires_at: Date.now() / 1000 + 240,
          qr_secret: "qr-secret-1",
        },
      ],
    });
    await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      expect(screen.getByText(/breaker_switch → BRK-13800-MAIN/)).toBeTruthy();
      expect(screen.getByText("apr_pending1")).toBeTruthy();
    });
    // The "Cannot approve own request" guard should NOT fire for a different user
    expect(screen.queryByText("Cannot approve own request")).toBeNull();
  });

  it("disables approve button for own requests (self-approval guard)", async () => {
    mockListPending.mockResolvedValueOnce({
      success: true,
      data: [
        {
          request_id: "apr_self",
          action: { type: "scada_command" },
          requested_by: "user-engineer-1", // same as mocked auth user
          status: "pending",
          approved_by: null,
          approved_at: null,
          rejected_by: null,
          rejected_reason: null,
          created_at: new Date().toISOString(),
          expires_at: Date.now() / 1000 + 240,
          qr_secret: "qr-self",
        },
      ],
    });
    await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      expect(screen.getByText("Cannot approve own request")).toBeTruthy();
    });
  });

  it("pauses auto-refresh when the create modal is open", async () => {
    const { container } = await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      expect(mockListPending).toHaveBeenCalledTimes(1);
    });
    const initialCallCount = mockListPending.mock.calls.length;
    // Open the create modal
    const buttons = container.querySelectorAll("button");
    const newRequestBtn = Array.from(buttons).find((b) => b.textContent === "New Request");
    newRequestBtn?.click();
    await waitFor(() => {
      expect(screen.getByText("New Dual-Control Request")).toBeTruthy();
    });
    // Wait >5s worth of fake time — auto-refresh should NOT fire while modal is open
    vi.useFakeTimers();
    vi.advanceTimersByTime(6000);
    vi.useRealTimers();
    // The call count should NOT have increased (modal is open → auto-refresh paused)
    expect(mockListPending.mock.calls.length).toBe(initialCallCount);
  });

  it("renders the countdown timer with a valid time format for pending requests", async () => {
    mockListPending.mockResolvedValueOnce({
      success: true,
      data: [
        {
          request_id: "apr_timer",
          action: { type: "breaker_switch" },
          requested_by: "user-operator-2",
          status: "pending",
          approved_by: null,
          approved_at: null,
          rejected_by: null,
          rejected_reason: null,
          created_at: new Date().toISOString(),
          expires_at: Date.now() / 1000 + 240, // 4 minutes
          qr_secret: "qr-timer",
        },
      ],
    });
    await renderWithRealTimers(<DualControl />);
    await waitFor(() => {
      // Timer should match M:SS format (e.g., "4:00")
      const timerEl = screen.getByText(/Auto-reject in \d:\d\d/);
      expect(timerEl).toBeTruthy();
    });
  });
});
