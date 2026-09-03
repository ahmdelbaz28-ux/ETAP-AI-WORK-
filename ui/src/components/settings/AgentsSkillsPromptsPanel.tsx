/**
 * AgentsSkillsPromptsPanel (P7b — Agents / Skills / Prompts)
 * ==========================================================
 * Settings tab panel providing backend-authoritative VISIBILITY of the
 * platform's agents, runtime skills, and prompt inventory through the
 * EXISTING agents API (api/agents.py). This panel is intentionally
 * READ-ONLY:
 *
 * SECURITY DESIGN (P7b):
 *   - Backend authority: every value rendered here comes from a trusted
 *     backend response. No client-side registry, no client-side
 *     authorization, no optimistic local state.
 *   - No mutation surface: the backend exposes no endpoint for enabling /
 *     disabling agents, activating skills, or editing prompts, so this
 *     panel must not fake one. Configuration remains server-managed.
 *   - Prompt safety: only prompt HANDLE names and counts are displayed.
 *     Prompt content (privileged system prompts) is never requested and
 *     never rendered — the browser cannot redefine or inject prompts.
 *   - No persistence: nothing is written to localStorage / sessionStorage.
 *   - No secrets: the endpoints used return metadata only.
 */

import { Bot, FileText, Loader2, ShieldCheck, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  type AhmedEtapSkillInfoResponse,
  type BackendAgent,
  getAgent,
  getAgentsInfo,
  getAhmedEtapSkillInfo,
  listAgents,
} from "../../lib/agents-skills-prompts";
import { Card, CardHeader } from "../ui";

type NotifyType = "success" | "error" | "info" | "warning";

interface AgentsSkillsPromptsPanelProps {
  readonly notify: (type: NotifyType, message: string) => void;
}

interface LoadedState {
  agents: BackendAgent[];
  promptHandles: string[];
  promptCount: number;
  orchestratorPromptHandle: string;
  orchestratorPromptLoaded: boolean;
  skillInfo: AhmedEtapSkillInfoResponse["data"] | null;
}

function statusBadgeClass(status: string): string {
  if (status === "active")
    return "bg-green-500/10 text-green-400 border border-green-500/20";
  if (status === "standby")
    return "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20";
  return "bg-red-500/10 text-red-400 border border-red-500/20";
}

