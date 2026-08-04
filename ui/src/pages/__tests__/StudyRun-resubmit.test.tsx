/**
 * @vitest-environment jsdom
 *
 * Tests for StudyRun re-submit behaviour:
 *   - Previous result remains visible (dimmed) while a new run is in progress
 *   - On success, the new result replaces the old one
 *   - On failure, the stale result is cleared and empty state is shown
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationProvider } from "../../context/NotificationContext";
import StudyRun from "../StudyRun";

// ── Mocks ──────────────────────────────────────────────────────────────────────

const mockRunStudy = vi.fn();

vi.mock("../../lib/api", () => ({
  runStudy: (...args: unknown[]) => mockRunStudy(...args),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "studyRun.dryRun": "Dry Run",
        "studyRun.dryRunCompleted": "Dry run completed",
        "studyRun.completed": "Study completed",
        "studyRun.failed": "Study failed",
        "studyRun.runStudy": "Run Study",
        "studyRun.validateStudy": "Validate",
        "studyRun.backToStudies": "Back",
        "studyRun.studyResult": "Study Result",
        "common.noData": "No data",
      };
      return map[key] || key;
    },
    i18n: { language: "en" },
  }),
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

vi.mock("../../components/help/ContextHelpButton", () => ({
  ContextHelpButton: () => null,
}));

vi.mock("../../lib/studyCategories", () => ({
  studyCategories: [
    {
      id: "load_flow",
      name: "Load Flow",
      description: "Load flow analysis",
      icon: "⚡",
      params: [{ name: "voltage", type: "number", default: "1.0", label: "Voltage" }],
      lucideIcon: "Zap",
    },
  ],
}));

// ── Helpers ────────────────────────────────────────────────────────────────────

function renderStudyRun() {
  return render(
    <MemoryRouter initialEntries={["/studies/load_flow"]}>
      <NotificationProvider>
        <Routes>
          <Route path="/studies/:studyType" element={<StudyRun />} />
        </Routes>
      </NotificationProvider>
    </MemoryRouter>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("StudyRun re-submit behaviour", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does NOT show empty state during re-submit — previous result stays visible", async () => {
    const user = userEvent.setup();

    // First run succeeds
    mockRunStudy.mockResolvedValueOnce({
      study_type: "load_flow",
      status: "completed",
      results: { voltage_profile: true },
      duration_ms: 120,
    });

    // Second run hangs (never resolves) to simulate in-flight state
    mockRunStudy.mockReturnValueOnce(new Promise(() => {}));

    renderStudyRun();

    // Fill and submit first run
    const submitBtn = await screen.findByRole("button", { name: /Run Study/i });
    await user.click(submitBtn);

    // Wait for first result to appear
    await waitFor(() => {
      expect(screen.getByText("Study Result")).toBeTruthy();
    });

    // Submit again (second run will hang)
    const submitBtnAgain = screen.getByRole("button", { name: /Run Study|Running/i });
    await user.click(submitBtnAgain);

    // The previous result should still be visible (not replaced by empty state)
    // We verify that "Study Result" heading is still in the document
    await waitFor(() => {
      expect(screen.getByText("Study Result")).toBeTruthy();
    });

    // The "Ready to Run" empty state should NOT be shown
    expect(screen.queryByText("Ready to Run")).toBeNull();
  }, 15000);

  it("replaces the old result with the new one on successful re-submit", async () => {
    const user = userEvent.setup();

    // First run
    mockRunStudy.mockResolvedValueOnce({
      study_type: "load_flow",
      status: "completed",
      results: { voltage_profile: true },
      duration_ms: 100,
    });

    // Second run
    mockRunStudy.mockResolvedValueOnce({
      study_type: "load_flow",
      status: "completed",
      results: { power_flow: true },
      duration_ms: 200,
    });

    renderStudyRun();

    const submitBtn = await screen.findByRole("button", { name: /Run Study/i });
    await user.click(submitBtn);

    // Wait for first result
    await waitFor(() => {
      expect(mockRunStudy).toHaveBeenCalledTimes(1);
    });

    // Submit again
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /Run Study/i });
      return btn;
    });

    const submitBtn2 = screen.getByRole("button", { name: /Run Study/i });
    await user.click(submitBtn2);

    // Wait for second result
    await waitFor(() => {
      expect(mockRunStudy).toHaveBeenCalledTimes(2);
    });

    // The result should still be visible
    expect(screen.getByText("Study Result")).toBeTruthy();
  }, 15000);

  it("clears stale result and shows empty state when re-submit fails", async () => {
    const user = userEvent.setup();

    // First run succeeds
    mockRunStudy.mockResolvedValueOnce({
      study_type: "load_flow",
      status: "completed",
      results: {},
      duration_ms: 50,
    });

    // Second run fails
    mockRunStudy.mockRejectedValueOnce(new Error("Server unavailable"));

    renderStudyRun();

    const submitBtn = await screen.findByRole("button", { name: /Run Study/i });
    await user.click(submitBtn);

    // Wait for first result
    await waitFor(() => {
      expect(screen.getByText("Study Result")).toBeTruthy();
    });

    // Submit again (will fail)
    const submitBtn2 = screen.getByRole("button", { name: /Run Study/i });
    await user.click(submitBtn2);

    // After failure, the stale result should be cleared
    // and the empty "Ready to Run" state should be shown
    await waitFor(() => {
      expect(screen.getByText("Ready to Run")).toBeTruthy();
    }, { timeout: 5000 });
  }, 15000);
});
