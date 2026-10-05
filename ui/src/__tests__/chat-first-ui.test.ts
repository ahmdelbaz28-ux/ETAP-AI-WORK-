import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchFeatureFlagsMock = vi.fn();
vi.mock("../lib/api", () => ({
  fetchFeatureFlags: () => fetchFeatureFlagsMock(),
}));

const getAuthTokenMock = vi.fn();
vi.mock("../lib/tokenStorage", () => ({
  getAuthToken: () => getAuthTokenMock(),
}));

import {
  CHAT_FIRST_UI_KEY,
  enterChatFirst,
  isChatFirstUiEnabled,
} from "../lib/chat-first-ui";

describe("chat-first-ui gateway and auth token checks", () => {
  beforeEach(() => {
    fetchFeatureFlagsMock.mockReset();
    getAuthTokenMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns effective enabled state when backend provides flag", async () => {
    getAuthTokenMock.mockReturnValue("mock-valid-jwt");
    fetchFeatureFlagsMock.mockResolvedValueOnce({
      data: [{ key: CHAT_FIRST_UI_KEY, effective_enabled: true }],
    });

    const enabled = await isChatFirstUiEnabled();
    expect(enabled).toBe(true);
    expect(fetchFeatureFlagsMock).toHaveBeenCalledTimes(1);
  });

  it("returns false when backend provides flag with effective_enabled=false", async () => {
    getAuthTokenMock.mockReturnValue("mock-valid-jwt");
    fetchFeatureFlagsMock.mockResolvedValueOnce({
      data: [{ key: CHAT_FIRST_UI_KEY, effective_enabled: false }],
    });

    const enabled = await isChatFirstUiEnabled();
    expect(enabled).toBe(false);
  });

  it("returns false when backend fails or throws network error", async () => {
    getAuthTokenMock.mockReturnValue("mock-valid-jwt");
    fetchFeatureFlagsMock.mockRejectedValueOnce(new Error("500 Internal Server Error"));

    const enabled = await isChatFirstUiEnabled();
    expect(enabled).toBe(false);
  });

  it("dispatches enter-chat-first event on enterChatFirst()", () => {
    const listener = vi.fn();
    window.addEventListener("enter-chat-first", listener);

    enterChatFirst();

    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener("enter-chat-first", listener);
  });
});
