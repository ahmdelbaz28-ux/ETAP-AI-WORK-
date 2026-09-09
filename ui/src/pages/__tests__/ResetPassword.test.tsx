import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import ResetPassword from "../ResetPassword";

/**
 * @vitest-environment jsdom
 *
 * Tests for the ResetPassword page (forgot-password completion flow).
 * Backend contract: POST /api/v1/auth/reset-password {token, new_password}.
 */

// Mock NotificationContext
vi.mock("../../context/NotificationContext", () => ({
  useNotify: () => ({
    notify: vi.fn(),
  }),
}));

// Mock API base URL
vi.mock("../../lib/api-config", () => ({
  API_BASE_URL: "http://localhost:8000",
}));

function renderWithToken(token: string | null) {
  const entry = token === null ? "/reset-password" : `/reset-password?token=${token}`;
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <ResetPassword />
    </MemoryRouter>,
  );
}

describe("ResetPassword Page", () => {
  it("shows invalid-link state when token is missing and never calls the API", () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;
    renderWithToken(null);
    expect(screen.getByText("Invalid link")).toBeInTheDocument();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("blocks mismatched passwords client-side without calling the API", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;
    renderWithToken("tok-123");
    fireEvent.change(screen.getByTestId("reset-new-password"), { target: { value: "NewPass!234" } });
    fireEvent.change(screen.getByTestId("reset-confirm-password"), { target: { value: "Other!999" } });
    fireEvent.click(screen.getByTestId("reset-submit"));
    expect(await screen.findByTestId("reset-error")).toBeInTheDocument();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("blocks short passwords client-side without calling the API", async () => {
    const mockFetch = vi.fn();
    globalThis.fetch = mockFetch;
    renderWithToken("tok-123");
    fireEvent.change(screen.getByTestId("reset-new-password"), { target: { value: "short" } });
    fireEvent.change(screen.getByTestId("reset-confirm-password"), { target: { value: "short" } });
    fireEvent.click(screen.getByTestId("reset-submit"));
    expect(await screen.findByTestId("reset-error")).toBeInTheDocument();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("submits exact contract and shows success", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ message: "Password has been reset successfully" }),
    });
    globalThis.fetch = mockFetch;
    renderWithToken("tok-abc");
    fireEvent.change(screen.getByTestId("reset-new-password"), { target: { value: "NewPass!234" } });
    fireEvent.change(screen.getByTestId("reset-confirm-password"), { target: { value: "NewPass!234" } });
    fireEvent.click(screen.getByTestId("reset-submit"));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/auth/reset-password",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ token: "tok-abc", new_password: "NewPass!234" }),
        }),
      );
    });
    expect(await screen.findByTestId("reset-success")).toBeInTheDocument();
  });

  it("shows server expired/invalid message without logging the token", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Invalid or expired reset token" }),
    });
    globalThis.fetch = mockFetch;
    renderWithToken("tok-stale");
    fireEvent.change(screen.getByTestId("reset-new-password"), { target: { value: "NewPass!234" } });
    fireEvent.change(screen.getByTestId("reset-confirm-password"), { target: { value: "NewPass!234" } });
    fireEvent.click(screen.getByTestId("reset-submit"));
    expect(await screen.findByTestId("reset-error")).toHaveTextContent("Invalid or expired reset token");
  });
});
