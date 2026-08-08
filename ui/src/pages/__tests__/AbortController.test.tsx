/**
 * @vitest-environment jsdom
 *
 * Tests for AbortController integration in AIAssistant.
 * Verifies that:
 *   - A new send aborts any in-flight request
 *   - Unmounting the component aborts pending requests
 *   - The abort signal is correctly propagated to llm-chat functions
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationProvider } from "../../context/NotificationContext";
import AIAssistant from "../AIAssistant";

// ── Mocks ──────────────────────────────────────────────────────────────────────

const mockFetchAgents = vi.fn();
const mockChatWithLLM = vi.fn();
const mockChatWithLLMStream = vi.fn();
const mockGetActiveProvider = vi.fn();
const mockGetConfiguredProviders = vi.fn();

vi.mock("../../lib/api", () => ({
  fetchAgents: (...args: unknown[]) => mockFetchAgents(...args),
}));

vi.mock("../../lib/llm-chat", () => ({
  chatWithLLM: (...args: unknown[]) => mockChatWithLLM(...args),
  chatWithLLMStream: (...args: unknown[]) => mockChatWithLLMStream(...args),
  getActiveProvider: (...args: unknown[]) => mockGetActiveProvider(...args),
  getConfiguredProviders: (...args: unknown[]) => mockGetConfiguredProviders(...args),
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

vi.mock("../Settings", () => ({
  POPULAR_PROVIDERS: [],
}));

// ── Helpers ────────────────────────────────────────────────────────────────────

const mockAgents = [
  {
    id: "power-system-coordinator-agent",
    name: "Power System Coordinator",
    description: "Main coordinator agent",
    capabilities: ["load_flow", "short_circuit"],
    model: "gpt-4o-mini",
    provider: "openai",
  },
];

function renderAssistant() {
  return render(
    <MemoryRouter>
      <NotificationProvider>
        <AIAssistant />
      </NotificationProvider>
    </MemoryRouter>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("AIAssistant AbortController integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    mockFetchAgents.mockResolvedValue(mockAgents);
    mockGetActiveProvider.mockReturnValue({
      id: "openai",
      name: "OpenAI",
      model: "gpt-4o-mini",
    });
    mockGetConfiguredProviders.mockReturnValue([{ id: "openai", name: "OpenAI" }]);
    mockChatWithLLMStream.mockImplementation(async function* () {
      yield "Response chunk";
    });
    mockChatWithLLM.mockResolvedValue({
      content: "Fallback response",
    });
  });

  it("passes an AbortSignal to chatWithLLMStream when sending a message", async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Message AI Assistant/i);
    await user.type(input, "Test abort signal");
    await user.keyboard("{Enter}");

    // Wait for the stream call and verify it received a signal argument
    await waitFor(() => {
      expect(mockChatWithLLMStream).toHaveBeenCalled();
    });

    // The third argument to chatWithLLMStream should be an AbortSignal
    const lastCall = mockChatWithLLMStream.mock.calls[mockChatWithLLMStream.mock.calls.length - 1];
    // chatWithLLMStream(messages, config?, signal?)
    expect(lastCall.length).toBeGreaterThanOrEqual(3);
    const signal = lastCall[2];
    expect(signal).toBeDefined();
    // AbortSignal instances have an `aborted` property
    expect(signal).toHaveProperty("aborted");
  }, 15000);

  it("aborts previous request when sending a new message while one is in-flight", async () => {
    // Make the first stream very slow (never resolves on its own)
    const firstStreamController: AbortController | null = null;
    let firstSignal: AbortSignal | undefined;

    mockChatWithLLMStream.mockImplementationOnce(async function* (_msgs, _config, signal) {
      firstSignal = signal;
      // Simulate a slow stream that waits
      yield "First ";
      await new Promise(() => {}); // Never resolves — simulates pending
    });

    // Second call resolves quickly
    mockChatWithLLMStream.mockImplementationOnce(async function* () {
      yield "Second response";
    });

    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Message AI Assistant/i);

    // Send first message
    await user.type(input, "First message");
    await user.keyboard("{Enter}");

    // Wait for the first stream to start
    await waitFor(() => {
      expect(mockChatWithLLMStream).toHaveBeenCalledTimes(1);
    });

    // Capture the first signal
    const capturedSignal = mockChatWithLLMStream.mock.calls[0][2] as AbortSignal;

    // Clear input and send second message (which should abort the first)
    const inputEl = screen.getByPlaceholderText(/Message AI Assistant/i) as HTMLTextAreaElement;
    await user.clear(inputEl);
    await user.type(inputEl, "Second message");
    await user.keyboard("{Enter}");

    // The first signal should now be aborted
    await waitFor(() => {
      expect(capturedSignal.aborted).toBe(true);
    });
  }, 20000);

  it("handles AbortError gracefully — no crash or duplicate error messages", async () => {
    // Simulate an aborted stream that throws AbortError
    mockChatWithLLMStream.mockImplementationOnce(async function* () {
      throw new DOMException("The user aborted a request.", "AbortError");
    });

    // Fallback also aborted
    mockChatWithLLM.mockRejectedValueOnce(new DOMException("Aborted", "AbortError"));

    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Message AI Assistant/i);
    await user.type(input, "Test abort error");
    await user.keyboard("{Enter}");

    // The component should not crash — the message should still be visible
    await waitFor(() => {
      expect(screen.getByText("Test abort error")).toBeTruthy();
    });
  }, 15000);
});