export function AgentsSkillsPromptsPanel({
  notify,
}: AgentsSkillsPromptsPanelProps) {
  const [loaded, setLoaded] = useState<LoadedState | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailAgent, setDetailAgent] = useState<BackendAgent | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Independent reads — the panel still renders if a secondary source
      // fails, but every failure is surfaced (never silently hidden).
      const agentsRes = await listAgents();
      let info: Awaited<ReturnType<typeof getAgentsInfo>> | null = null;
      let skill: AhmedEtapSkillInfoResponse | null = null;
      try {
        info = await getAgentsInfo();
      } catch (err) {
        notify(
          "warning",
          `Prompt metadata unavailable: ${err instanceof Error ? err.message : "unknown error"}`,
        );
      }
      try {
        skill = await getAhmedEtapSkillInfo();
      } catch (err) {
        notify(
          "warning",
          `Skill metadata unavailable: ${err instanceof Error ? err.message : "unknown error"}`,
        );
      }
      setLoaded({
        agents: agentsRes.agents ?? [],
        promptHandles: info?.data.available_prompts ?? [],
        promptCount: info?.data.prompt_count ?? 0,
        orchestratorPromptHandle: info?.data.orchestrator.prompt_handle ?? "",
        orchestratorPromptLoaded: info?.data.orchestrator.prompt_loaded ?? false,
        skillInfo: skill?.data ?? null,
      });
    } catch (err) {
      notify(
        "error",
        err instanceof Error ? err.message : "Failed to load agents",
      );
      setLoaded(null);
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    void load();
  }, [load]);

  const showAgentDetail = useCallback(async (agentId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const res = await getAgent(agentId);
      setDetailAgent(res.agent);
    } catch (err) {
      setDetailAgent(null);
      setDetailError(
        err instanceof Error ? err.message : "Failed to load agent detail",
      );
    } finally {
      setDetailLoading(false);
    }
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12" data-testid="agents-panel-loading">
        <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="agents-skills-prompts-panel">
      <Card padding="md">
        <CardHeader
          title="Agents, Skills & Prompts"
          subtitle="Backend-authoritative view — configuration is managed server-side"
          icon={<Bot className="w-4 h-4" />}
        />
        <div className="flex items-start gap-2 mt-2 text-xs text-[var(--text-muted)]">
          <ShieldCheck className="w-4 h-4 shrink-0 text-green-400" />
          <span>
            Read-only view served by the engineering backend. Agent
            enablement, skill activation, and prompt definitions are
            controlled by the backend manifest and cannot be modified from
            the browser.
          </span>
        </div>
      </Card>

      {/* ── Agents ─────────────────────────────────────────────────────── */}
      <Card padding="md">
        <CardHeader
          title={`Registered Agents (${loaded?.agents.length ?? 0})`}
          subtitle="Canonical registry from the backend"
          icon={<Bot className="w-4 h-4" />}
        />
        <div className="mt-3 space-y-2">
          {(loaded?.agents ?? []).map((agent) => (
            <button
              key={agent.id}
              type="button"
              data-testid={`agent-row-${agent.id}`}
              onClick={() => void showAgentDetail(agent.id)}
              className="w-full text-left p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-elevated)] hover:border-brand-500/40 transition-all"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm">{agent.name}</span>
                <span
                  data-testid={`agent-status-${agent.id}`}
                  className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusBadgeClass(agent.status)}`}
                >
                  {agent.status}
                </span>
              </div>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                {agent.description}
              </p>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                Standard: {agent.standard || "—"} · Model: {agent.model || "—"} ·
                Provider: {agent.provider || "—"}
              </p>
            </button>
          ))}
          {loaded?.agents.length === 0 && (
            <p className="text-sm text-[var(--text-muted)]" data-testid="agents-empty">
              No agents reported by the backend.
            </p>
          )}
        </div>

        {detailLoading && (
          <div className="flex items-center gap-2 mt-3 text-sm text-[var(--text-muted)]" data-testid="agent-detail-loading">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading agent…
          </div>
        )}
        {detailError && (
          <p className="mt-3 text-sm text-red-400" data-testid="agent-detail-error">
            {detailError}
          </p>
        )}
        {detailAgent && (
          <div
            className="mt-3 p-3 rounded-lg border border-brand-500/30 bg-[var(--bg-primary)]"
            data-testid="agent-detail"
          >
            <p className="font-semibold text-sm">{detailAgent.name}</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              {detailAgent.description}
            </p>
            <div className="flex flex-wrap gap-1 mt-2">
              {detailAgent.capabilities.map((cap) => (
                <span
                  key={cap}
                  data-testid={`agent-capability-${cap}`}
                  className="px-2 py-0.5 rounded-full text-xs bg-brand-500/10 text-brand-400 border border-brand-500/20"
                >
                  {cap}
                </span>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* ── Skills ─────────────────────────────────────────────────────── */}
      <Card padding="md">
        <CardHeader
          title="Runtime Skills"
          subtitle="Skill metadata reported by the backend"
          icon={<Wrench className="w-4 h-4" />}
        />
        {loaded?.skillInfo ? (
          <div className="mt-3 p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-elevated)]" data-testid="skill-info">
            <p className="font-semibold text-sm">
              {typeof loaded.skillInfo.name === "string"
                ? loaded.skillInfo.name
                : "AhmedETAP Orchestration Skill"}
            </p>
            {typeof loaded.skillInfo.description === "string" && (
              <p className="text-xs text-[var(--text-muted)] mt-1">
                {loaded.skillInfo.description}
              </p>
            )}
            {typeof loaded.skillInfo.skill_text_chars === "number" && (
              <p className="text-xs text-[var(--text-muted)] mt-1">
                Knowledge base size: {loaded.skillInfo.skill_text_chars} chars
              </p>
            )}
          </div>
        ) : (
          <p className="mt-3 text-sm text-[var(--text-muted)]" data-testid="skills-unavailable">
            Skill metadata unavailable from the backend.
          </p>
        )}
      </Card>

      {/* ── Prompts (metadata only — never content) ────────────────────── */}
      <Card padding="md">
        <CardHeader
          title={`Prompt Handles (${loaded?.promptCount ?? 0})`}
          subtitle="Manifest-first inventory — content stays server-side"
          icon={<FileText className="w-4 h-4" />}
        />
        <div className="mt-3" data-testid="prompt-handles">
          <p className="text-xs text-[var(--text-muted)]">
            Orchestrator prompt:{" "}
            <span className="font-mono" data-testid="orchestrator-prompt-handle">
              {loaded?.orchestratorPromptHandle || "—"}
            </span>{" "}
            ·{" "}
            <span data-testid="orchestrator-prompt-loaded">
              {loaded?.orchestratorPromptLoaded ? "loaded" : "not loaded"}
            </span>
          </p>
          <div className="flex flex-wrap gap-1 mt-2">
            {(loaded?.promptHandles ?? []).map((handle) => (
              <span
                key={handle}
                data-testid={`prompt-handle-${handle}`}
                className="px-2 py-0.5 rounded-full text-xs font-mono bg-[var(--bg-primary)] text-[var(--text-muted)] border border-[var(--border-primary)]"
              >
                {handle}
              </span>
            ))}
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-3">
            Prompt resolution is manifest-first (prompts.json → YAML →
            fallback) and validated server-side. Prompt content and
            configuration are not editable here by design.
          </p>
        </div>
      </Card>


    </div>
  );
}

export default AgentsSkillsPromptsPanel;
