/**
 * Agents Control Panel Page — Administration UI for all AI agents.
 *
 * Wires to all 15 JSON endpoints exposed by api/agents.py
 * (prefix /api/v1/agents):
 *
 *   Agent listing/info:
 *     GET  /api/v1/agents                              — list all 25 agents
 *     GET  /api/v1/agents/{agent_id}                   — single agent detail
 *     GET  /api/v1/agents/info                         — orchestrator + prompts info
 *
 *   ETAP Expert & GUI chat:
 *     POST /api/v1/agents/etap-expert/chat             — {message, context?}
 *     POST /api/v1/agents/etap-gui/chat                — {message, context?}
 *
 *   CUA & Safety:
 *     POST /api/v1/agents/etap-gui/execute             — real CUA loop
 *     GET  /api/v1/agents/etap-gui/health              — CUA deps + life safety
 *     POST /api/v1/agents/etap-gui/kill-switch/activate?reason=  — EMERGENCY STOP
 *     POST /api/v1/agents/etap-gui/kill-switch/deactivate        — resume
 *     GET  /api/v1/agents/etap-gui/safety/health                  — life-safety status
 *     GET  /api/v1/agents/etap-gui/safety/audit/verify            — audit chain verify
 *
 *   SIEM:
 *     GET  /api/v1/agents/etap-gui/siem/health                    — syslog forwarder
 *     GET  /api/v1/agents/etap-gui/siem/events?limit=50           — recent events
 *
 *   AhmedETAP orchestration:
 *     POST /api/v1/agents/ahmed-etap/orchestrate        — run study pipeline
 *     GET  /api/v1/agents/ahmed-etap/info               — skill metadata
 *
 * Ref: TASK-5
 */

import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Cpu,
  Eye,
  Loader2,
  Network,
  Power,
  PowerOff,
  Radio,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  XCircle,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  CardSection,
  EmptyState,
  Modal,
  Tabs,
} from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

// ---------------------------------------------------------------------------
// Types — mirror api/agents.py response shapes
// ---------------------------------------------------------------------------

interface AgentMeta {
  id: string;
  name: string;
  description: string;
  standard: string;
  status: string;
  capabilities: string[];
  model: string;
  provider: string;
}

interface AgentsListResponse {
  success: boolean;
  agents: AgentMeta[];
  trace_id?: string;
}

interface AgentDetailResponse {
  success: boolean;
  agent: AgentMeta;
  trace_id?: string;
  error?: string;
}

interface AgentsInfoResponse {
  success: boolean;
  data: {
    agents?: Record<string, unknown>;
    available_prompts?: string[];
    prompt_count?: number;
    [k: string]: unknown;
  };
  trace_id?: string;
}

interface ChatResponse {
  success: boolean;
  data?: Record<string, unknown>;
  errors?: string[];
  trace_id?: string;
}

interface LifeSafetyStatus {
  kill_switch_active: boolean;
  audit_chain_valid: boolean;
  audit_chain_broken_entries: string[];
  lethal_patterns_count: number;
  dual_confirmation_patterns_count: number;
  cooldown_seconds: number;
  degraded_vision_sources: string[];
}

interface CuaHealthData {
  cua_loop_available: boolean;
  missing_dependencies: string[];
  gemini_vision: Record<string, unknown>;
  agent_info: Record<string, unknown>;
  life_safety: LifeSafetyStatus;
}

interface CuaHealthResponse {
  success: boolean;
  data: CuaHealthData;
}

interface KillSwitchData {
  kill_switch_active: boolean;
  reason?: string;
  activated_at?: string;
  was_active?: boolean;
  message: string;
}

interface KillSwitchResponse {
  success: boolean;
  data: KillSwitchData;
}

interface SafetyHealthResponse {
  success: boolean;
  data: LifeSafetyStatus;
}

interface AuditVerifyData {
  is_valid: boolean;
  broken_entries: string[];
  total_broken: number;
  message: string;
}

interface AuditVerifyResponse {
  success: boolean;
  data: AuditVerifyData;
}

interface SiemHealthResponse {
  success: boolean;
  data: Record<string, unknown>;
}

interface SiemEvent {
  [k: string]: unknown;
  timestamp?: string;
  event?: string;
  level?: string;
}

interface SiemEventsResponse {
  success: boolean;
  data?: { events: SiemEvent[]; total: number; log_file?: string; message?: string };
  error?: string;
  message?: string;
}

interface AhmedEtapInfoResponse {
  success: boolean;
  data: {
    skill_text_chars?: number;
    peer_review_matrix?: Record<string, unknown>;
    token_budget_defaults?: Record<string, number>;
    max_retries?: number;
    math_guard_tolerance_pct?: number;
    [k: string]: unknown;
  };
}

interface OrchestrateData {
  verdict?: string;
  math_guard?: Record<string, unknown>;
  peer_review?: Record<string, unknown>;
  shared_context?: Record<string, unknown>;
  response?: Record<string, unknown>;
  iterations?: number;
  elapsed_seconds?: number;
}

interface OrchestrateResponse {
  success: boolean;
  data?: OrchestrateData;
  errors?: string[];
  trace_id?: string;
}

type TabId = "agents" | "chat" | "cua" | "siem" | "orchestration";

// ---------------------------------------------------------------------------
// Fetch helpers (same pattern as EmailDashboard)
// ---------------------------------------------------------------------------

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

