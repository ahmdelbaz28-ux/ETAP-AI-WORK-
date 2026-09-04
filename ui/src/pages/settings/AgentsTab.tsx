/**
 * AgentsTab (Phase P7b — Agents Settings)
 * ========================================
 * Table of 25 engineering agents registered in the platform (api/shared_handlers:AGENTS:25).
 *
 * SPECIFICATION & SECURITY:
 *   - Fetches agent catalog dynamically from canonical backend endpoint GET /api/v1/agents.
 *   - Local-only enabled/disabled state via React memory state (no PATCH /agents call).
 *   - Search filter by name, standard, and description.
 *   - Status badge and capability tags for each agent.
 *   - Zero dangerouslySetInnerHTML, zero localStorage persistence.
 */

import {
  Bot,
  Cpu,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, CardHeader, Input, Toggle } from "../../components/ui";
import { type BackendAgent, listAgents } from "../../lib/agents-skills-prompts";
import { cn } from "../../utils/helpers";

export interface AgentsTabProps {
  readonly notify?: (type: "success" | "error" | "info" | "warning", message: string) => void;
}

export function AgentsTab({ notify }: Readonly<AgentsTabProps>) {
  const [agents, setAgents] = useState<BackendAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  // Strictly local in-memory toggle state (NO PATCH /agents call)
  const [disabledAgents, setDisabledAgents] = useState<Record<string, boolean>>({});

  const fetchAgentList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAgents();
      if (res?.agents) {
        setAgents(res.agents);
      } else {
        setAgents([]);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load agents";
      setError(msg);
      if (notify) {
        notify("error", `Failed to load agents: ${msg}`);
      }
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    void fetchAgentList();
  }, [fetchAgentList]);

  const handleToggleAgent = useCallback(
    (agentId: string, currentEnabled: boolean) => {
      setDisabledAgents((prev) => ({
        ...prev,
        [agentId]: currentEnabled,
      }));
      if (notify) {
        notify(
          "info",
          `Agent ${agentId} ${currentEnabled ? "disabled" : "enabled"} in local session`,
        );
      }
    },
    [notify],
  );

  const filteredAgents = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter(
      (agent) =>
        agent.name.toLowerCase().includes(q) ||
        agent.id.toLowerCase().includes(q) ||
        (agent.standard && agent.standard.toLowerCase().includes(q)) ||
        (agent.description && agent.description.toLowerCase().includes(q)),
    );
  }, [agents, searchQuery]);

  const enabledCount = useMemo(() => {
    return agents.filter((a) => !disabledAgents[a.id]).length;
  }, [agents, disabledAgents]);

  return (
    <div className="space-y-4" data-testid="agents-tab">
      {/* ── Header Card ────────────────────────────────────────────── */}
      <Card padding="md">
        <CardHeader
          title={`Engineering Agents (${agents.length || 25})`}
          subtitle="Dual-runtime architecture (Mastra TypeScript + Python Engineering Engines)"
          icon={<Bot className="w-5 h-5 text-brand-400" />}
          action={
            <div className="flex items-center gap-2">
              <Badge variant="brand" size="md">
                {enabledCount} / {agents.length} Enabled
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                icon={RefreshCw}
                onClick={() => void fetchAgentList()}
                disabled={loading}
              >
                Refresh
              </Button>
            </div>
          }
        />
        <div className="flex items-start gap-2 mt-2 text-xs text-[var(--text-muted)]">
          <ShieldCheck className="w-4 h-4 shrink-0 text-green-400 mt-0.5" />
          <span>
            Active agent registry loaded from GET /api/v1/agents. Toggles are managed in local
            session memory without mutating backend registry contracts.
          </span>
        </div>
      </Card>

      {/* ── Search & Filter Bar ────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="w-full sm:flex-1">
          <Input
            leftIcon={Search}
            placeholder="Search 25 agents by name, ID, or standard (e.g. IEC 60909, IEEE 1584)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        {searchQuery && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSearchQuery("")}
            className="text-xs shrink-0"
          >
            Clear Filter
          </Button>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center justify-between">
          <span>Failed to load agents from backend: {error}</span>
          <Button variant="ghost" size="sm" onClick={() => void fetchAgentList()}>
            Retry
          </Button>
        </div>
      )}

      {/* ── Agents Table / List ────────────────────────────────────── */}
      <Card padding="none">
        {loading && agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-[var(--text-muted)]">
            <Loader2 className="w-8 h-8 animate-spin text-brand-500 mb-2" />
            <p className="text-sm">Loading agents registry from backend...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-[var(--border-primary)] bg-[var(--bg-elevated)]/50 text-[var(--text-secondary)] text-xs">
                  <th className="py-3 px-4 font-semibold">Agent</th>
                  <th className="py-3 px-4 font-semibold">Standard</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold text-right">Enabled</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-primary)]">
                {filteredAgents.map((agent) => {
                  const isDisabled = Boolean(disabledAgents[agent.id]);
                  const isEnabled = !isDisabled;

                  return (
                    <tr
                      key={agent.id}
                      data-testid={`agent-row-${agent.id}`}
                      className={cn(
                        "transition-colors hover:bg-[var(--bg-elevated)]/40",
                        isDisabled && "opacity-60 bg-[var(--bg-elevated)]/10",
                      )}
                    >
                      <td className="py-3.5 px-4 align-top">
                        <div className="flex items-start gap-3">
                          <div
                            className={cn(
                              "p-2 rounded-lg shrink-0 mt-0.5",
                              isEnabled
                                ? "bg-brand-500/10 text-brand-400 border border-brand-500/20"
                                : "bg-[var(--bg-elevated)] text-[var(--text-muted)] border border-[var(--border-primary)]",
                            )}
                          >
                            <Cpu className="w-4 h-4" />
                          </div>
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-[var(--text-primary)]">
                                {agent.name}
                              </span>
                              <span className="text-[11px] font-mono text-[var(--text-muted)]">
                                ({agent.id})
                              </span>
                            </div>
                            <p className="text-xs text-[var(--text-muted)] max-w-xl leading-relaxed">
                              {agent.description}
                            </p>
                            {agent.capabilities && agent.capabilities.length > 0 && (
                              <div className="flex flex-wrap gap-1 pt-1">
                                {agent.capabilities.slice(0, 4).map((cap) => (
                                  <span
                                    key={cap}
                                    className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-primary)]"
                                  >
                                    {cap}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 align-top whitespace-nowrap">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-primary)]">
                          {agent.standard || "Internal"}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 align-top whitespace-nowrap">
                        {isDisabled ? (
                          <Badge variant="neutral" size="sm" dot>
                            Disabled
                          </Badge>
                        ) : agent.status === "active" ? (
                          <Badge variant="success" size="sm" dot>
                            Active
                          </Badge>
                        ) : (
                          <Badge variant="warning" size="sm" dot>
                            {agent.status || "Beta"}
                          </Badge>
                        )}
                      </td>
                      <td className="py-3.5 px-4 align-top text-right whitespace-nowrap">
                        <div className="inline-block">
                          <Toggle
                            size="sm"
                            checked={isEnabled}
                            onChange={() => handleToggleAgent(agent.id, isEnabled)}
                            label={isEnabled ? "Active" : "Off"}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filteredAgents.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-12 text-center text-[var(--text-muted)]">
                      <Filter className="w-6 h-6 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">
                        {searchQuery
                          ? `No agents matching "${searchQuery}"`
                          : "No agents available from backend"}
                      </p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

export default AgentsTab;
