/**
 * McpServersTab (Phase P7c — Split MCP Settings)
 * ==============================================
 * Dedicated settings panel for managing Model Context Protocol (MCP) Servers.
 * Handles server discovery from /api/v1/agents/mcp-servers and backend health checks.
 */

import { Database } from "lucide-react";
import { useEffect, useState } from "react";
import { Card } from "../../components/ui";
import { checkMcpServerHealth, fetchMcpServers } from "../../lib/api";
import { cn } from "../../utils/helpers";

export interface MCPConfig {
  id: string;
  name: string;
  status: "connected" | "standby" | "disabled";
  type: string;
  urlOrPath: string;
  description: string;
  tools: string[];
}

export const MCP_SERVERS_FALLBACK: MCPConfig[] = [
  {
    id: "weather",
    name: "Weather MCP Server",
    status: "connected",
    type: "Local/Service",
    urlOrPath: "src/mastra/agents/weather-agent.ts",
    description:
      "Retrieves real-time weather and temperature details for renewable energy capacity planning.",
    tools: ["weatherTool"],
  },
  {
    id: "gis",
    name: "QGIS Map Service MCP Server",
    status: "connected",
    type: "Local/GIS Provider",
    urlOrPath: "gis_integration/providers/",
    description:
      "Bridges and extracts coordinates, lines, and substations from active QGIS layers or shapefiles.",
    tools: ["load_gis_features", "sync_gis_telemetry"],
  },
  {
    id: "scada",
    name: "SCADA zenon Telemetry MCP Server",
    status: "connected",
    type: "WebSocket/SCADA API",
    urlOrPath: "api/scada.py",
    description:
      "Subscribes and queries active Copa-Data zenon alerts and live telemetry registers (I, V, P, Q).",
    tools: ["fetch_live_telemetry", "trigger_zenon_alarm"],
  },
  {
    id: "etap_com",
    name: "ETAP COM Automation MCP Server",
    status: "standby",
    type: "COM/Windows Service",
    urlOrPath: "etap_integration/etap_com.py",
    description:
      "Executes direct COM automation scripts to run Newton-Raphson studies in Windows-only desktop clients.",
    tools: ["run_etap_study", "export_etap_one_line"],
  },
  {
    id: "guard",
    name: "AI Code Guard MCP Server",
    status: "connected",
    type: "Local/Validation",
    urlOrPath: "guards/code_guard_agent.py",
    description:
      "Enforces safety boundaries, double-confirmation checks, and SIEM logging rules on generated code.",
    tools: ["validate_code"],
  },
];

export type McpHealthStatus = { status: string; message: string; loading: boolean };