async function agentsFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const callerHeaders = init?.headers;
  const mergedHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
  };
  if (callerHeaders instanceof Headers) {
    callerHeaders.forEach((v, k) => {
      mergedHeaders[k] = v;
    });
  } else if (Array.isArray(callerHeaders)) {
    for (const [k, v] of callerHeaders) {
      mergedHeaders[k] = v;
    }
  } else if (callerHeaders && typeof callerHeaders === "object") {
    Object.assign(mergedHeaders, callerHeaders);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: mergedHeaders });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Small UI primitives
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  sub,
  tone = "neutral",
  icon,
}: {
  readonly label: string;
  readonly value: ReactNode;
  readonly sub?: ReactNode;
  readonly tone?: "success" | "danger" | "warning" | "neutral";
  readonly icon?: ReactNode;
}) {
  const toneClass = {
    success: "text-green-400",
    danger: "text-red-400",
    warning: "text-amber-400",
    neutral: "text-zinc-100",
  }[tone];
  const iconBg = {
    success: "bg-green-500/10 text-green-400",
    danger: "bg-red-500/10 text-red-400",
    warning: "bg-amber-500/10 text-amber-400",
    neutral: "bg-zinc-500/10 text-zinc-300",
  }[tone];
  return (
    <Card>
      <CardSection className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] uppercase tracking-wider text-zinc-400 font-semibold">
              {label}
            </p>
            <p className={`mt-1 text-2xl font-bold ${toneClass}`}>{value}</p>
            {sub ? <p className="mt-1 text-xs text-zinc-500">{sub}</p> : null}
          </div>
          {icon ? <div className={`shrink-0 rounded-lg p-2 ${iconBg}`}>{icon}</div> : null}
        </div>
      </CardSection>
    </Card>
  );
}

function agentStatusClass(s: string): string {
  if (s === "active") return "bg-green-500/10 text-green-300 border-green-500/30";
  if (s === "coming_soon" || s === "coming-soon" || s === "disabled") {
    return "bg-amber-500/10 text-amber-300 border-amber-500/30";
  }
  return "bg-zinc-500/10 text-zinc-300 border-zinc-500/30";
}

function AgentStatusBadge({ status }: { readonly status: string }) {
  const s = status.toLowerCase();
  const cls = agentStatusClass(s);
  return <Badge className={`border ${cls}`}>{status}</Badge>;
}

function BooleanBadge({ ok, yes, no }: { readonly ok: boolean; yes: string; no: string }) {
  return ok ? (
    <Badge className="bg-green-500/10 text-green-300 border border-green-500/30">
      <CheckCircle2 className="w-3 h-3 mr-1" />
      {yes}
    </Badge>
  ) : (
    <Badge className="bg-red-500/10 text-red-300 border border-red-500/30">
      <XCircle className="w-3 h-3 mr-1" />
      {no}
    </Badge>
  );
}

function ErrorBanner({ message }: { readonly message: string }) {
  return (
    <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
      <AlertTriangle className="mr-2 inline h-4 w-4" />
      {message}
    </div>
  );
}

