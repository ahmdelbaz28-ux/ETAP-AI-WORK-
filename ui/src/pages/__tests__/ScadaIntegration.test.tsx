import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ScadaIntegration from "../ScadaIntegration";

/**
 * @vitest-environment jsdom
 */

// Mock useAuth
vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: {
      id: "user-eng-42",
      email: "engineer@grid.internal",
      name: "Lead Protection Engineer",
      role: "engineer",
    },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    register: vi.fn(),
    refreshToken: vi.fn(),
  }),
}));

// Mock NotificationContext
vi.mock("../../context/NotificationContext", () => ({
  useNotify: () => ({
    notify: vi.fn(),
  }),
}));

// Mock secure settings
vi.mock("../../lib/api-config", () => ({
  API_BASE_URL: "http://localhost:8000",
  getDeobfuscatedSettings: vi.fn().mockResolvedValue({
    SCADA_SERVER_URL: "http://localhost:8080/zenon",
    SCADA_API_KEY: "test-key",
    SCADA_PROJECT_NAME: "ETAP_Zenon_Sync",
    SCADA_SYNC_INTERVAL_SEC: "5",
  }),
  refreshSettingsCache: vi.fn().mockResolvedValue(undefined),
  setEncryptedSettings: vi.fn().mockResolvedValue(undefined),
}));

// Mock tokenStorage
vi.mock("../../lib/tokenStorage", () => ({
  getAuthToken: () => "mock-jwt-token-engineer",
}));

describe("ScadaIntegration Page — Substation Control Bay & SBO Gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/v1/scada/control/pending")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              total: 1,
              data: [
                {
                  action_id: "act-test-9999",
                  device_id: "CB-01",
                  action_type: "breaker_open",
                  target_value: 0.0,
                  reason: "Routine transformer line maintenance",
                  requested_by_user_id: "user-eng-42",
                  requested_by_role: "engineer",
                  created_at: new Date().toISOString(),
                  expires_at: new Date(Date.now() + 300000).toISOString(),
                },
              ],
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            data: { points: [] },
          }),
      });
    });
  });

  it("renders Substation Control Bay and switchgear components", async () => {
    render(
      <MemoryRouter>
        <ScadaIntegration />
      </MemoryRouter>,
    );

    // Verify Substation Control Bay header and active interlock badge
    expect(screen.getByText(/Substation Control Bay/i)).toBeTruthy();
    expect(screen.getByText(/CTI ≥ 0.2s & N-R Interlock Active/i)).toBeTruthy();
    expect(screen.getByText(/ROLE: ENGINEER/i)).toBeTruthy();

    // Verify Breakers and OLTC equipment
    expect(screen.getByText("CB-01")).toBeTruthy();
    expect(screen.getByText("CB-02")).toBeTruthy();
    expect(screen.getByText("CB-Tie-01")).toBeTruthy();
    expect(screen.getByText("XF1-Tap")).toBeTruthy();
  });

  it("renders Dual-Control Authorization Queue with pending actions", async () => {
    render(
      <MemoryRouter>
        <ScadaIntegration />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Dual-Control Authorization Queue/i)).toBeTruthy();
      expect(screen.getByText(/Routine transformer line maintenance/i)).toBeTruthy();
    });
  });

  it("opens SBO confirmation modal when clicking Trip / Open on CB-01", async () => {
    render(
      <MemoryRouter>
        <ScadaIntegration />
      </MemoryRouter>,
    );

    // Find Trip / Open button for CB-01
    const tripButtons = screen.getAllByRole("button", { name: /Trip \/ Open/i });
    expect(tripButtons.length).toBeGreaterThan(0);

    fireEvent.click(tripButtons[0]);

    // Modal should be open
    await waitFor(() => {
      expect(screen.getByText(/Select-Before-Operate \(SBO\) Gate/i)).toBeTruthy();
      expect(screen.getByText(/Automated Pre-Flight Engineering Checks/i)).toBeTruthy();
      expect(screen.getByText(/Engineering Rationale \/ Work Order/i)).toBeTruthy();
    });
  });
});
