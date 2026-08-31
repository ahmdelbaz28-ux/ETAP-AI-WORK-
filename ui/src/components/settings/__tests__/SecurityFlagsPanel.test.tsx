/**
 * @vitest-environment jsdom
 *
 * P7d — SecurityFlagsPanel tests
 * Covers: backend-truth rendering, backend-authoritative toggle (state comes
 * from the PATCH response, never from the click intent), failure paths, and
 * absence of secret/storage side effects.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SecurityFlagsPanel } from "../SecurityFlagsPanel";

// jsdom userEvent flows are slow in this repo's CI environment — give headroom.
vi.setConfig({ testTimeout: 15000 });

vi.mock("../../../lib/api", () => ({
  fetchFeatureFlags: vi.fn(),
  patchFeatureFlag: vi.fn(),
}));

import { fetchFeatureFlags, patchFeatureFlag } from "../../../lib/api";

const mockedFetch = vi.mocked(fetchFeatureFlags);
const mockedPatch = vi.mocked(patchFeatureFlag);

const BACKEND_FLAGS = {
  success: true,
  data: [
    {
      key: "harmonic_analysis",
      enabled: false,
      status: "beta",
      description: "Harmonic analysis (IEEE 519) - in development",
      effective_enabled: false,
    },
    {
      key: "mock_gis_provider",
      enabled: false,
      status: "internal",
      description: "Allow MockGISProvider as fallback in non-dev environments",
      effective_enabled: false,
    },
  ],
  total: 2,
  env: "production",
};

function renderPanel() {
  const notify = vi.fn();
  render(<SecurityFlagsPanel notify={notify} />);
  return { notify };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  mockedFetch.mockResolvedValue(BACKEND_FLAGS);
});

// ── Rendering ──────────────────────────────────────────────────────────────────

describe("SecurityFlagsPanel — rendering", () => {
  it("renders every flag from the backend registry (backend truth)", async () => {
    renderPanel();
    await waitFor(() => expect(screen.getByTestId("flag-row-harmonic_analysis")).toBeTruthy());
    expect(screen.getByTestId("flag-row-mock_gis_provider")).toBeTruthy();
    expect(screen.getByTestId("feature-flags-env").textContent).toContain("production");
  });

  it("reflects the backend enabled state, not a client default", async () => {
    renderPanel();
    const toggle = (await screen.findByRole("switch", {
      name: "Toggle harmonic_analysis",
    })) as HTMLButtonElement;
    expect(toggle.getAttribute("aria-checked")).toBe("false");

    // ── Toggle (backend-authoritative) ─────────────────────────────────────────────

    describe("SecurityFlagsPanel — toggle", () => {
      it("calls PATCH with the inverted value and applies the BACKEND response", async () => {
        const user = userEvent.setup();
        // Backend rejects the intent: returns enabled=false even though the UI
        // requested true — the panel must show the backend's value.
        mockedPatch.mockResolvedValue({
          success: true,
          data: {
            ...BACKEND_FLAGS.data[0],
            enabled: false,
            previous_enabled: false,
            env: "production",
          },
          env: undefined,
          trace_id: undefined,
        } as Awaited<ReturnType<typeof patchFeatureFlag>>);
        renderPanel();

        const toggle = await screen.findByRole("switch", {
          name: "Toggle harmonic_analysis",
        });
        await user.click(toggle);

        await waitFor(() => expect(mockedPatch).toHaveBeenCalledWith("harmonic_analysis", true));
        await waitFor(() =>
          expect(
            (
              screen.getByRole("switch", { name: "Toggle harmonic_analysis" }) as HTMLButtonElement
            ).getAttribute("aria-checked"),
          ).toBe("false"),
        );
      });

      it("applies the backend state and notifies success when PATCH succeeds", async () => {
        const user = userEvent.setup();
        mockedPatch.mockResolvedValue({
          success: true,
          data: {
            ...BACKEND_FLAGS.data[0],
            enabled: true,
            previous_enabled: false,
            env: "production",
          },
          env: undefined,
          trace_id: undefined,
        } as Awaited<ReturnType<typeof patchFeatureFlag>>);
        const { notify } = renderPanel();

        await user.click(await screen.findByRole("switch", { name: "Toggle harmonic_analysis" }));

        await waitFor(() =>
          expect(
            (
              screen.getByRole("switch", { name: "Toggle harmonic_analysis" }) as HTMLButtonElement
            ).getAttribute("aria-checked"),
          ).toBe("true"),
        );
        expect(notify.mock.calls.some(([type]) => type === "success")).toBe(true);
      });

      it("keeps backend truth and notifies error when PATCH fails", async () => {
        const user = userEvent.setup();
        mockedPatch.mockRejectedValue(new Error("403 Forbidden"));
        const { notify } = renderPanel();

        await user.click(await screen.findByRole("switch", { name: "Toggle harmonic_analysis" }));

        await waitFor(() =>
          expect(notify.mock.calls.some(([type]) => type === "error")).toBe(true),
        );
        // State unchanged (backend truth preserved, no optimistic update)
        expect(
          (
            screen.getByRole("switch", { name: "Toggle harmonic_analysis" }) as HTMLButtonElement
          ).getAttribute("aria-checked"),
        ).toBe("false");
      });
    });

    // ── Load errors ────────────────────────────────────────────────────────────────

    describe("SecurityFlagsPanel — load errors", () => {
      it("surfaces load failure via notify without crashing", async () => {
        mockedFetch.mockRejectedValue(new Error("backend unreachable"));
        const { notify } = renderPanel();
        await waitFor(() => expect(notify).toHaveBeenCalled());
        const errorCall = notify.mock.calls.find(([type]) => type === "error");
        expect(String(errorCall?.[1])).toContain("backend unreachable");
      });
    });
  });

  it("writes nothing to localStorage or sessionStorage", async () => {
    renderPanel();
    await waitFor(() => expect(screen.getByTestId("flag-row-harmonic_analysis")).toBeTruthy());
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
