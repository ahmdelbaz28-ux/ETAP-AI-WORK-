/**
 * P6 feature flag tests.
 *
 * Pins the chat_first_ui behavior per spec Section 13:
 *  - OFF (default)         → legacy UI active
 *  - ON                    → ChatWorkspace primary
 *  - missing / malformed / server error → fail-closed → OFF
 *  - build-time override   → VITE_CHAT_FIRST_UI=true
 *
 * The flag is a UI routing gate only; it is NOT a security boundary.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFeatureFlagsMock = vi.fn();
vi.mock("../../../lib/api", () => ({
  fetchFeatureFlags: () => fetchFeatureFlagsMock(),
}));

import { isChatFirstUiEnabled, CHAT_FIRST_UI_KEY } from "../../lib/chat-first-ui";

describe("P6 chat_first_ui feature flag — fail-closed", () => {
  beforeEach(() => {
    fetchFeatureFlagsMock.mockReset();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("default OFF when backend returns no chat_first_ui entry", async () => {
    fetchFeatureFlagsMock.mockResolvedValueOnce({ data: [] });
    const enabled = await isChatFirstUiEnabled();
    expect(enabled).toBe(false);
  });

  it("default OFF when backend returns chat_first_ui but effective_enabled=false", async () => {
    fetchFeatureFlagsMock.mockResolvedValueOnce({
      data: [{ key: CHAT_FIRST_UI_KEY, effective_enabled: false }],
    });
    expect(await isChatFirstUiEnabled()).toBe(false);
  });

  it("ON when backend returns chat_first_ui with effective_enabled=true", async () => {
    fetchFeatureFlagsMock.mockResolvedValueOnce({
      data: [{ key: CHAT_FIRST_UI_KEY, effective_enabled: true }],
    });
    expect(await isChatFirstUiEnabled()).toBe(true);
  });

  it("fail-closed on backend error (network / 500)", async () => {
    fetchFeatureFlagsMock.mockRejectedValueOnce(new Error("API 500"));
    expect(await isChatFirstUiEnabled()).toBe(false);
  });

  it("fail-closed on malformed payload (no `data` key)", async () => {
    fetchFeatureFlagsMock.mockResolvedValueOnce({}); // missing `data`
    expect(await isChatFirstUiEnabled()).toBe(false);
  });

  it("fail-closed on `data` of the wrong type", async () => {
    fetchFeatureFlagsMock.mockResolvedValueOnce({ data: "not-an-array" });
    expect(await isChatFirstUiEnabled()).toBe(false);
  });

  it("ignores other flag keys (does not flip on by accident)", async () => {
    fetchFeatureFlagsMock.mockResolvedValueOnce({
      data: [{ key: "some_other_flag", effective_enabled: true }],
    });
    expect(await isChatFirstUiEnabled()).toBe(false);
  });
});
