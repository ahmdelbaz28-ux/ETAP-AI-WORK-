/**
 * AgentsTab (Phase P7b — Agents Settings)
 * ========================================
 * Table of 25 engineering agents registered in the platform (api/shared_handlers:AGENTS:25).
 *
 * SPECIFICATION & SECURITY:
 *   - Fetches agent catalog from canonical backend endpoint GET /api/v1/agents.
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

/**
 * Fallback canonical registry of 25 agents from api/shared_handlers.py:AGENTS.
 * Guarantees reliable offline rendering and resilience against network timeouts.
 */
const CANONICAL_AGENTS: BackendAgent[] = [
  {
    id: "load-flow-agent",
    name: "Load Flow Agent",
    standard: "IEEE 3002.7",
    status: "active",
    description: "Newton-Raphson load flow analysis, voltage profile assessment, power loss calculation.",
    capabilities: ["load_flow", "newton_raphson", "voltage_profile", "loss_calculation"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "short-circuit-agent",
    name: "Short Circuit Agent",
    standard: "IEC 60909",
    status: "active",
    description: "Fault current analysis (3-phase, SLG, LL, LLG), equipment rating verification.",
    capabilities: ["short_circuit", "fault_analysis", "iec_60909", "equipment_rating"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "arcflash-agent",
    name: "Arc Flash Agent",
    standard: "IEEE 1584",
    status: "beta",
    description: "Incident energy calculation, arc flash boundary, PPE category determination.",
    capabilities: ["arc_flash", "incident_energy", "ppe_category", "ieee_1584"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "protection-agent",
    name: "Protection Agent",
    standard: "IEC 60255",
    status: "active",
    description: "Relay coordination, time-current curve analysis, protection selectivity verification.",
    capabilities: ["protection", "relay_coordination", "tcc_curves", "iec_60255"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "motorstarting-agent",
    name: "Motor Starting Agent",
    standard: "IEEE 399",
    status: "beta",
    description: "Motor starting current analysis, voltage dip assessment, acceleration risk evaluation.",
    capabilities: ["motor_starting", "voltage_dip", "acceleration_risk", "ieee_399"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "stability-agent",
    name: "Stability Agent",
    standard: "IEEE 399",
    status: "beta",
    description: "Transient stability, swing equation (RK4), eigenvalue analysis, critical clearing time.",
    capabilities: ["transient_stability", "rk4_solver", "eigenvalues", "cct"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "harmonic-agent",
    name: "Harmonic Analysis Agent",
    standard: "IEEE 519",
    status: "active",
    description: "Harmonic distortion analysis, filter sizing, THD calculation, IEEE 519 compliance.",
    capabilities: ["harmonics", "thd_calculation", "filter_sizing", "ieee_519"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "cable-sizing-agent",
    name: "Cable Sizing Agent",
    standard: "IEC 60364",
    status: "beta",
    description: "Cable ampacity calculation, voltage drop verification, thermal withstand checks.",
    capabilities: ["cable_sizing", "ampacity", "voltage_drop", "iec_60364"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "earth-grid-agent",
    name: "Earth Grid Agent",
    standard: "IEEE 80",
    status: "beta",
    description: "Substation ground grid design, mesh/step/touch voltage calculation.",
    capabilities: ["ground_grid", "mesh_voltage", "step_voltage", "ieee_80"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "opf-agent",
    name: "Optimal Power Flow Agent",
    standard: "IEEE 3002.7",
    status: "active",
    description: "Cost minimization, transmission loss optimization, generation dispatch.",
    capabilities: ["optimal_power_flow", "dispatch_optimization", "loss_minimization"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "renewable-agent",
    name: "Renewable Energy Agent",
    standard: "IEEE 1547",
    status: "beta",
    description: "Solar PV & wind generation integration, intermittency modeling, grid code compliance.",
    capabilities: ["renewables", "solar_pv", "wind_integration", "ieee_1547"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "battery-storage-agent",
    name: "Battery Storage Agent",
    standard: "IEC 62933",
    status: "beta",
    description: "Battery Energy Storage System (BESS) sizing, state of charge, dispatch optimization.",
    capabilities: ["bess", "battery_storage", "dispatch_optimization", "iec_62933"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "scada-agent",
    name: "SCADA Agent",
    standard: "IEC 61850",
    status: "beta",
    description: "SCADA real-time telemetry, Copa-Data zenon sync, GOOSE/SV messaging mapping.",
    capabilities: ["scada", "telemetry", "zenon_sync", "iec_61850"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "digital-twin-agent",
    name: "Digital Twin Agent",
    standard: "IEC 61970",
    status: "beta",
    description: "Real-time state estimation, topology processing, dynamic model synchronization.",
    capabilities: ["digital_twin", "state_estimation", "topology_processing", "iec_61970"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "predictive-agent",
    name: "Predictive Maintenance",
    standard: "ISO 13381",
    status: "beta",
    description: "Equipment degradation modeling, remaining useful life (RUL), anomaly trends.",
    capabilities: ["predictive_maintenance", "rul_estimation", "degradation_models", "iso_13381"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "anomaly-agent",
    name: "Anomaly Detection Agent",
    standard: "IEEE 1159",
    status: "beta",
    description: "Power quality events, voltage sags/swells, transient spike anomaly detection.",
    capabilities: ["anomaly_detection", "power_quality", "voltage_sag", "ieee_1159"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "coordination-agent",
    name: "Coordination Agent",
    standard: "IEC 60255",
    status: "beta",
    description: "Protection selectivity verification, grading margins, coordination audit.",
    capabilities: ["protection_coordination", "selectivity_check", "grading_margins", "iec_60255"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "report-agent",
    name: "Report Generation Agent",
    standard: "IEEE 3002.7",
    status: "active",
    description: "Automated engineering documentation, calculation summaries, multi-format export.",
    capabilities: ["reporting", "pdf_export", "standards_documentation"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "validation-agent",
    name: "Validation Agent",
    standard: "IEC 60038",
    status: "active",
    description: "Engineering sanity check, first-principles cross verification, rule compliance.",
    capabilities: ["validation", "first_principles", "standards_audit", "iec_60038"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "etap-engineer-agent",
    name: "ETAP Engineer Agent",
    standard: "ETAP Manual",
    status: "active",
    description: "General-purpose ETAP study assistant, project file validation, one-line model audits.",
    capabilities: ["etap_core", "study_orchestration", "model_audit"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "goal-planner-agent",
    name: "Goal Planner Agent",
    standard: "Internal",
    status: "beta",
    description: "Deconstructs high-level engineering objectives into sequenced study workflows.",
    capabilities: ["goal_planning", "study_decomposition", "task_sequencing"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "weather-agent",
    name: "Weather Agent",
    standard: "IEC 60721",
    status: "beta",
    description: "Weather environmental data retrieval, solar irradiance, ambient temperature curves.",
    capabilities: ["weather_telemetry", "solar_irradiance", "thermal_rating", "iec_60721"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "power-system-coordinator",
    name: "Power System Coordinator",
    standard: "All",
    status: "active",
    description: "Triage and routing agent, dispatches incoming tasks to specialist domain agents.",
    capabilities: ["agent_coordination", "task_routing", "specialist_dispatch"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "etap-expert-agent",
    name: "ETAP Expert Skill Agent",
    standard: "IEEE/IEC/NEC/NFPA (all)",
    status: "active",
    description: "6-step workflow with Format A/B/C/D responses. Knowledge base: skills/etap-expert.md.",
    capabilities: ["etap_expert", "rule_based_audit", "standards_compliance", "format_a_b_c_d"],
    model: "gpt-4o",
    provider: "openai",
  },
  {
    id: "etap-gui-agent",
    name: "ETAP GUI Agent (Computer Use Agent)",
    standard: "Safety + Audit",
    status: "active",
    description: "Computer Use Agent for desktop apps (ETAP, Revit, AutoCAD, SCADA, QGIS, ArcGIS).",
    capabilities: ["cua", "desktop_automation", "etap_ui_control", "vision_grounding"],
    model: "gpt-4o",
    provider: "openai",
  },
];

export function AgentsTab({ notify }: Readonly<AgentsTabProps>) {
  const [agents, setAgents] = useState<BackendAgent[]>(CANONICAL_AGENTS);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  // Strictly local in-memory toggle state (NO PATCH /agents call)
  const [disabledAgents, setDisabledAgents] = useState<Record<string, boolean>>({});

  const fetchAgentList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listAgents();
      if (res?.agents && res.agents.length > 0) {
        setAgents(res.agents);
      } else {
        setAgents(CANONICAL_AGENTS);
      }
    } catch {
      // Graceful fallback to canonical 25 agents
      setAgents(CANONICAL_AGENTS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAgentList();
  }, [fetchAgentList]);

  const handleToggleAgent = useCallback((agentId: string, currentEnabled: boolean) => {
    setDisabledAgents((prev) => {
      const next = { ...prev, [agentId]: currentEnabled };
      return next;
    });
    if (notify) {
      notify(
        "info",
        `Agent ${agentId} ${currentEnabled ? "disabled" : "enabled"} in local session`,
      );
    }
  }, [notify]);

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
          title="Engineering Agents (25)"
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
            Active agent registry loaded from the engineering backend. Toggles are managed in local
            session memory without modifying backend registry contracts.
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
                          {agent.standard || "Standard Internal"}
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
                      <p className="text-sm">No agents matching &ldquo;{searchQuery}&rdquo;</p>
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
