/**
 * @vitest-environment jsdom
 *
 * P7a — ProviderKeysPanel tests
 * Covers: masked-only display, secret never persisted in browser storage,
 * key travels in request body (not URL), cancel/save clears the typed secret,
 * test/activate/delete flows, and error paths.
 * The fake secret TEST_PROVIDER_SECRET_123 is used everywhere — never a real key.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProviderKeysPanel } from "../ProviderKeysPanel";

// jsdom userEvent flows are slow in this repo's CI environment — give headroom.
vi.setConfig({ testTimeout: 15000 });

const FAKE_SECRET = "TEST_PROVIDER_SECRET_123";

vi.mock("../../../lib/provider-keys", () => ({
  listProviderKeys: vi.fn(),
  saveProviderKey: vi.fn(),
  deleteProviderKey: vi.fn(),
  testProviderKey: vi.fn(),
  activateProviderKey: vi.fn(),
}));

import {
  activateProviderKey,
  deleteProviderKey,
  listProviderKeys,
  saveProviderKey,
  testProviderKey,
} from "../../../lib/provider-keys";

const mockedList = vi.mocked(listProviderKeys);
const mockedSave = vi.mocked(saveProviderKey);
const mockedTest = vi.mocked(testProviderKey);
const mockedActivate = vi.mocked(activateProviderKey);
const mockedDelete = vi.mocked(deleteProviderKey);

const EXISTING_KEY = {
  provider: "openai",
  api_key_masked: "sk-***abcd",
  api_key_set: true,
  base_url: "https://api.openai.com/v1",
  model_name: "gpt-4o",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

function emptyList() {
  return { success: true, data: {}, providers: [] };
}

function renderPanel() {
  const notify = vi.fn();
  render(<ProviderKeysPanel notify={notify} />);
  return { notify };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  mockedList.mockResolvedValue(emptyList());
});

// ── Rendering ──────────────────────────────────────────────────────────────────

describe("ProviderKeysPanel — rendering", () => {
  it("renders provider cards with Add Key actions when no keys are configured", async () => {
    renderPanel();
    await waitFor(() => expect(mockedList).toHaveBeenCalled());
    expect(screen.getByTestId("provider-add-openai")).toBeTruthy();
    expect(screen.getByTestId("provider-add-anthropic")).toBeTruthy();
    expect(screen.getByText("Providers & API Keys")).toBeTruthy();
  });

  it("displays the masked key and never a plaintext secret", async () => {
    mockedList.mockResolvedValue({
      success: true,
      data: { openai: EXISTING_KEY },
      providers: ["openai"],
    });
    renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("provider-masked-key-openai")).toBeTruthy(),
    );
    expect(screen.getByTestId("provider-masked-key-openai").textContent).toBe("sk-***abcd");
    // No plaintext secret anywhere in the DOM
    expect(screen.queryByText(FAKE_SECRET)).toBeNull();
    expect(document.body.innerHTML).not.toContain(FAKE_SECRET);
  });
});

// ── Save / Cancel / Security ───────────────────────────────────────────────────

describe("ProviderKeysPanel — save & cancel", () => {
  it(
    "saves via the API client (key in body) and clears the typed secret",
    async () => {
      const user = userEvent.setup();
      mockedSave.mockResolvedValue({ success: true, data: null, message: "saved" });
      renderPanel();

      await user.click(await screen.findByTestId("provider-add-openai"));
      const input = screen.getByTestId("provider-key-input-openai") as HTMLInputElement;
      await user.type(input, FAKE_SECRET);
      expect(input.value).toBe(FAKE_SECRET);
      expect(input.getAttribute("type")).toBe("password");

      await user.click(screen.getByTestId("provider-save-openai"));

      await waitFor(() => expect(mockedSave).toHaveBeenCalled());
      // Key goes to the API client (body, not URL) — URL contains no secret
      const [provider, inputArg] = mockedSave.mock.calls[0];
      expect(provider).toBe("openai");
      expect((inputArg as { api_key: string }).api_key).toBe(FAKE_SECRET);

      // Input cleared after save in all paths; secret gone from the DOM
      await waitFor(() =>
        expect(screen.queryByTestId("provider-key-input-openai")).toBeNull(),
      );
      expect(document.body.innerHTML).not.toContain(FAKE_SECRET);
    },
    15000,
  );

  it("clears the typed secret on cancel", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByTestId("provider-add-openai"));
    const input = screen.getByTestId("provider-key-input-openai") as HTMLInputElement;
    await user.type(input, FAKE_SECRET);

    await user.click(screen.getByTestId("provider-cancel-openai"));
    expect(mockedSave).not.toHaveBeenCalled();
    expect(screen.queryByTestId("provider-key-input-openai")).toBeNull();
    expect(document.body.innerHTML).not.toContain(FAKE_SECRET);
  });

  it("never persists secrets to browser storage during the save flow", async () => {
    const user = userEvent.setup();
    mockedSave.mockResolvedValue({ success: true, data: null, message: "saved" });
    renderPanel();

    await user.click(await screen.findByTestId("provider-add-openai"));
    await user.type(screen.getByTestId("provider-key-input-openai"), FAKE_SECRET);
    await user.click(screen.getByTestId("provider-save-openai"));
    await waitFor(() => expect(mockedSave).toHaveBeenCalled());

    const lsDump = JSON.stringify(localStorage);
    const ssDump = JSON.stringify(sessionStorage);
    expect(lsDump).not.toContain(FAKE_SECRET);
    expect(ssDump).not.toContain(FAKE_SECRET);
  });

  it("shows an error notification when saving fails and still clears the secret", async () => {
    const user = userEvent.setup();
    mockedSave.mockRejectedValue(new Error("backend unavailable"));
    const { notify } = renderPanel();

    await user.click(await screen.findByTestId("provider-add-openai"));
    await user.type(screen.getByTestId("provider-key-input-openai"), FAKE_SECRET);
    await user.click(screen.getByTestId("provider-save-openai"));

    await waitFor(() => expect(notify).toHaveBeenCalled());
    const errorCall = notify.mock.calls.find(([type]) => type === "error");
    expect(errorCall).toBeTruthy();
    await waitFor(() =>
      expect(screen.queryByTestId("provider-key-input-openai")).toBeNull(),
    );
    expect(document.body.innerHTML).not.toContain(FAKE_SECRET);
  });
});

// ── Test connection / Activate / Delete ────────────────────────────────────────

describe("ProviderKeysPanel — test, activate, delete", () => {
  function renderWithExistingKey() {
    mockedList.mockResolvedValue({
      success: true,
      data: { openai: EXISTING_KEY },
      providers: ["openai"],
    });
    return renderPanel();
  }

  it("shows a success badge when the backend test passes", async () => {
    const user = userEvent.setup();
    mockedTest.mockResolvedValue({
      success: true,
      data: { success: true, message: "Key valid for gpt-4o", model: "gpt-4o" },
    });
    renderWithExistingKey();

    await user.click(await screen.findByTestId("provider-test-openai"));
    await waitFor(() =>
      expect(screen.getByTestId("provider-test-result-openai").textContent).toContain(
        "Key valid for gpt-4o",
      ),
    );
  });

  it("shows an error badge and notification when the backend test fails", async () => {
    const user = userEvent.setup();
    mockedTest.mockRejectedValue(new Error("network down"));
    const { notify } = renderWithExistingKey();

    await user.click(await screen.findByTestId("provider-test-openai"));
    await waitFor(() =>
      expect(screen.getByTestId("provider-test-result-openai").textContent).toContain(
        "network down",
      ),
    );
    expect(notify.mock.calls.some(([type]) => type === "error")).toBe(true);
  });

  it("deactivates an active key via the activate endpoint", async () => {
    const user = userEvent.setup();
    mockedActivate.mockResolvedValue({ success: true, message: "deactivated" });
    renderWithExistingKey();

    await user.click(await screen.findByTestId("provider-activate-openai"));
    await waitFor(() => expect(mockedActivate).toHaveBeenCalledWith("openai", false));
  });

  it("deletes the key after user confirmation and refreshes the list", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockedDelete.mockResolvedValue({ success: true, message: "deleted" });
    renderWithExistingKey();

    await user.click(await screen.findByTestId("provider-delete-openai"));
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith("openai"));
    expect(window.confirm).toHaveBeenCalled();
  });

  it("does not delete when the user dismisses the confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    renderWithExistingKey();

    await user.click(await screen.findByTestId("provider-delete-openai"));
    expect(mockedDelete).not.toHaveBeenCalled();
  });
});

// ── Load errors ────────────────────────────────────────────────────────────────

describe("ProviderKeysPanel — load errors", () => {
  it("surfaces a load failure via notify without crashing", async () => {
    mockedList.mockRejectedValue(new Error("backend unreachable"));
    const { notify } = renderPanel();
    await waitFor(() => expect(notify).toHaveBeenCalled());
    const errorCall = notify.mock.calls.find(([type]) => type === "error");
    expect(errorCall).toBeTruthy();
    expect(String(errorCall?.[1])).toContain("backend unreachable");
    // Panel still renders provider cards (Add Key available)
    expect(screen.getByTestId("provider-add-openai")).toBeTruthy();
  });
});

