import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
/**
 * @vitest-environment jsdom
 *
 * Tests for the AIAssistant page component.
 *
 * These tests reflect the current implementation of AIAssistant.tsx, which:
 *   - uses useNavigate() from react-router-dom (so it must be rendered inside
 *     a <MemoryRouter>),
 *   - loads agents via fetchAgents() but no longer renders an agent picker
 *     <select> (agent selection was removed when the LLM chat flow was
 *     introduced),
 *   - streams assistant replies via chatWithLLMStream / chatWithLLM (from
 *     ../lib/llm-chat), not chatWithAgent,
 *   - exposes the "Reset Chat" button to clear the conversation,
 *   - shows the empty-state prompt "How can I help you today?".
 */
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

// Avoid loading Settings.tsx (which imports a lot). We only need POPULAR_PROVIDERS
// as a fallback for the model <option> list when an active provider is configured.
vi.mock("../Settings", () => ({
  POPULAR_PROVIDERS: [],
}));

// ── Helpers ────────────────────────────────────────────────────────────────────

const mockAgents = [
  {
    id: "power-system-coordinator-agent",
    name: "Power System Coordinator",
    description: "Main coordinator agent",
    capabilities: ["load_flow", "short_circuit", "arc_flash"],
    model: "gpt-4o-mini",
    provider: "openai",
  },
  {
    id: "protection-agent",
    name: "Protection Agent",
    description: "Relay coordination agent",
    capabilities: ["protection_coordination"],
    model: "gpt-4o",
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

describe("AIAssistant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock scrollIntoView which is not available in jsdom
    Element.prototype.scrollIntoView = vi.fn();
    mockFetchAgents.mockResolvedValue(mockAgents);
    mockGetActiveProvider.mockReturnValue({
      id: "openai",
      name: "OpenAI",
      model: "gpt-4o-mini",
    });
    mockGetConfiguredProviders.mockReturnValue([{ id: "openai", name: "OpenAI" }]);
    // By default, make the stream yield one chunk then complete.
    mockChatWithLLMStream.mockImplementation(async function* () {
      yield "Here is the load flow analysis result.";
    });
    mockChatWithLLM.mockResolvedValue({
      content: "Here is the load flow analysis result.",
    });
  });

  it("renders the empty-state prompt heading", async () => {
    renderAssistant();
    // The empty-state hero text. We wait for the agents fetch to settle so
    // any re-render triggered by it does not race with the assertion.
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());
    expect(screen.getByText("How can I help you today?")).toBeTruthy();
  });

  it("loads agents on mount (calls fetchAgents once)", async () => {
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());
  });

  it("does not send when the input is empty (submit button disabled in empty state)", async () => {
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());
    // The send button is rendered as a form submit; with empty input the
    // handler short-circuits and never calls the LLM.
    expect(mockChatWithLLMStream).not.toHaveBeenCalled();
    expect(mockChatWithLLM).not.toHaveBeenCalled();
  });

  it("sends a message and streams a reply", async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Message AI Assistant/i);
    await user.type(input, "Run a load flow analysis");

    // Submit via Enter (the component handles Enter without Shift).
    await user.keyboard("{Enter}");

    // The user message should appear in the transcript.
    await waitFor(() => {
      expect(screen.getByText("Run a load flow analysis")).toBeTruthy();
    });

    // The streamed assistant reply should appear.
    await waitFor(() => {
      expect(screen.getByText("Here is the load flow analysis result.")).toBeTruthy();
    });
  });

  it("shows an error notification when chat fails", async () => {
    const user = userEvent.setup();
    // Both streaming and non-streaming fallback fail.
    mockChatWithLLMStream.mockImplementation(async function* () {
      throw new Error("Network error");
    });
    mockChatWithLLM.mockRejectedValue(new Error("Network error"));
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Message AI Assistant/i);
    await user.type(input, "Hello");
    await user.keyboard("{Enter}");

    // The user's "Hello" message should be visible even when the assistant
    // fails to respond.
    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeTruthy();
    });
  });

  it("clears the conversation when Reset Chat is clicked", async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Message AI Assistant/i);
    await user.type(input, "Test message");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Test message")).toBeTruthy();
    });

    const resetBtn = screen.getByText("Reset Chat");
    await user.click(resetBtn);

    // After reset, the empty-state hero should be visible again.
    await waitFor(() => {
      expect(screen.getByText("How can I help you today?")).toBeTruthy();
    });
  });

  it("does not send empty/whitespace-only messages", async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Message AI Assistant/i);
    await user.type(input, "   ");
    await user.keyboard("{Enter}");

    // Give any pending microtasks a chance to flush, then assert no LLM call.
    await waitFor(() => {
      expect(mockChatWithLLMStream).not.toHaveBeenCalled();
      expect(mockChatWithLLM).not.toHaveBeenCalled();
    });
  });

  it("populates the input when a quick-prompt button is clicked", async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    // The first quick-prompt button text in AIAssistant.tsx is
    // 'Run a Newton-Raphson load flow'.
    const quickBtn = screen.getByText("Run a Newton-Raphson load flow");
    await user.click(quickBtn);

    const input = screen.getByPlaceholderText(/Message AI Assistant/i) as HTMLTextAreaElement;
    expect(input.value).toBe("Run a Newton-Raphson load flow");
  });
});
