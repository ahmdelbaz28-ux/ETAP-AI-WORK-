/**
 * @vitest-environment jsdom
 *
 * P7b — AgentsSkillsPromptsPanel tests
 * Covers: backend-authoritative agent listing, agent detail fetch (incl.
 * unknown-id rejection), prompt-handle metadata display, read-only prompt
 * surface (no editable inputs), skill metadata, load-failure surfacing,
 * and zero browser persistence. Only fake/test values are used.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentsSkillsPromptsPanel } from "../AgentsSkillsPromptsPanel";

vi.setConfig({ testTimeout: 15000 });

vi.mock("../../../lib/agents-skills-prompts", () => ({
  listAgents: vi.fn(),
  getAgent: vi.fn(),
  getAgentsInfo: vi.fn(),
  getAhmedEtapSkillInfo: vi.fn(),
}));

import {
  getAgent,
  getAgentsInfo,
  getAhmedEtapSkillInfo,
  listAgents,
} from "../../../lib/agents-skills-prompts";

const mockedListAgents = vi.mocked(listAgents);
const mockedGetAgent = vi.mocked(getAgent);
const mockedGetAgentsInfo = vi.mocked(getAgentsInfo);
const mockedGetSkill = vi.mocked(getAhmedEtapSkillInfo);

const FAKE_AGENT = {
  id: "load-flow-agent",
  name: "Load Flow Analysis Agent",
  description: "Performs AC load flow analysis using Newton-Raphson.",
  standard: "IEEE 3002.7",
  status: "active",
  capabilities: ["load_flow", "voltage_profile"],
  model: "gpt-4o",
  provider: "openai",
};

function backendResponses() {
  return {
    agents: {
      success: true,
      agents: [
        FAKE_AGENT,
        {
          id: "short-circuit-agent",
          name: "Short Circuit Analysis Agent",
          description: "Calculates fault currents per IEC 60909.",
          standard: "IEC 60909",
          status: "active",
          capabilities: ["short_circuit"],
          model: "gpt-4o",
          provider: "openai",
        },
      ],
    },
    info: {
      success: true,
      data: {
        orchestrator: { prompt_handle: "power_system_coordinator_agent", prompt_loaded: true },
        agents: {},
        available_prompts: ["load_flow_agent", "short_circuit_agent", "fallback_agent"],
        prompt_count: 3,
      },
    },
    skill: {
      success: true,
      data: {
        name: "AhmedETAP Orchestration Skill",
        description: "SharedContext, TokenBudget, MathGuard, PeerReview.",
        skill_text_chars: 1234,
      },
    },
  };
}

function renderPanel() {
  const notify = vi.fn();
  render(<AgentsSkillsPromptsPanel notify={notify} />);
  return { notify };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  const res = backendResponses();
  mockedListAgents.mockResolvedValue(res.agents);
  mockedGetAgentsInfo.mockResolvedValue(res.info);
  mockedGetSkill.mockResolvedValue(res.skill);
});

// ── Prompts (metadata only) ────────────────────────────────────────────────────

describe("AgentsSkillsPromptsPanel — prompts", () => {
  it("displays prompt handle names and count from the backend manifest loader", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("prompt-handle-load_flow_agent")).toBeTruthy(),
    );
    expect(screen.getByTestId("prompt-handle-short_circuit_agent")).toBeTruthy();
    expect(screen.getByTestId("prompt-handle-fallback_agent")).toBeTruthy();
    expect(screen.getByText("Prompt Handles (3)")).toBeTruthy();
    expect(
      screen.getByTestId("orchestrator-prompt-handle").textContent,
    ).toBe("power_system_coordinator_agent");
    expect(screen.getByTestId("orchestrator-prompt-loaded").textContent).toBe(
      "loaded",
    );
  });

  it("is strictly read-only: no editable inputs for prompts, agents, or skills", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("prompt-handles")).toBeTruthy(),
    );
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(document.querySelector("input")).toBeNull();
    expect(document.querySelector("textarea")).toBeNull();
  });

  it("warns but still renders agents when prompt metadata is unavailable", async () => {
    mockedGetAgentsInfo.mockRejectedValue(new Error("info endpoint down"));
    const { notify } = renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("agent-row-load-flow-agent")).toBeTruthy(),
    );
    const warn = notify.mock.calls.find(([type]) => type === "warning");
    expect(String(warn?.[1])).toContain("Prompt metadata unavailable");
    // Prompt inventory degrades gracefully to an empty (0-count) section
    expect(screen.getByText("Prompt Handles (0)")).toBeTruthy();
    // Skill metadata (independent source) still renders
    expect(screen.getByTestId("skill-info")).toBeTruthy();
  });

  it("warns but still renders agents when skill metadata is unavailable", async () => {
    mockedGetSkill.mockRejectedValue(new Error("skill endpoint down"));
    const { notify } = renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("agent-row-load-flow-agent")).toBeTruthy(),
    );
    expect(screen.getByTestId("skills-unavailable")).toBeTruthy();
    const warn = notify.mock.calls.find(([type]) => type === "warning");
    expect(String(warn?.[1])).toContain("Skill metadata unavailable");
    // Prompt metadata (independent source) still renders
    expect(screen.getByTestId("prompt-handle-load_flow_agent")).toBeTruthy();
  });
});

// ── Skills ─────────────────────────────────────────────────────────────────────

describe("AgentsSkillsPromptsPanel — skills", () => {
  it("renders runtime skill metadata reported by the backend", async () => {
    renderPanel();
    await waitFor(() => expect(screen.getByTestId("skill-info")).toBeTruthy());
    expect(screen.getByText("AhmedETAP Orchestration Skill")).toBeTruthy();
    expect(screen.getByText(/Knowledge base size: 1234 chars/)).toBeTruthy();
  });
});

// ── Errors / security invariants ───────────────────────────────────────────────

describe("AgentsSkillsPromptsPanel — load errors & security", () => {
  it("surfaces a registry load failure via notify without crashing", async () => {
    mockedListAgents.mockRejectedValue(new Error("backend unreachable"));
    const { notify } = renderPanel();
    await waitFor(() => expect(notify).toHaveBeenCalled());
    const errorCall = notify.mock.calls.find(([type]) => type === "error");
    expect(String(errorCall?.[1])).toContain("backend unreachable");
  });

  it("never persists anything to browser storage", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("agent-row-load-flow-agent")).toBeTruthy(),
    );
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("states the read-only backend-authoritative contract to the user", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("agents-skills-prompts-panel")).toBeTruthy(),
    );
    expect(screen.getByText(/Backend-authoritative view/)).toBeTruthy();
    expect(screen.getByText(/cannot be modified from\s+the browser/)).toBeTruthy();
  });
});


describe("AgentsSkillsPromptsPanel — agents", () => {
  it("renders the backend agent registry (backend truth, not a client registry)", async () => {
    renderPanel();
    await waitFor(() =>
      expect(screen.getByTestId("agent-row-load-flow-agent")).toBeTruthy(),
    );
    expect(screen.getByTestId("agent-row-short-circuit-agent")).toBeTruthy();
    expect(screen.getByText("Load Flow Analysis Agent")).toBeTruthy();
    expect(
      screen.getByTestId("agent-status-load-flow-agent").textContent,
    ).toBe("active");
    expect(screen.getByText(/IEEE 3002.7/)).toBeTruthy();
  });

  it("fetches and shows agent detail from GET /agents/{id} on selection", async () => {
    const user = userEvent.setup();
    mockedGetAgent.mockResolvedValue({ success: true, agent: FAKE_AGENT });
    renderPanel();

    await user.click(await screen.findByTestId("agent-row-load-flow-agent"));
    await waitFor(() => expect(screen.getByTestId("agent-detail")).toBeTruthy());
    expect(mockedGetAgent).toHaveBeenCalledWith("load-flow-agent");
    expect(screen.getByTestId("agent-capability-load_flow")).toBeTruthy();
  });

  it("surfaces backend rejection for an unknown agent id without crashing", async () => {
    const user = userEvent.setup();
    mockedGetAgent.mockRejectedValue(new Error("API 404: Agent not found"));
    renderPanel();

    await user.click(await screen.findByTestId("agent-row-load-flow-agent"));
    await waitFor(() =>
      expect(screen.getByTestId("agent-detail-error").textContent).toContain(
        "Agent not found",
      ),
    );
    expect(screen.queryByTestId("agent-detail")).toBeNull();
  });
});