export function McpServersTab() {
  const [servers, setServers] = useState<MCPConfig[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);
  const [health, setHealth] = useState<Record<string, McpHealthStatus>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetchMcpServers();
        if (cancelled) return;
        const list = resp?.data?.servers ?? [];
        if (list.length === 0) {
          // No .mcp.json configured — show fallback (documented) so the UI is not empty.
          setServers(MCP_SERVERS_FALLBACK);
          setUsingFallback(true);
        } else {
          // Map server-side MCP info into the MCPConfig shape the renderer expects.
          setServers(
            list.map((s) => ({
              id: s.id,
              name: s.name || s.id,
              status: s.status === "configured" ? "connected" : "standby",
              type: s.type || "stdio",
              urlOrPath: s.command || "(no command)",
              description: `Args: ${(s.args ?? []).join(" ") || "(none)"} · Env keys: ${s.env_keys?.join(", ") || "(none)"}`,
              tools: s.env_keys ?? [],
            })),
          );
          setUsingFallback(false);
        }
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load MCP servers");
        setServers(MCP_SERVERS_FALLBACK);
        setUsingFallback(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "connected":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-500/10 text-green-400 border border-green-500/20">
            ● Active
          </span>
        );
      case "standby":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
            ● Standby
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/10 text-red-400 border border-red-500/20">
            ● Offline
          </span>
        );
    }
  };

  const checkHealth = async (serverId: string) => {
    setHealth((prev) => ({
      ...prev,
      [serverId]: { status: "checking", message: "Probing endpoint…", loading: true },
    }));
    try {
      const resp = await checkMcpServerHealth(serverId);
      const data = resp?.data;
      setHealth((prev) => ({
        ...prev,
        [serverId]: {
          status: data?.status ?? "unreachable",
          message: data?.message ?? resp?.errors?.[0] ?? "Health probe returned no data.",
          loading: false,
        },
      }));
    } catch (err) {
      setHealth((prev) => ({
        ...prev,
        [serverId]: {
          status: "unreachable",
          message: err instanceof Error ? err.message : "Health probe failed.",
          loading: false,
        },
      }));
    }
  };

  const getHealthBadgeClass = (status: string) => {
    switch (status) {
      case "ok":
        return "bg-green-500/10 text-green-400 border-green-500/20";
      case "degraded":
      case "checking":
        return "bg-yellow-500/10 text-yellow-400 border-yellow-500/20";
      default:
        return "bg-red-500/10 text-red-400 border-red-500/20";
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 col-span-2">
        <Card padding="md">
          <div className="flex items-center gap-3 text-[var(--text-secondary)]">
            <div className="w-4 h-4 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Loading MCP servers from backend…</span>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 col-span-2">
      <Card padding="md">
        <div className="flex items-start gap-3 mb-5 pb-4 border-b border-[var(--border-primary)]">
          <div className="w-10 h-10 rounded-xl bg-brand-500/15 flex items-center justify-center shrink-0">
            <Database className="w-5 h-5 text-brand-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-semibold text-[var(--text-primary)]">
              Model Context Protocol (MCP) Servers
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              The platform utilizes MCP to expose local files, databases, SCADA bridges, and
              engineering scripts to AI specialist agents as secure tools.
            </p>
            {error && (
              <div className="mt-3 px-3 py-2 rounded-md bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
                Backend unreachable: {error}. Showing documented fallback list. Configure .mcp.json
                or set MCP_CONFIG_PATH to enable server-side discovery.
              </div>
            )}
            {!error && usingFallback && (
              <div className="mt-3 px-3 py-2 rounded-md bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-xs">
                No .mcp.json configured on backend — showing documented fallback list. Create
                .mcp.json at the repo root (see .mcp.json.example) to switch to live discovery.
              </div>
            )}
            {!error && !usingFallback && (
              <div className="mt-3 px-3 py-2 rounded-md bg-green-500/10 border border-green-500/20 text-green-300 text-xs">
                Loaded from <code className="font-mono">/api/v1/agents/mcp-servers</code>. Env
                values are redacted server-side for security.
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {(servers ?? []).map((srv) => (
            <div
              key={srv.id}
              className="p-4 bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl hover:border-brand-500/30 transition-all"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-[var(--text-primary)]">
                    {srv.name}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-primary)] border border-[var(--border-primary)] text-[var(--text-muted)] font-mono">
                    {srv.type}
                  </span>
                </div>
                {getStatusBadge(srv.status)}
              </div>
              <p className="text-xs text-[var(--text-secondary)] mb-3 leading-relaxed">
                {srv.description}
              </p>

              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] text-[var(--text-muted)] font-semibold uppercase tracking-wider">
                  Exposed Tools:
                </span>
                {srv.tools.map((tool) => (
                  <span
                    key={tool}
                    className="text-[10px] font-mono px-2 py-0.5 rounded bg-brand-500/5 text-brand-400 border border-brand-500/10"
                  >
                    {tool}
                  </span>
                ))}
              </div>

              {health[srv.id] && !health[srv.id].loading && (
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed mt-2">
                  Health: {health[srv.id].message}
                </p>
              )}

              <div className="mt-3 pt-3 border-t border-[var(--border-primary)] flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void checkHealth(srv.id)}
                  disabled={health[srv.id]?.loading}
                  className="text-xs px-3 py-1.5 rounded-md border border-brand-500/30 bg-brand-500/10 text-brand-300 hover:bg-brand-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {health[srv.id]?.loading ? "Probing…" : "Health check"}
                </button>
                {health[srv.id] && !health[srv.id].loading && (
                  <span
                    className={cn(
                      "text-[10px] px-2 py-0.5 rounded-full border font-semibold uppercase",
                      getHealthBadgeClass(health[srv.id].status),
                    )}
                  >
                    {health[srv.id].status}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// Backward-compatibility export
export { McpServersTab as MCPSettingsPanel };
export default McpServersTab;
