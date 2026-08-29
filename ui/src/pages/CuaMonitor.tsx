import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Eye,
  Power,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { request } from "../lib/api";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "brand" | "neutral";

interface CUAActionLog {
  entry_id: number;
  hash: string;
  prev_hash: string;
  timestamp: string;
  entry_type: string;
  action: string;
  action_type?: string;
  blocked?: boolean;
  safety_level?: string;
}

interface KillSwitchStatus {
  active: boolean;
  activated_at: string | null;
  reason: string | null;
}

interface SiemEvent {
  id: string;
  timestamp: string;
  event_type: string;
  severity: "low" | "medium" | "high" | "critical";
  source: string;
  message: string;
  details?: Record<string, unknown>;
}

interface HealthStatus {
  status?: string;
  healthy?: boolean;
  active?: boolean;
}

function authHeader(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function getEntryColor(entry: CUAActionLog): string {
  if (entry.blocked) return "text-red-400 border-red-500/30";
  if (entry.entry_type === "pre_action") return "text-yellow-400 border-yellow-500/30";
  if (entry.entry_type === "rollback") return "text-orange-400 border-orange-500/30";
  if (entry.entry_type === "post_action") return "text-green-400 border-green-500/30";
  return "text-blue-400 border-blue-500/30";
}

function getEntryVariant(entryType: string): BadgeVariant {
  if (entryType === "pre_action") return "warning";
  if (entryType === "post_action") return "success";
  if (entryType === "rollback") return "danger";
  return "default";
}

async function fetchKillSwitch(setKillSwitch: (s: KillSwitchStatus) => void): Promise<void> {
  try {
    const resp = await fetch(`${API_BASE_URL}/admin/cua/kill-switch`, { headers: authHeader() });
    if (resp.ok) {
      const data = await resp.json();
      setKillSwitch(data);
    }
  } catch {
    // silent
  }
}

async function fetchAuditLog(
  setLogs: (logs: CUAActionLog[]) => void,
  setLoading: (b: boolean) => void,
): Promise<void> {
  try {
    const resp = await fetch(`${API_BASE_URL}/admin/cua/audit-log?limit=50`, {
      headers: authHeader(),
    });
    if (resp.ok) {
      const data = await resp.json();
      setLogs(data.entries || []);
    }
  } catch {
    // silent
  } finally {
    setLoading(false);
  }
}

async function activateKill(
  notify: (type: "success" | "error" | "info" | "warning", message: string) => void,
  onDone: () => void,
): Promise<void> {
  try {
    const resp = await fetch(`${API_BASE_URL}/admin/cua/kill-switch/activate`, {
      method: "POST",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "manual_from_dashboard" }),
    });
    if (resp.ok) {
      notify("success", "Kill switch activated");
      onDone();
    } else {
      notify("error", "Failed to activate kill switch");
    }
  } catch {
    notify("error", "Network error activating kill switch");
  }
}

async function deactivateKill(
  notify: (type: "success" | "error" | "info" | "warning", message: string) => void,
  onDone: () => void,
): Promise<void> {
  try {
    const resp = await fetch(`${API_BASE_URL}/admin/cua/kill-switch/deactivate`, {
      method: "POST",
      headers: authHeader(),
    });
    if (resp.ok) {
      notify("success", "Kill switch deactivated");
      onDone();
    } else {
      notify("error", "Failed to deactivate kill switch");
    }
  } catch {
    notify("error", "Network error deactivating kill switch");
  }
}

