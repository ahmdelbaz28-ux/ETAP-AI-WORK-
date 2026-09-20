import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QuickActionsBar } from "../QuickActionsBar";
import { useChatStore } from "../../../store/chatStore";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, defaultValue: string) => defaultValue || key,
    i18n: { language: "en" },
  }),
}));

vi.mock("../../../lib/api", () => ({
  fetchFeatureFlags: vi.fn().mockResolvedValue({
    success: true,
    data: [
      { key: "motor_starting", effective_enabled: false },
      { key: "harmonic_analysis", effective_enabled: false },
      { key: "transient_stability", effective_enabled: false },
    ],
  }),
}));

describe("QuickActionsBar", () => {
  beforeEach(() => {
    useChatStore.setState({
      projectId: null,
      streamStatus: "idle",
      messages: [],
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders all 8 quick action buttons", async () => {
    render(<QuickActionsBar />);
    expect(screen.getByTestId("quick-action-load_flow")).toBeDefined();
    expect(screen.getByTestId("quick-action-short_circuit")).toBeDefined();
    expect(screen.getByTestId("quick-action-arc_flash")).toBeDefined();
    expect(screen.getByTestId("quick-action-protection_coordination")).toBeDefined();
    expect(screen.getByTestId("quick-action-motor_starting")).toBeDefined();
    expect(screen.getByTestId("quick-action-harmonic")).toBeDefined();
    expect(screen.getByTestId("quick-action-stability")).toBeDefined();
    expect(screen.getByTestId("quick-action-report")).toBeDefined();
  });

  it("shows warning and does not trigger sendMessage when no project is selected", async () => {
    const sendMessageSpy = vi.fn();
    useChatStore.setState({ projectId: null, sendMessage: sendMessageSpy });

    render(<QuickActionsBar />);
    const loadFlowBtn = screen.getByTestId("quick-action-load_flow");
    fireEvent.click(loadFlowBtn);

    expect(sendMessageSpy).not.toHaveBeenCalled();
    expect(screen.getByTestId("quick-actions-warning")).toBeDefined();
  });

  it("calls sendMessage through normal pipeline when project is selected", async () => {
    const sendMessageSpy = vi.fn().mockResolvedValue(true);
    useChatStore.setState({ projectId: "proj_cairo_substation", sendMessage: sendMessageSpy });

    render(<QuickActionsBar />);
    const loadFlowBtn = screen.getByTestId("quick-action-load_flow");
    fireEvent.click(loadFlowBtn);

    expect(sendMessageSpy).toHaveBeenCalledWith(
      expect.stringContaining("Load Flow")
    );
  });

  it("disables buttons whose feature flags are not effective_enabled", async () => {
    render(<QuickActionsBar />);
    await waitFor(() => {
      const motorBtn = screen.getByTestId("quick-action-motor_starting") as HTMLButtonElement;
      expect(motorBtn.disabled).toBe(true);
    });
  });
});