function LoadingInline({ label }: { readonly label: string }) {
  return (
    <div className="flex items-center gap-2 text-zinc-400">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

// Pretty-print a JSON object in a scrollable <pre>.
function JsonBlock({ data }: { readonly data: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-md border border-zinc-700 bg-zinc-900 p-3 text-xs text-zinc-200">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function AgentsControlPanelPage() {
  const { notify } = useNotify();
  const [tab, setTab] = useState<TabId>("agents");

  // ─── Agents tab state ──────────────────────────────────────────────
  const [agents, setAgents] = useState<AgentMeta[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [detailAgent, setDetailAgent] = useState<AgentMeta | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [agentsInfo, setAgentsInfo] = useState<AgentsInfoResponse["data"] | null>(null);

  // ─── Chat tab state ────────────────────────────────────────────────
  const [expertMessage, setExpertMessage] = useState("");
  const [expertResult, setExpertResult] = useState<Record<string, unknown> | null>(null);
  const [expertLoading, setExpertLoading] = useState(false);
  const [guiMessage, setGuiMessage] = useState("");
  const [guiResult, setGuiResult] = useState<Record<string, unknown> | null>(null);
  const [guiLoading, setGuiLoading] = useState(false);

  // ─── CUA & Safety tab state ────────────────────────────────────────
  const [cuaHealth, setCuaHealth] = useState<CuaHealthData | null>(null);
  const [cuaHealthLoading, setCuaHealthLoading] = useState(false);
  const [cuaHealthError, setCuaHealthError] = useState<string | null>(null);
  const [safetyHealth, setSafetyHealth] = useState<LifeSafetyStatus | null>(null);
  const [auditVerify, setAuditVerify] = useState<AuditVerifyData | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [killOpen, setKillOpen] = useState(false);
  const [killReason, setKillReason] = useState("manual_api_call");
  const [killLoading, setKillLoading] = useState(false);
  const [deactivateLoading, setDeactivateLoading] = useState(false);
  const [execMessage, setExecMessage] = useState("");
  const [execMaxSteps, setExecMaxSteps] = useState(15);
  const [execConfirm, setExecConfirm] = useState(true);
  const [execResult, setExecResult] = useState<Record<string, unknown> | null>(null);
  const [execLoading, setExecLoading] = useState(false);

  // ─── SIEM tab state ────────────────────────────────────────────────
  const [siemHealth, setSiemHealth] = useState<Record<string, unknown> | null>(null);
  const [siemHealthLoading, setSiemHealthLoading] = useState(false);
  const [siemEvents, setSiemEvents] = useState<SiemEvent[]>([]);
  const [siemEventsLoading, setSiemEventsLoading] = useState(false);
  const [siemError, setSiemError] = useState<string | null>(null);
  const [siemLimit, setSiemLimit] = useState(50);

  // ─── Orchestration tab state ───────────────────────────────────────
  const [ahmedInfo, setAhmedInfo] = useState<AhmedEtapInfoResponse["data"] | null>(null);
  const [ahmedInfoLoading, setAhmedInfoLoading] = useState(false);
  const [orchStudyType, setOrchStudyType] = useState("load_flow");
  const [orchProjectName, setOrchProjectName] = useState("default");
  const [orchBaseMva, setOrchBaseMva] = useState(100);
  const [orchBaseKv, setOrchBaseKv] = useState(115);
  const [orchClaimValue, setOrchClaimValue] = useState(1);
  const [orchClaimUnit, setOrchClaimUnit] = useState("pu");
  const [orchQuantityKind, setOrchQuantityKind] = useState("voltage");
  const [orchExpectedUnit, setOrchExpectedUnit] = useState("");
  const [orchBudgetTokens, setOrchBudgetTokens] = useState(8000);
  const [orchLeadAgent, setOrchLeadAgent] = useState("");
  const [orchResult, setOrchResult] = useState<OrchestrateData | null>(null);
  const [orchLoading, setOrchLoading] = useState(false);
  const [orchError, setOrchError] = useState<string | null>(null);

  const [autoRefresh, setAutoRefresh] = useState(true);

  // -------------------------------------------------------------------------
  // Data loaders
  // -------------------------------------------------------------------------

  const loadAgents = useCallback(async () => {
    setAgentsLoading(true);
    setAgentsError(null);
    try {
      const res = await agentsFetch<AgentsListResponse>("/api/v1/agents");
      setAgents(res.agents);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setAgentsError(msg);
    } finally {
      setAgentsLoading(false);
    }
  }, []);

  const loadAgentsInfo = useCallback(async () => {
    try {
      const res = await agentsFetch<AgentsInfoResponse>("/api/v1/agents/info");
      setAgentsInfo(res.data);
    } catch {
      // Non-critical; info card simply stays hidden.
    }
  }, []);

  const loadCuaHealth = useCallback(async () => {
    setCuaHealthLoading(true);
    setCuaHealthError(null);
    try {
      const res = await agentsFetch<CuaHealthResponse>("/api/v1/agents/etap-gui/health");
      setCuaHealth(res.data);
      setSafetyHealth(res.data.life_safety);
      // Also fetch the canonical safety/health endpoint so the life_safety
      // status is always up-to-date independent of the CUA health snapshot.
      try {
        const safetyRes = await agentsFetch<SafetyHealthResponse>(
          "/api/v1/agents/etap-gui/safety/health",
        );
        setSafetyHealth(safetyRes.data);
      } catch {
        // Keep the snapshot from CUA health if the dedicated call fails.
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setCuaHealthError(msg);
    } finally {
      setCuaHealthLoading(false);
    }
  }, []);

  const loadSiemHealth = useCallback(async () => {
    setSiemHealthLoading(true);
    try {
      const res = await agentsFetch<SiemHealthResponse>("/api/v1/agents/etap-gui/siem/health");
      setSiemHealth(res.data);
    } catch {
      // Non-critical.
    } finally {
      setSiemHealthLoading(false);
    }
  }, []);

  const loadSiemEvents = useCallback(async () => {
    setSiemEventsLoading(true);
    setSiemError(null);
    try {
      const res = await agentsFetch<SiemEventsResponse>(
        `/api/v1/agents/etap-gui/siem/events?limit=${siemLimit}`,
      );
      setSiemEvents(res.data?.events ?? []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setSiemError(msg);
    } finally {
      setSiemEventsLoading(false);
    }
  }, [siemLimit]);

  const loadAhmedInfo = useCallback(async () => {
    setAhmedInfoLoading(true);
    try {
      const res = await agentsFetch<AhmedEtapInfoResponse>("/api/v1/agents/ahmed-etap/info");
      setAhmedInfo(res.data);
    } catch {
      // Non-critical.
    } finally {
      setAhmedInfoLoading(false);
    }
  }, []);

  // ─── Initial load + tab-triggered loads ────────────────────────────
  useEffect(() => {
    // SIEM tab needs two loaders; break out to keep main effect flat.
    const loadSiemTabData = () => {
      if (!siemHealth) loadSiemHealth();
      if (siemEvents.length === 0) loadSiemEvents();
    };
    switch (tab) {
      case "agents":
        if (agents.length === 0) {
          loadAgents();
          loadAgentsInfo();
        }
        break;
      case "cua":
        if (!cuaHealth) loadCuaHealth();
        break;
      case "siem":
        loadSiemTabData();
        break;
      case "orchestration":
        if (!ahmedInfo) loadAhmedInfo();
        break;
    }
  }, [
    tab,
    agents.length,
    cuaHealth,
    siemHealth,
    siemEvents.length,
    ahmedInfo,
    loadAgents,
    loadAgentsInfo,
    loadCuaHealth,
    loadSiemHealth,
    loadSiemEvents,
    loadAhmedInfo,
  ]);

  // Auto-refresh (30s) for Agents + CUA health + SIEM events.
  useEffect(() => {
    if (!autoRefresh) return;
    const reload = () => {
      switch (tab) {
        case "agents":
          loadAgents();
          break;
        case "cua":
          loadCuaHealth();
          break;
        case "siem":
          loadSiemEvents();
          break;
      }
    };
    const id = setInterval(reload, 30_000);
    return () => clearInterval(id);
  }, [autoRefresh, tab, loadAgents, loadCuaHealth, loadSiemEvents]);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const openAgentDetail = useCallback(
    async (agentId: string) => {
      setDetailLoading(true);
      setDetailOpen(true);
      setDetailAgent(null);
      try {
        const cached = agents.find((a) => a.id === agentId);
        if (cached) {
          setDetailAgent(cached);
          setDetailLoading(false);
          return;
        }
        const res = await agentsFetch<AgentDetailResponse>(
          `/api/v1/agents/${encodeURIComponent(agentId)}`,
        );
        setDetailAgent(res.agent);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        notify("error", `Failed to load agent: ${msg}`);
      } finally {
        setDetailLoading(false);
      }
    },
    [agents, notify],
  );

  const sendExpertChat = useCallback(async () => {
    if (!expertMessage.trim()) {
      notify("error", "Message must not be empty");
      return;
    }
    setExpertLoading(true);
    setExpertResult(null);
    try {
      const res = await agentsFetch<ChatResponse>("/api/v1/agents/etap-expert/chat", {
        method: "POST",
        body: JSON.stringify({ message: expertMessage }),
      });
      if (res.success && res.data) {
        setExpertResult(res.data);
      } else {
        notify("error", res.errors?.[0] ?? "Expert chat failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Expert chat failed: ${msg}`);
    } finally {
      setExpertLoading(false);
    }
  }, [expertMessage, notify]);

  const sendGuiChat = useCallback(async () => {
    if (!guiMessage.trim()) {
      notify("error", "Message must not be empty");
      return;
    }
    setGuiLoading(true);
    setGuiResult(null);
    try {
      const res = await agentsFetch<ChatResponse>("/api/v1/agents/etap-gui/chat", {
        method: "POST",
        body: JSON.stringify({ message: guiMessage }),
      });
      if (res.success && res.data) {
        setGuiResult(res.data);
      } else {
        notify("error", res.errors?.[0] ?? "GUI chat failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `GUI chat failed: ${msg}`);
    } finally {
      setGuiLoading(false);
    }
  }, [guiMessage, notify]);

  const runCuaExecute = useCallback(async () => {
    if (!execMessage.trim()) {
      notify("error", "Objective must not be empty");
      return;
    }
    setExecLoading(true);
    setExecResult(null);
    try {
      const res = await agentsFetch<ChatResponse>("/api/v1/agents/etap-gui/execute", {
        method: "POST",
        body: JSON.stringify({
          message: execMessage,
          max_steps: execMaxSteps,
          require_confirmation: execConfirm,
        }),
      });
      if (res.success && res.data) {
        setExecResult(res.data);
      } else {
        notify("error", res.errors?.[0] ?? "CUA execute failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `CUA execute failed: ${msg}`);
    } finally {
      setExecLoading(false);
    }
  }, [execMessage, execMaxSteps, execConfirm, notify]);

  const activateKillSwitch = useCallback(async () => {
    setKillLoading(true);
    try {
      const res = await agentsFetch<KillSwitchResponse>(
        `/api/v1/agents/etap-gui/kill-switch/activate?reason=${encodeURIComponent(killReason)}`,
        { method: "POST" },
      );
      notify("error", `Kill switch ACTIVATED: ${res.data.message}`);
      setKillOpen(false);
      await loadCuaHealth();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Failed to activate kill switch: ${msg}`);
    } finally {
      setKillLoading(false);
    }
  }, [killReason, notify, loadCuaHealth]);

  const deactivateKillSwitch = useCallback(async () => {
    setDeactivateLoading(true);
    try {
      const res = await agentsFetch<KillSwitchResponse>(
        "/api/v1/agents/etap-gui/kill-switch/deactivate",
        { method: "POST" },
      );
      notify("success", `Kill switch deactivated: ${res.data.message}`);
      await loadCuaHealth();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Failed to deactivate kill switch: ${msg}`);
    } finally {
      setDeactivateLoading(false);
    }
  }, [notify, loadCuaHealth]);

  const verifyAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const res = await agentsFetch<AuditVerifyResponse>(
        "/api/v1/agents/etap-gui/safety/audit/verify",
      );
      setAuditVerify(res.data);
      if (res.data.is_valid) {
        notify("success", res.data.message);
      } else {
        notify("error", res.data.message);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Audit verify failed: ${msg}`);
    } finally {
      setAuditLoading(false);
    }
  }, [notify]);

  const runOrchestration = useCallback(async () => {
    if (!orchStudyType.trim()) {
      notify("error", "Study type must not be empty");
      return;
    }
    setOrchLoading(true);
    setOrchError(null);
    setOrchResult(null);
    try {
      const body: Record<string, unknown> = {
        study_type: orchStudyType,
        project_name: orchProjectName,
        base_mva: orchBaseMva,
        base_kv: orchBaseKv,
        claim_value: orchClaimValue,
        claim_unit: orchClaimUnit,
        quantity_kind: orchQuantityKind,
        budget_tokens: orchBudgetTokens,
      };
      if (orchExpectedUnit.trim()) body.expected_unit = orchExpectedUnit;
      if (orchLeadAgent.trim()) body.lead_agent = orchLeadAgent;

      const res = await agentsFetch<OrchestrateResponse>(
        "/api/v1/agents/ahmed-etap/orchestrate",
        { method: "POST", body: JSON.stringify(body) },
      );
      if (res.success && res.data) {
        setOrchResult(res.data);
        notify("success", `Orchestration ${res.data.verdict ?? "complete"}`);
      } else {
        const msg = res.errors?.[0] ?? "Orchestration blocked";
        setOrchError(msg);
        notify("error", msg);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setOrchError(msg);
      notify("error", `Orchestration failed: ${msg}`);
    } finally {
      setOrchLoading(false);
    }
  }, [
    orchStudyType,
    orchProjectName,
    orchBaseMva,
    orchBaseKv,
    orchClaimValue,
    orchClaimUnit,
    orchQuantityKind,
    orchExpectedUnit,
    orchBudgetTokens,
    orchLeadAgent,
    notify,
  ]);

  // -------------------------------------------------------------------------
  // Derived values
  // -------------------------------------------------------------------------

  const filteredAgents = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter(
      (a) =>
        a.id.toLowerCase().includes(q) ||
        a.name.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.standard.toLowerCase().includes(q),
    );
  }, [agents, search]);

  const refreshCurrent = useCallback(() => {
    if (tab === "agents") {
      loadAgents();
      loadAgentsInfo();
    }
    if (tab === "cua") loadCuaHealth();
    if (tab === "siem") {
      loadSiemHealth();
      loadSiemEvents();
    }
    if (tab === "orchestration") loadAhmedInfo();
  }, [tab, loadAgents, loadAgentsInfo, loadCuaHealth, loadSiemHealth, loadSiemEvents, loadAhmedInfo]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-zinc-100">
              <Bot className="h-7 w-7 text-cyan-400" />
              Agents Control Panel
            </h1>
            <p className="mt-1 text-sm text-zinc-400">
              Administer all 25 AI agents, CUA safety, SIEM forwarding, and the AhmedETAP
              orchestration pipeline
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={refreshCurrent}>
              <RefreshCw className="mr-1.5 h-4 w-4" />
              Refresh
            </Button>
            <Button variant="secondary" onClick={() => setAutoRefresh((v) => !v)}>
              {autoRefresh ? "Auto: 30s" : "Auto: off"}
            </Button>
          </div>
        </header>

        {/* Tabs */}
        <Tabs
          tabs={[
            { id: "agents", label: "Agents" },
            { id: "chat", label: "Agent Chat" },
            { id: "cua", label: "CUA & Safety" },
            { id: "siem", label: "SIEM" },
            { id: "orchestration", label: "Orchestration" },
          ]}
          activeTab={tab}
          onChange={(v) => setTab(v as TabId)}
        />

        {/* ─── Agents Tab ─────────────────────────────────────────── */}
        {tab === "agents" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-6"
          >
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-[240px]">
                <input
                  type="text"
                  placeholder="Search agents by id, name, standard…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-500"
                />
              </div>
              <span className="text-xs text-zinc-500">
                {filteredAgents.length} / {agents.length} agents
              </span>
            </div>

            {agentsError && <ErrorBanner message={agentsError} />}
            {agentsLoading && agents.length === 0 && <LoadingInline label="Loading agents…" />}

            {!agentsLoading && agents.length === 0 && !agentsError && (
              <EmptyState
                icon={<Bot className="h-8 w-8" />}
                title="No agents found"
                description="The agent registry returned an empty list."
              />
            )}

            {filteredAgents.length > 0 && (
              <Card>
                <CardHeader title="Registered Agents" />
                <CardSection>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                          <th className="px-3 py-2">Name</th>
                          <th className="px-3 py-2">ID</th>
                          <th className="px-3 py-2">Standard</th>
                          <th className="px-3 py-2">Status</th>
                          <th className="px-3 py-2">Model</th>
                          <th className="px-3 py-2">Provider</th>
                          <th className="px-3 py-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredAgents.map((a) => (
                          <tr
                            key={a.id}
                            className="border-b border-zinc-900 hover:bg-zinc-900/40"
                          >
                            <td className="px-3 py-2 font-medium text-zinc-100">{a.name}</td>
                            <td className="px-3 py-2 font-mono text-xs text-zinc-400">{a.id}</td>
                            <td className="px-3 py-2 text-zinc-400">{a.standard || "—"}</td>
                            <td className="px-3 py-2">
                              <AgentStatusBadge status={a.status} />
                            </td>
                            <td className="px-3 py-2 text-zinc-400">{a.model || "—"}</td>
                            <td className="px-3 py-2 text-zinc-400">{a.provider || "—"}</td>
                            <td className="px-3 py-2 text-right">
                              <Button
                                variant="secondary"
                                onClick={() => openAgentDetail(a.id)}
                                title="View agent detail"
                              >
                                <Eye className="mr-1 h-3.5 w-3.5" />
                                View
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardSection>
              </Card>
            )}

            {agentsInfo && (
              <Card>
                <CardHeader title="Prompt Integration Info" />
                <CardSection>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <StatCard
                      label="Available Prompts"
                      value={agentsInfo.prompt_count ?? 0}
                      tone="neutral"
                      icon={<Sparkles className="h-5 w-5" />}
                    />
                    <StatCard
                      label="Agents Registered"
                      value={
                        agentsInfo.agents ? Object.keys(agentsInfo.agents).length : agents.length
                      }
                      tone="neutral"
                      icon={<Bot className="h-5 w-5" />}
                    />
                    <StatCard
                      label="Info Source"
                      value="orchestrator"
                      sub="ChiefEngineeringOrchestrator"
                      tone="neutral"
                      icon={<Cpu className="h-5 w-5" />}
                    />
                  </div>
                  {agentsInfo.available_prompts && agentsInfo.available_prompts.length > 0 && (
                    <div className="mt-4">
                      <p className="mb-2 text-xs uppercase tracking-wider text-zinc-500">
                        Prompt handles
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {agentsInfo.available_prompts.map((p) => (
                          <Badge
                            key={p}
                            className="bg-zinc-800 text-zinc-300 border border-zinc-700"
                          >
                            {p}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardSection>
              </Card>
            )}
          </motion.div>
        )}

        {/* ─── Agent Chat Tab ─────────────────────────────────────── */}
        {tab === "chat" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2"
          >
            {/* ETAP Expert chat */}
            <Card>
              <CardHeader title="ETAP Expert Chat" />
              <CardSection className="space-y-3">
                <p className="text-xs text-zinc-500">
                  6-step workflow (PARSE → SEARCH → VALIDATE → SIMULATE → FORMAT → QA). Returns
                  Format A/B/C/D.
                </p>
                <textarea
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
                  rows={4}
                  placeholder="Ask the ETAP expert a question…"
                  value={expertMessage}
                  onChange={(e) => setExpertMessage(e.target.value)}
                />
                <Button variant="primary" onClick={sendExpertChat} disabled={expertLoading}>
                  {expertLoading ? (
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-1.5 h-4 w-4" />
                  )}
                  Ask Expert
                </Button>
                {expertResult && (
                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">Response</p>
                    <JsonBlock data={expertResult} />
                  </div>
                )}
              </CardSection>
            </Card>

            {/* ETAP GUI chat */}
            <Card>
              <CardHeader title="ETAP GUI Agent Chat" />
              <CardSection className="space-y-3">
                <p className="text-xs text-zinc-500">
                  Classifies into Analyze / Monitor / Control / Solve. Control and Solve require
                  confirmation.
                </p>
                <textarea
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
                  rows={4}
                  placeholder="Ask the GUI agent to analyze or control ETAP…"
                  value={guiMessage}
                  onChange={(e) => setGuiMessage(e.target.value)}
                />
                <Button variant="primary" onClick={sendGuiChat} disabled={guiLoading}>
                  {guiLoading ? (
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-1.5 h-4 w-4" />
                  )}
                  Ask GUI
                </Button>
                {guiResult && (
                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">Response</p>
                    <JsonBlock data={guiResult} />
                  </div>
                )}
              </CardSection>
            </Card>
          </motion.div>
        )}

        {/* ─── CUA & Safety Tab ───────────────────────────────────── */}
        {tab === "cua" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-6"
          >
            {cuaHealthError && <ErrorBanner message={cuaHealthError} />}
            {cuaHealthLoading && !cuaHealth && <LoadingInline label="Loading CUA health…" />}

            {cuaHealth && (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <StatCard
                    label="CUA Loop"
                    value={
                      <BooleanBadge
                        ok={cuaHealth.cua_loop_available}
                        yes="Available"
                        no="Unavailable"
                      />
                    }
                    tone={cuaHealth.cua_loop_available ? "success" : "danger"}
                    icon={<Cpu className="h-5 w-5" />}
                  />
                  <StatCard
                    label="Kill Switch"
                    value={
                      <BooleanBadge
                        ok={!cuaHealth.life_safety.kill_switch_active}
                        yes="Inactive"
                        no="ACTIVE"
                      />
                    }
                    tone={cuaHealth.life_safety.kill_switch_active ? "danger" : "success"}
                    icon={<PowerOff className="h-5 w-5" />}
                  />
                  <StatCard
                    label="Audit Chain"
                    value={
                      <BooleanBadge
                        ok={cuaHealth.life_safety.audit_chain_valid}
                        yes="Valid"
                        no="BROKEN"
                      />
                    }
                    tone={cuaHealth.life_safety.audit_chain_valid ? "success" : "danger"}
                    icon={<ShieldCheck className="h-5 w-5" />}
                  />
                  <StatCard
                    label="Lethal Patterns"
                    value={cuaHealth.life_safety.lethal_patterns_count}
                    sub={`${cuaHealth.life_safety.dual_confirmation_patterns_count} dual-confirm`}
                    tone="warning"
                    icon={<ShieldAlert className="h-5 w-5" />}
                  />
                </div>

                {cuaHealth.missing_dependencies.length > 0 && (
                  <Card>
                    <CardHeader title="Missing CUA Dependencies" />
                    <CardSection>
                      <div className="flex flex-wrap gap-2">
                        {cuaHealth.missing_dependencies.map((d) => (
                          <Badge
                            key={d}
                            className="bg-amber-500/10 text-amber-300 border border-amber-500/30"
                          >
                            {d}
                          </Badge>
                        ))}
                      </div>
                    </CardSection>
                  </Card>
                )}
              </>
            )}

            {/* Kill-switch controls */}
            <Card>
              <CardHeader title="Emergency Kill Switch" />
              <CardSection className="space-y-3">
                <p className="text-xs text-zinc-500">
                  The kill switch is file-based and non-bypassable. Once activated, the CUA Loop
                  aborts on the next action check and cannot run until deactivated.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="danger"
                    onClick={() => setKillOpen(true)}
                    disabled={safetyHealth?.kill_switch_active}
                    title="Activate emergency stop"
                  >
                    <PowerOff className="mr-1.5 h-4 w-4" />
                    Activate Kill Switch
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={deactivateKillSwitch}
                    disabled={
                      deactivateLoading || !safetyHealth?.kill_switch_active
                    }
                    title="Deactivate emergency stop"
                  >
                    {deactivateLoading ? (
                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : (
                      <Power className="mr-1.5 h-4 w-4" />
                    )}
                    Deactivate
                  </Button>
                </div>
              </CardSection>
            </Card>

            {/* Safety health + audit verify */}
            <Card>
              <CardHeader title="Safety Audit Verification" />
              <CardSection className="space-y-3">
                <p className="text-xs text-zinc-500">
                  The tamper-evident audit log uses SHA-256 chaining. Any modification to a past
                  entry breaks the chain.
                </p>
                <Button variant="secondary" onClick={verifyAudit} disabled={auditLoading}>
                  {auditLoading ? (
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  ) : (
                    <ShieldCheck className="mr-1.5 h-4 w-4" />
                  )}
                  Verify Audit Chain
                </Button>
                {auditVerify && (
                  <div className="rounded-md border border-zinc-800 bg-zinc-900/50 p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <BooleanBadge
                        ok={auditVerify.is_valid}
                        yes="Chain Intact"
                        no="Chain Broken"
                      />
                      <span className="text-xs text-zinc-500">
                        {auditVerify.total_broken} broken entries
                      </span>
                    </div>
                    <p className="text-sm text-zinc-300">{auditVerify.message}</p>
                    {auditVerify.broken_entries.length > 0 && (
                      <ul className="mt-2 list-inside list-disc text-xs text-red-300">
                        {auditVerify.broken_entries.map((e) => (
                          <li key={e}>{e}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </CardSection>
            </Card>

            {/* CUA Execute */}
            <Card>
              <CardHeader title="CUA Execute" />
              <CardSection className="space-y-3">
                <p className="text-xs text-zinc-500">
                  Run the real CUA loop — captures screenshots, analyses them via Gemini Vision,
                  and drives pyautogui to click/type/hotkey.
                </p>
                <textarea
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500"
                  rows={3}
                  placeholder="Objective, e.g. 'Open ETAP and run Load Flow'"
                  value={execMessage}
                  onChange={(e) => setExecMessage(e.target.value)}
                />
                <div className="flex flex-wrap items-center gap-4">
                  <label className="flex items-center gap-2 text-sm text-zinc-400">
                  <span>Max steps:</span>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={execMaxSteps}
                    onChange={(e) => setExecMaxSteps(Number(e.target.value))}
                    className="w-20 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-100"
                  />
                </label>
                <label className="flex items-center gap-2 text-sm text-zinc-400">
                  <input
                    type="checkbox"
                    checked={execConfirm}
                    onChange={(e) => setExecConfirm(e.target.checked)}
                    className="h-4 w-4"
                  />
                  <span>Require confirmation</span>
                </label>
                  <Button variant="primary" onClick={runCuaExecute} disabled={execLoading}>
                    {execLoading ? (
                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : (
                      <Terminal className="mr-1.5 h-4 w-4" />
                    )}
                    Execute CUA
                  </Button>
                </div>
                {execResult && (
                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">Result</p>
                    <JsonBlock data={execResult} />
                  </div>
                )}
              </CardSection>
            </Card>
          </motion.div>
        )}

        {/* ─── SIEM Tab ───────────────────────────────────────────── */}
        {tab === "siem" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-6"
          >
            <Card>
              <CardHeader title="SIEM Syslog Forwarder" />
              <CardSection>
                {siemHealthLoading && <LoadingInline label="Loading SIEM health…" />}
                {siemHealth && <JsonBlock data={siemHealth} />}
                {!siemHealth && !siemHealthLoading && (
                  <p className="text-sm text-zinc-500">No SIEM health data.</p>
                )}
              </CardSection>
            </Card>

            <Card>
              <CardHeader title="Recent SIEM Events" />
              <CardSection className="space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <label className="text-sm text-zinc-400" htmlFor="siem-limit">
                    Limit:
                  </label>
                  <select
                    id="siem-limit"
                    value={siemLimit}
                    onChange={(e) => setSiemLimit(Number(e.target.value))}
                    className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                  >
                    {[10, 25, 50, 100, 200].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                  <Button variant="secondary" onClick={loadSiemEvents} disabled={siemEventsLoading}>
                    {siemEventsLoading ? (
                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-1.5 h-4 w-4" />
                    )}
                    Reload
                  </Button>
                </div>

                {siemError && <ErrorBanner message={siemError} />}
                {siemEventsLoading && siemEvents.length === 0 && (
                  <LoadingInline label="Loading events…" />
                )}
                {!siemEventsLoading && siemEvents.length === 0 && !siemError && (
                  <EmptyState
                    icon={<Radio className="h-8 w-8" />}
                    title="No SIEM events"
                    description="Set SIEM_LOG_FILE env var to enable event viewing."
                  />
                )}

                {siemEvents.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                          <th className="px-3 py-2">#</th>
                          <th className="px-3 py-2">Event</th>
                          <th className="px-3 py-2">Level</th>
                          <th className="px-3 py-2">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody>
                        {siemEvents.map((ev, i) => (
                          <tr
                            key={`siem-${ev.timestamp ?? i}-${ev.event ?? i}`}
                            className="border-b border-zinc-900"
                          >
                            <td className="px-3 py-2 text-zinc-500">{i + 1}</td>
                            <td className="px-3 py-2 text-zinc-200">
                              {String(ev.event ?? "—")}
                            </td>
                            <td className="px-3 py-2">
                              <Badge className="bg-zinc-800 text-zinc-300 border border-zinc-700">
                                {String(ev.level ?? "info")}
                              </Badge>
                            </td>
                            <td className="px-3 py-2 text-zinc-400">
                              {String(ev.timestamp ?? "—")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardSection>
            </Card>
          </motion.div>
        )}

        {/* ─── Orchestration Tab ──────────────────────────────────── */}
        {tab === "orchestration" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-6"
          >
            <Card>
              <CardHeader title="AhmedETAP Skill Info" />
              <CardSection>
                {ahmedInfoLoading && <LoadingInline label="Loading skill info…" />}
                {ahmedInfo && (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <StatCard
                      label="Skill Text"
                      value={`${(ahmedInfo.skill_text_chars ?? 0).toLocaleString()} chars`}
                      tone="neutral"
                      icon={<Sparkles className="h-5 w-5" />}
                    />
                    <StatCard
                      label="Max Retries"
                      value={ahmedInfo.max_retries ?? 0}
                      tone="neutral"
                      icon={<RefreshCw className="h-5 w-5" />}
                    />
                    <StatCard
                      label="MathGuard Tol."
                      value={`${ahmedInfo.math_guard_tolerance_pct ?? 0.01}%`}
                      tone="neutral"
                      icon={<ShieldCheck className="h-5 w-5" />}
                    />
                    <StatCard
                      label="Token Budget"
                      value={
                        ahmedInfo.token_budget_defaults?.default ?? 8000
                      }
                      tone="neutral"
                      icon={<Activity className="h-5 w-5" />}
                    />
                  </div>
                )}
                {ahmedInfo?.peer_review_matrix && (
                  <div className="mt-4">
                    <p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">
                      Peer Review Matrix
                    </p>
                    <JsonBlock data={ahmedInfo.peer_review_matrix} />
                  </div>
                )}
              </CardSection>
            </Card>

            <Card>
              <CardHeader title="Run Orchestration" />
              <CardSection className="space-y-3">
                <p className="text-xs text-zinc-500">
                  Pipeline: Parse → SharedContext → Lead Agent → MathGuard → Peer Review → ship |
                  loop (max 2 retries).
                </p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Study Type</span>
                    <input
                      type="text"
                      value={orchStudyType}
                      onChange={(e) => setOrchStudyType(e.target.value)}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                      placeholder="load_flow"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Project Name</span>
                    <input
                      type="text"
                      value={orchProjectName}
                      onChange={(e) => setOrchProjectName(e.target.value)}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Lead Agent (optional)</span>
                    <input
                      type="text"
                      value={orchLeadAgent}
                      onChange={(e) => setOrchLeadAgent(e.target.value)}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                      placeholder="auto-derived"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Base MVA</span>
                    <input
                      type="number"
                      step="any"
                      value={orchBaseMva}
                      onChange={(e) => setOrchBaseMva(Number(e.target.value))}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Base kV</span>
                    <input
                      type="number"
                      step="any"
                      value={orchBaseKv}
                      onChange={(e) => setOrchBaseKv(Number(e.target.value))}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Budget Tokens</span>
                    <input
                      type="number"
                      value={orchBudgetTokens}
                      onChange={(e) => setOrchBudgetTokens(Number(e.target.value))}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Claim Value</span>
                    <input
                      type="number"
                      step="any"
                      value={orchClaimValue}
                      onChange={(e) => setOrchClaimValue(Number(e.target.value))}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Claim Unit</span>
                    <input
                      type="text"
                      value={orchClaimUnit}
                      onChange={(e) => setOrchClaimUnit(e.target.value)}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Quantity Kind</span>
                    <input
                      type="text"
                      value={orchQuantityKind}
                      onChange={(e) => setOrchQuantityKind(e.target.value)}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm text-zinc-400">
                    <span>Expected Unit (optional)</span>
                    <input
                      type="text"
                      value={orchExpectedUnit}
                      onChange={(e) => setOrchExpectedUnit(e.target.value)}
                      className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
                    />
                  </label>
                </div>
                <Button variant="primary" onClick={runOrchestration} disabled={orchLoading}>
                  {orchLoading ? (
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  ) : (
                    <Network className="mr-1.5 h-4 w-4" />
                  )}
                  Run Orchestration
                </Button>

                {orchError && <ErrorBanner message={orchError} />}

                {orchResult && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs uppercase tracking-wider text-zinc-500">
                        Verdict
                      </span>
                      <Badge
                        className={
                          (orchResult.verdict ?? "").startsWith("approved")
                            ? "bg-green-500/10 text-green-300 border border-green-500/30"
                            : "bg-red-500/10 text-red-300 border border-red-500/30"
                        }
                      >
                        {orchResult.verdict ?? "unknown"}
                      </Badge>
                      {orchResult.iterations != null && (
                        <span className="text-xs text-zinc-500">
                          {orchResult.iterations} iteration(s)
                        </span>
                      )}
                      {orchResult.elapsed_seconds != null && (
                        <span className="text-xs text-zinc-500">
                          {orchResult.elapsed_seconds.toFixed(2)}s
                        </span>
                      )}
                    </div>
                    <JsonBlock data={orchResult} />
                  </div>
                )}
              </CardSection>
            </Card>
          </motion.div>
        )}
      </div>

      {/* ─── Agent detail modal ──────────────────────────────────── */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title="Agent Detail"
        size="lg"
      >
        {(() => {
          if (detailLoading) return <LoadingInline label="Loading agent…" />;
          if (detailAgent) {
            return (
              <div className="space-y-3 text-sm">
                <div className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-cyan-400" />
                  <span className="text-lg font-bold text-zinc-100">{detailAgent.name}</span>
                  <AgentStatusBadge status={detailAgent.status} />
                </div>
                <p className="text-zinc-400">{detailAgent.description}</p>
                <dl className="grid grid-cols-2 gap-2 text-xs">
                  <dt className="text-zinc-500">ID</dt>
                  <dd className="font-mono text-zinc-300">{detailAgent.id}</dd>
                  <dt className="text-zinc-500">Standard</dt>
                  <dd className="text-zinc-300">{detailAgent.standard || "—"}</dd>
                  <dt className="text-zinc-500">Model</dt>
                  <dd className="text-zinc-300">{detailAgent.model || "—"}</dd>
                  <dt className="text-zinc-500">Provider</dt>
                  <dd className="text-zinc-300">{detailAgent.provider || "—"}</dd>
                </dl>
                <div>
                  <p className="mb-1 text-xs uppercase tracking-wider text-zinc-500">Capabilities</p>
                  <div className="flex flex-wrap gap-2">
                    {detailAgent.capabilities.length === 0 ? (
                      <span className="text-zinc-500">—</span>
                    ) : (
                      detailAgent.capabilities.map((c) => (
                        <Badge
                          key={c}
                          className="bg-cyan-500/10 text-cyan-300 border border-cyan-500/30"
                        >
                          {c}
                        </Badge>
                      ))
                    )}
                  </div>
                </div>
              </div>
            );
          }
          return <p className="text-sm text-zinc-500">No agent data.</p>;
        })()}
      </Modal>

      {/* ─── Kill-switch confirmation modal ──────────────────────── */}
      <Modal
        open={killOpen}
        onClose={() => setKillOpen(false)}
        title="Activate Emergency Kill Switch"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setKillOpen(false)} disabled={killLoading}>
              Cancel
            </Button>
            <Button variant="danger" onClick={activateKillSwitch} disabled={killLoading}>
              {killLoading ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <PowerOff className="mr-1.5 h-4 w-4" />
              )}
              Activate Now
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-sm">
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-red-300">
            <AlertTriangle className="mr-2 inline h-4 w-4" />
            This will immediately halt the CUA Loop on its next action check. Only deactivate
            after the safety issue has been resolved and reviewed.
          </div>
          <label className="flex flex-col gap-1 text-zinc-400">
            <span>Reason</span>
            <input
              type="text"
              value={killReason}
              onChange={(e) => setKillReason(e.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
            />
          </label>
        </div>
      </Modal>
    </div>
  );
}