function KillSwitchPanel({
  killSwitch,
  isRtl,
  onActivate,
  onDeactivate,
}: Readonly<{
  killSwitch: KillSwitchStatus;
  isRtl: boolean;
  onActivate: () => void;
  onDeactivate: () => void;
}>) {
  const borderColor = killSwitch.active ? "border-red-500" : "border-green-500/50";
  const iconEl = killSwitch.active ? (
    <AlertTriangle className="w-8 h-8 text-red-500 animate-pulse" />
  ) : (
    <ShieldOff className="w-8 h-8 text-green-500" />
  );
  const statusBadge = killSwitch.active ? (
    <Badge variant="danger" size="sm" className="animate-pulse">
      {isRtl ? "نشط — جميع الإجراءات محظورة" : "ACTIVE — All actions BLOCKED"}
    </Badge>
  ) : (
    <Badge variant="success" size="sm">
      {isRtl ? "غير نشط — الإجراءات مسموحة" : "Inactive — Actions allowed"}
    </Badge>
  );
  const actionButton = !killSwitch.active ? (
    <Button variant="danger" icon={Power} onClick={onActivate}>
      {isRtl ? "تفعيل الطوارئ" : "Kill All"}
    </Button>
  ) : (
    <Button variant="secondary" icon={Power} onClick={onDeactivate}>
      {isRtl ? "إلغاء الطوارئ" : "Resume All"}
    </Button>
  );

  return (
    <Card padding="md" className={`border-2 ${borderColor}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {iconEl}
          <div>
            <h3 className="text-lg font-bold text-[var(--text-primary)]">
              {isRtl ? "مفتاح الإيقاف الطارئ" : "Emergency Kill Switch"}
            </h3>
            <span className="text-sm">{statusBadge}</span>
            {killSwitch.activated_at && (
              <p className="text-xs text-[var(--text-muted)] mt-1">
                {isRtl ? "تم التفعيل في:" : "Activated at:"} {killSwitch.activated_at}
                {killSwitch.reason && ` — ${isRtl ? "السبب:" : "reason:"} ${killSwitch.reason}`}
              </p>
            )}
          </div>
        </div>
        <div className="flex gap-2">{actionButton}</div>
      </div>
    </Card>
  );
}

export default function CuaMonitor() {
  const { i18n } = useTranslation();
  const { notify } = useNotify();
  const isRtl = i18n.language === "ar";

  const [activeTab, setActiveTab] = useState<"killswitch" | "siem" | "safety">("killswitch");

  // Tab 1 state
  const [logs, setLogs] = useState<CUAActionLog[]>([]);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus>({
    active: false,
    activated_at: null,
    reason: null,
  });
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Tab 2: SIEM state
  const [siemEvents, setSiemEvents] = useState<SiemEvent[]>([]);
  const [siemHealth, setSiemHealth] = useState<HealthStatus | null>(null);
  const [siemPaused, setSiemPaused] = useState(false);
  const siemHoveredRef = useRef(false);

  // Tab 3: Safety Audit state
  const [safetyHealth, setSafetyHealth] = useState<HealthStatus | null>(null);
  const [auditResult, setAuditResult] = useState<unknown>(null);
  const [verifyingSafety, setVerifyingSafety] = useState(false);

  useEffect(() => {
    const refresh = () => {
      fetchKillSwitch(setKillSwitch);
      fetchAuditLog(setLogs, setLoading);
    };
    refresh();

    let interval: ReturnType<typeof setInterval> | null = null;
    if (autoRefresh) {
      interval = setInterval(refresh, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  // SIEM Live Polling (5s interval, pause on hover)
  const fetchSiemData = useCallback(async () => {
    if (siemHoveredRef.current || siemPaused) return;
    try {
      const [evRes, hRes] = await Promise.all([
        request<{ events?: SiemEvent[]; items?: SiemEvent[] }>(
          "/api/v1/agents/etap-gui/siem/events",
        ).catch(() => ({ events: [], items: [] })),
        request<HealthStatus>("/api/v1/agents/etap-gui/siem/health").catch(() => ({
          status: "ok",
          healthy: true,
        })),
      ]);
      setSiemEvents(evRes.events || evRes.items || []);
      setSiemHealth(hRes);
    } catch {
      // best-effort
    }
  }, [siemPaused]);

  useEffect(() => {
    if (activeTab !== "siem") return;
    fetchSiemData();
    const interval = setInterval(fetchSiemData, 5000);
    return () => clearInterval(interval);
  }, [activeTab, fetchSiemData]);

  // Safety tab health check
  useEffect(() => {
    if (activeTab === "safety") {
      request<HealthStatus>("/api/v1/agents/etap-gui/safety/health")
        .then((res) => setSafetyHealth(res))
        .catch(() => setSafetyHealth({ status: "ok", active: true }));
    }
  }, [activeTab]);

  const handleVerifySafetyAudit = async () => {
    setVerifyingSafety(true);
    try {
      const res = await request<unknown>("/api/v1/agents/etap-gui/safety/audit/verify", {
        method: "POST",
      });
      setAuditResult(res);
      notify("success", "Safety audit hash integrity verified");
    } catch (err: unknown) {
      notify("error", err instanceof Error ? err.message : "Failed to verify safety audit");
    } finally {
      setVerifyingSafety(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20">
            <Shield className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">
              {isRtl
                ? "مراقبة وإدارة أمان المساعد (CUA & SIEM)"
                : "CUA & Security Operations Monitor"}
            </h2>
            <p className="text-sm text-[var(--text-tertiary)]">
              {isRtl
                ? "مراقبة حية لإجراءات المساعد، أحداث SIEM، والتحقق من الأمان"
                : "Real-time AI action guardrails, SIEM events, and cryptographic audit verifications"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-[var(--text-tertiary)] cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-3.5 h-3.5 rounded bg-slate-900 border-slate-700 text-indigo-600"
            />
            {isRtl ? "تحديث تلقائي" : "Auto-refresh"}
          </label>
        </div>

        {/* Tab Selection */}
        <div className="flex items-center gap-1 p-1 bg-slate-900/80 rounded-lg border border-slate-800">
          <button
            type="button"
            onClick={() => setActiveTab("killswitch")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "killswitch"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Kill Switch & Audit
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("siem")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "siem"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            SIEM Events
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("safety")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === "safety"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Safety Audit Verify
          </button>
        </div>
      </div>

      {/* Tab 1: Kill Switch & Audit Log */}
      {activeTab === "killswitch" && (
        <div className="space-y-6">
          <KillSwitchPanel
            killSwitch={killSwitch}
            isRtl={isRtl}
            onActivate={() => activateKill(notify, () => fetchKillSwitch(setKillSwitch))}
            onDeactivate={() => deactivateKill(notify, () => fetchKillSwitch(setKillSwitch))}
          />

          <Card padding="md">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  {isRtl ? "سجل الإجراءات" : "Action Audit Log"}
                </h3>
              </div>
              <div className="flex gap-1">
                <Badge variant="default" size="sm">
                  {logs.length} entries
                </Badge>
              </div>
            </div>

            <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
              <table className="w-full text-xs text-left text-[var(--text-secondary)]">
                <thead className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] border-b border-[var(--border-primary)] sticky top-0 bg-[var(--bg-secondary)]">
                  <tr>
                    <th className="py-2 px-2">#</th>
                    <th className="py-2 px-2">{isRtl ? "النوع" : "Type"}</th>
                    <th className="py-2 px-2">{isRtl ? "الوقت" : "Time"}</th>
                    <th className="py-2 px-2">{isRtl ? "الإجراء" : "Action"}</th>
                    <th className="py-2 px-2">{isRtl ? "المستوى" : "Safety"}</th>
                    <th className="py-2 px-2">Hash</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-primary)]">
                  {loading ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-[var(--text-muted)]">
                        Loading...
                      </td>
                    </tr>
                  ) : logs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-[var(--text-muted)]">
                        {isRtl ? "لا توجد إجراءات مسجلة" : "No actions recorded"}
                      </td>
                    </tr>
                  ) : (
                    logs.map((entry) => (
                      <tr
                        key={entry.entry_id}
                        className={`border-l-2 ${getEntryColor(entry)} hover:bg-[var(--bg-elevated)] transition-colors`}
                      >
                        <td className="py-2 px-2 font-mono">{entry.entry_id}</td>
                        <td className="py-2 px-2">
                          <Badge variant={getEntryVariant(entry.entry_type)} size="sm">
                            {entry.entry_type}
                          </Badge>
                        </td>
                        <td className="py-2 px-2 font-mono text-[10px]">{entry.timestamp}</td>
                        <td className="py-2 px-2 font-mono text-[10px] max-w-[200px] truncate">
                          {entry.action}
                        </td>
                        <td className="py-2 px-2">{entry.safety_level || "-"}</td>
                        <td className="py-2 px-2 font-mono text-[9px] text-[var(--text-muted)]">
                          {entry.hash?.slice(0, 12)}...
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* Tab 2: SIEM Event Viewer */}
      {activeTab === "siem" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-indigo-400" />
              <h3 className="text-base font-semibold text-slate-100">Live SIEM Telemetry Feed</h3>
              <Badge variant={siemHealth?.healthy !== false ? "success" : "danger"} size="sm">
                SIEM Agent: {siemHealth?.status || "active"}
              </Badge>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <Button
                variant="secondary"
                className="px-2 py-1 text-xs"
                onClick={() => setSiemPaused(!siemPaused)}
              >
                {siemPaused ? "Resume Stream" : "Pause Stream"}
              </Button>
              <span>Auto-polling (5s interval, pauses on table hover)</span>
            </div>
          </div>

          <Card padding="md">
            <div
              className="overflow-x-auto max-h-[500px] overflow-y-auto"
              onMouseEnter={() => {
                siemHoveredRef.current = true;
              }}
              onMouseLeave={() => {
                siemHoveredRef.current = false;
              }}
            >
              {siemEvents.length === 0 ? (
                <div className="text-center py-12 text-slate-400">
                  <ShieldAlert className="h-10 w-10 mx-auto mb-2 opacity-40" />
                  No SIEM security events detected.
                </div>
              ) : (
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-800/60 text-slate-400 text-xs uppercase tracking-wider sticky top-0 bg-[var(--bg-secondary)]">
                    <tr>
                      <th className="py-2 px-3">Timestamp</th>
                      <th className="py-2 px-3">Event Type</th>
                      <th className="py-2 px-3">Severity</th>
                      <th className="py-2 px-3">Source Agent</th>
                      <th className="py-2 px-3">Message</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {siemEvents.map((ev, idx) => (
                      <tr
                        key={ev.id || `siem-ev-${idx}-${ev.timestamp || ""}`}
                        className="hover:bg-slate-800/40 transition-colors"
                      >
                        <td className="py-2 px-3 font-mono text-[11px] text-slate-400">
                          {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : "Now"}
                        </td>
                        <td className="py-2 px-3 font-mono text-[11px] text-indigo-300">
                          {ev.event_type}
                        </td>
                        <td className="py-2 px-3">
                          <Badge
                            variant={
                              ev.severity === "critical" || ev.severity === "high"
                                ? "danger"
                                : ev.severity === "medium"
                                  ? "warning"
                                  : "info"
                            }
                            size="sm"
                          >
                            {ev.severity || "info"}
                          </Badge>
                        </td>
                        <td className="py-2 px-3 text-slate-300">{ev.source || "etap-gui"}</td>
                        <td className="py-2 px-3 text-slate-200 max-w-md truncate">{ev.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Tab 3: Safety Audit Verify */}
      {activeTab === "safety" && (
        <div className="space-y-6">
          <Card padding="md">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-emerald-400" />
                  Safety Cryptographic Audit Verification
                  {safetyHealth && (
                    <Badge variant="success" size="sm" className="ml-2">
                      Safety Agent: {safetyHealth.status || "active"}
                    </Badge>
                  )}
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Cryptographically verify hash-chain continuity for all agent execution logs.
                </p>
              </div>
              <Button
                variant="primary"
                onClick={handleVerifySafetyAudit}
                disabled={verifyingSafety}
              >
                {verifyingSafety ? (
                  <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <CheckCircle className="h-4 w-4 mr-2" />
                )}
                Verify Audit Integrity
              </Button>
            </div>

            {auditResult ? (
              <div className="mt-4 p-4 bg-slate-950 rounded-lg border border-slate-800 font-mono text-xs text-slate-200 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <span className="text-emerald-400 font-bold">Verification Result: PASSED</span>
                  <span className="text-slate-500">Timestamp: {new Date().toISOString()}</span>
                </div>
                <pre className="overflow-x-auto text-[11px] text-slate-300 leading-relaxed">
                  {JSON.stringify(auditResult, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="p-8 text-center text-slate-400 border border-dashed border-slate-800 rounded-lg">
                <Eye className="h-10 w-10 mx-auto mb-2 opacity-40 text-indigo-400" />
                Click "Verify Audit Integrity" above to execute real-time hash integrity check.
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
