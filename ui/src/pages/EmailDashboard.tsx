/**
 * Email Dashboard Page — Real-time monitoring of transactional email delivery.
 *
 * Wires to all 7 JSON endpoints exposed by api/email_dashboard.py
 * (prefix /api/v1/email-dashboard):
 *   GET  /api/stats                  — aggregate stats (window_hours)
 *   GET  /api/recent                 — recent send records (limit, flow)
 *   GET  /api/by-day                 — per-day send counts (days)
 *   GET  /api/record/{record_id}     — single record detail
 *   POST /api/clear                  — clear old log records (max_age_hours)
 *   GET  /api/config                 — non-secret Resend config
 *
 * The HTML endpoint GET / is intentionally NOT used — we render our own
 * React UI so the dashboard integrates with the rest of the app (sidebar,
 * i18n, theme, toast notifications).
 *
 * Ref: TASK-4
 */

import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Eye,
  Loader2,
  Mail,
  RefreshCw,
  Settings as SettingsIcon,
  Trash2,
  TrendingDown,
  TrendingUp,
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
// Types — mirror api/email_dashboard.py + services/email_send_log.py
// ---------------------------------------------------------------------------

interface EmailSendRecord {
  id: string;
  timestamp: string;
  recipient: string;
  subject: string;
  flow: string;
  success: boolean;
  message_id: string | null;
  error: string | null;
  status_code: number | null;
  elapsed_ms: number;
  tags: string[];
}

interface SendStats {
  window_hours: number;
  total: number;
  succeeded: number;
  failed: number;
  success_rate: number;
  avg_elapsed_ms: number;
  by_flow: Record<string, { total: number; success: number; failed: number }>;
  top_errors: { error: string; count: number }[];
  top_recipients: { email: string; count: number }[];
  buffer_size: number;
  buffer_max: number;
}

interface DayBucket {
  date: string;
  total: number;
  succeeded: number;
  failed: number;
}

interface ResendConfig {
  RESEND_ENABLED: string;
  RESEND_FROM_EMAIL: string;
  RESEND_FROM_NAME: string;
  RESEND_REPLY_TO: string;
  RESEND_TIMEOUT_SECONDS: string;
  RESEND_MAX_RETRIES: string;
  RESEND_RATE_LIMIT_MAX: string;
  RESEND_RATE_LIMIT_WINDOW: string;
  RESEND_LOGIN_ALERTS_ENABLED: string;
  RESEND_LOCKOUT_ALERTS_ENABLED: string;
  RESEND_WELCOME_EMAIL_ENABLED: string;
  RESEND_NOTIFICATION_EMAILS_ENABLED: string;
  OTP_TTL_SECONDS: string;
  MAGIC_LINK_TTL_SECONDS: string;
  EMAIL_DIGEST_ENABLED: string;
  EMAIL_DIGEST_SCHEDULE_DAILY: string;
  EMAIL_BRAND_NAME: string;
  EMAIL_APP_URL: string;
  RESEND_API_KEY_SET: string;
  [key: string]: string; // index signature for the dynamic config table
}

interface StatsResponse {
  success: boolean;
  stats: SendStats;
}

interface RecentResponse {
  success: boolean;
  records: EmailSendRecord[];
}

interface ByDayResponse {
  success: boolean;
  days: DayBucket[];
}

interface RecordResponse {
  success: boolean;
  record: EmailSendRecord;
}

interface ClearResponse {
  success: boolean;
  removed: number;
  max_age_hours: number;
}

interface ConfigResponse {
  success: boolean;
  config: ResendConfig;
}

type TabId = "overview" | "recent" | "config";

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

async function dashboardFetch<T>(path: string, init?: RequestInit): Promise<T> {
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
// Small UI primitives (kept local to avoid bloating the shared ui/ folder)
// ---------------------------------------------------------------------------

function successRateTone(rate: number): "success" | "warning" | "danger" {
  if (rate >= 95) return "success";
  if (rate >= 80) return "warning";
  return "danger";
}

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

function FlowBadge({ flow }: { readonly flow: string }) {
  const palette: Record<string, string> = {
    otp: "bg-blue-500/10 text-blue-300 border-blue-500/30",
    password_reset: "bg-amber-500/10 text-amber-300 border-amber-500/30",
    welcome: "bg-green-500/10 text-green-300 border-green-500/30",
    login_alert: "bg-purple-500/10 text-purple-300 border-purple-500/30",
    lockout_alert: "bg-red-500/10 text-red-300 border-red-500/30",
    notification: "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
    digest: "bg-indigo-500/10 text-indigo-300 border-indigo-500/30",
  };
  const cls = palette[flow] ?? "bg-zinc-500/10 text-zinc-300 border-zinc-500/30";
  return <Badge className={`border ${cls}`}>{flow}</Badge>;
}

function SuccessBadge({ success }: { readonly success: boolean }) {
  return success ? (
    <Badge className="bg-green-500/10 text-green-300 border border-green-500/30">
      <CheckCircle2 className="w-3 h-3 mr-1" />
      OK
    </Badge>
  ) : (
    <Badge className="bg-red-500/10 text-red-300 border border-red-500/30">
      <XCircle className="w-3 h-3 mr-1" />
      FAIL
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

const WINDOW_OPTIONS = [
  { value: 1, label: "Last hour" },
  { value: 6, label: "Last 6 hours" },
  { value: 24, label: "Last 24 hours" },
  { value: 168, label: "Last 7 days" },
  { value: 720, label: "Last 30 days" },
];

const FLOW_OPTIONS = [
  "",
  "otp",
  "password_reset",
  "welcome",
  "login_alert",
  "lockout_alert",
  "notification",
  "digest",
];

export default function EmailDashboardPage() {
  const { notify } = useNotify();
  const [tab, setTab] = useState<TabId>("overview");
  const [windowHours, setWindowHours] = useState(24);
  const [days, setDays] = useState(7);
  const [flowFilter, setFlowFilter] = useState("");

  // ─── Overview state ─────────────────────────────────────────────────
  const [stats, setStats] = useState<SendStats | null>(null);
  const [byDay, setByDay] = useState<DayBucket[]>([]);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);

  // ─── Recent state ───────────────────────────────────────────────────
  const [recent, setRecent] = useState<EmailSendRecord[]>([]);
  const [recentLoading, setRecentLoading] = useState(false);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [detailRecord, setDetailRecord] = useState<EmailSendRecord | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  // ─── Config state ───────────────────────────────────────────────────
  const [config, setConfig] = useState<ResendConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);

  // ─── Clear-log modal ────────────────────────────────────────────────
  const [clearOpen, setClearOpen] = useState(false);
  const [clearAgeHours, setClearAgeHours] = useState(720);
  const [clearing, setClearing] = useState(false);

  // ─── Auto-refresh (default 30s when on Overview) ────────────────────
  const [autoRefresh, setAutoRefresh] = useState(true);

  // -------------------------------------------------------------------------
  // Data loaders
  // -------------------------------------------------------------------------

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    setStatsError(null);
    try {
      const [statsRes, byDayRes] = await Promise.all([
        dashboardFetch<StatsResponse>(
          `/api/v1/email-dashboard/api/stats?window_hours=${windowHours}`,
        ),
        dashboardFetch<ByDayResponse>(`/api/v1/email-dashboard/api/by-day?days=${days ?? 7}`),
      ]);
      setStats(statsRes.stats);
      setByDay(byDayRes.days);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatsError(msg);
    } finally {
      setStatsLoading(false);
    }
  }, [windowHours, days]);

  const loadRecent = useCallback(async () => {
    setRecentLoading(true);
    setRecentError(null);
    try {
      const flowParam = flowFilter ? `&flow=${encodeURIComponent(flowFilter)}` : "";
      const res = await dashboardFetch<RecentResponse>(
        `/api/v1/email-dashboard/api/recent?limit=100${flowParam || ""}`,
      );
      setRecent(res.records);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setRecentError(msg);
    } finally {
      setRecentLoading(false);
    }
  }, [flowFilter]);

  const loadConfig = useCallback(async () => {
    setConfigLoading(true);
    setConfigError(null);
    try {
      const res = await dashboardFetch<ConfigResponse>("/api/v1/email-dashboard/api/config");
      setConfig(res.config);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setConfigError(msg);
    } finally {
      setConfigLoading(false);
    }
  }, []);

  // ─── Initial load + auto-refresh ────────────────────────────────────
  useEffect(() => {
    if (tab === "overview") loadStats();
    if (tab === "recent") loadRecent();
    if (tab === "config") loadConfig();
  }, [tab, loadStats, loadRecent, loadConfig]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => {
      if (tab === "overview") loadStats();
      if (tab === "recent") loadRecent();
    }, 30_000);
    return () => clearInterval(id);
  }, [autoRefresh, tab, loadStats, loadRecent]);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const openDetail = useCallback(
    async (recordId: string) => {
      setDetailLoading(true);
      setDetailOpen(true);
      setDetailRecord(null);
      try {
        // Try to use the cached record from the recent list first (avoids
        // a network round-trip in the common case).
        const cached = recent.find((r) => r.id === recordId);
        if (cached) {
          setDetailRecord(cached);
          setDetailLoading(false);
          return;
        }
        const res = await dashboardFetch<RecordResponse>(
          `/api/v1/email-dashboard/api/record/${encodeURIComponent(recordId)}`,
        );
        setDetailRecord(res.record);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        notify("error", `Failed to load record: ${msg}`);
      } finally {
        setDetailLoading(false);
      }
    },
    [recent, notify],
  );

  const handleClear = useCallback(async () => {
    setClearing(true);
    try {
      const res = await dashboardFetch<ClearResponse>("/api/v1/email-dashboard/api/clear", {
        method: "POST",
        body: JSON.stringify({ max_age_hours: clearAgeHours }),
      });
      notify("success", `Cleared ${res.removed} records older than ${res.max_age_hours}h`);
      setClearOpen(false);
      // Reload stats + recent to reflect the change.
      await Promise.all([loadStats(), loadRecent()]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Failed to clear logs: ${msg}`);
    } finally {
      setClearing(false);
    }
  }, [clearAgeHours, notify, loadStats, loadRecent]);

  // -------------------------------------------------------------------------
  // Derived values
  // -------------------------------------------------------------------------

  const maxDayTotal = useMemo(() => Math.max(1, ...byDay.map((d) => d.total)), [byDay]);

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
              <Mail className="h-7 w-7 text-amber-400" />
              Email Dashboard
            </h1>
            <p className="mt-1 text-sm text-zinc-400">
              Real-time monitoring of transactional email delivery via Resend
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                if (tab === "overview") loadStats();
                if (tab === "recent") loadRecent();
                if (tab === "config") loadConfig();
              }}
            >
              <RefreshCw className="mr-1.5 h-4 w-4" />
              Refresh
            </Button>
            <Button variant="secondary" onClick={() => setAutoRefresh((v) => !v)}>
              {autoRefresh ? "Auto: 30s" : "Auto: off"}
            </Button>
            <Button
              variant="danger"
              onClick={() => setClearOpen(true)}
              title="Clear old log records"
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              Clear Old
            </Button>
          </div>
        </header>

        {/* Tabs */}
        <Tabs
          tabs={[
            { id: "overview", label: "Overview" },
            { id: "recent", label: "Recent Sends" },
            { id: "config", label: "Config" },
          ]}
          activeTab={tab}
          onChange={(v) => setTab(v as TabId)}
        />

        {/* ─── Overview Tab ─────────────────────────────────────────── */}
        {tab === "overview" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-6"
          >
            {/* Window selector */}
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-sm text-zinc-400" htmlFor="window-hours">
                Window:
              </label>
              <select
                id="window-hours"
                value={windowHours}
                onChange={(e) => setWindowHours(Number(e.target.value))}
                className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
              >
                {WINDOW_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <label className="ml-2 text-sm text-zinc-400" htmlFor="days-range">
                Days:
              </label>
              <select
                id="days-range"
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
              >
                {[7, 14, 30, 90].map((d) => (
                  <option key={d} value={d}>
                    {d} days
                  </option>
                ))}
              </select>
            </div>

            {/* Error banner */}
            {statsError && (
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
                <AlertTriangle className="mr-2 inline h-4 w-4" />
                {statsError}
              </div>
            )}

            {/* Loading skeleton */}
            {statsLoading && !stats && (
              <div className="flex items-center gap-2 text-zinc-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading stats…
              </div>
            )}

            {/* Stat cards */}
            {stats && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                  label="Total Sends"
                  value={stats.total}
                  sub={`in last ${stats.window_hours}h`}
                  tone="neutral"
                  icon={<Mail className="h-5 w-5" />}
                />
                <StatCard
                  label="Success Rate"
                  value={`${stats.success_rate}%`}
                  sub={`${stats.succeeded} succeeded`}
                  tone={successRateTone(stats.success_rate)}
                  icon={<TrendingUp className="h-5 w-5" />}
                />
                <StatCard
                  label="Failed"
                  value={stats.failed}
                  sub={`${stats.total > 0 ? ((stats.failed / stats.total) * 100).toFixed(1) : 0}% of total`}
                  tone={stats.failed === 0 ? "success" : "danger"}
                  icon={<TrendingDown className="h-5 w-5" />}
                />
                <StatCard
                  label="Avg Latency"
                  value={`${stats.avg_elapsed_ms} ms`}
                  sub={`buffer: ${stats.buffer_size}/${stats.buffer_max}`}
                  tone="neutral"
                  icon={<Clock className="h-5 w-5" />}
                />
              </div>
            )}

            {/* Per-flow breakdown + daily chart */}
            {stats && (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {/* Per-flow */}
                <Card>
                  <CardHeader title="By Flow" />
                  <CardSection>
                    {Object.keys(stats.by_flow).length === 0 ? (
                      <EmptyState
                        icon={<Activity className="h-8 w-8" />}
                        title="No sends in window"
                        description="No email sends have been logged in the selected window."
                      />
                    ) : (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                            <th className="py-2 pr-3">Flow</th>
                            <th className="py-2 px-3">Total</th>
                            <th className="py-2 px-3">OK</th>
                            <th className="py-2 px-3">Fail</th>
                            <th className="py-2 pl-3">Rate</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(stats.by_flow)
                            .sort((a, b) => b[1].total - a[1].total)
                            .map(([flow, c]) => (
                              <tr key={flow} className="border-b border-zinc-900">
                                <td className="py-2 pr-3">
                                  <FlowBadge flow={flow} />
                                </td>
                                <td className="py-2 px-3 tabular-nums">{c.total}</td>
                                <td className="py-2 px-3 tabular-nums text-green-400">
                                  {c.success}
                                </td>
                                <td className="py-2 px-3 tabular-nums text-red-400">{c.failed}</td>
                                <td className="py-2 pl-3 tabular-nums">
                                  {c.total > 0 ? ((c.success / c.total) * 100).toFixed(1) : "0.0"}%
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    )}
                  </CardSection>
                </Card>

                {/* Daily chart */}
                <Card>
                  <CardHeader title={`Daily Sends (last ${days} days)`} />
                  <CardSection>
                    {byDay.length === 0 ? (
                      <EmptyState
                        icon={<Activity className="h-8 w-8" />}
                        title="No data"
                        description="No daily send data available."
                      />
                    ) : (
                      <div className="space-y-2">
                        {byDay.map((d) => (
                          <div key={d.date} className="flex items-center gap-3 text-sm">
                            <span className="w-24 shrink-0 text-xs text-zinc-500">{d.date}</span>
                            <div className="relative h-6 flex-1 overflow-hidden rounded bg-zinc-800">
                              <div
                                className="absolute inset-y-0 left-0 flex"
                                style={{ width: `${(d.total / maxDayTotal) * 100}%` }}
                              >
                                <div
                                  className="h-full bg-green-500/60"
                                  style={{
                                    width: `${d.total > 0 ? (d.succeeded / d.total) * 100 : 0}%`,
                                  }}
                                />
                                <div
                                  className="h-full bg-red-500/60"
                                  style={{
                                    width: `${d.total > 0 ? (d.failed / d.total) * 100 : 0}%`,
                                  }}
                                />
                              </div>
                            </div>
                            <span className="w-16 shrink-0 text-right tabular-nums text-zinc-300">
                              {d.total}
                            </span>
                          </div>
                        ))}
                        <div className="flex items-center gap-4 pt-2 text-xs text-zinc-500">
                          <span className="flex items-center gap-1">
                            <span className="h-2 w-2 rounded bg-green-500/60" /> Succeeded
                          </span>
                          <span className="flex items-center gap-1">
                            <span className="h-2 w-2 rounded bg-red-500/60" /> Failed
                          </span>
                        </div>
                      </div>
                    )}
                  </CardSection>
                </Card>
              </div>
            )}

            {/* Top errors + top recipients */}
            {stats && (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader title="Top Errors" />
                  <CardSection>
                    {stats.top_errors.length === 0 ? (
                      <p className="py-4 text-center text-sm text-zinc-500">No errors in window.</p>
                    ) : (
                      <ul className="space-y-2 text-sm">
                        {stats.top_errors.map((e) => (
                          <li
                            key={`err-${e.error.slice(0, 40)}-${e.count}`}
                            className="flex items-start gap-2"
                          >
                            <Badge className="bg-red-500/10 text-red-300 border border-red-500/30">
                              ×{e.count}
                            </Badge>
                            <span className="flex-1 break-all font-mono text-xs text-zinc-400">
                              {e.error}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardSection>
                </Card>
                <Card>
                  <CardHeader title="Top Recipients" />
                  <CardSection>
                    {stats.top_recipients.length === 0 ? (
                      <p className="py-4 text-center text-sm text-zinc-500">
                        No recipients in window.
                      </p>
                    ) : (
                      <ul className="space-y-2 text-sm">
                        {stats.top_recipients.map((r) => (
                          <li key={`rec-${r.email}`} className="flex items-center gap-2">
                            <Badge className="bg-zinc-500/10 text-zinc-300 border border-zinc-500/30">
                              ×{r.count}
                            </Badge>
                            <span className="flex-1 break-all font-mono text-xs text-zinc-400">
                              {r.email}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardSection>
                </Card>
              </div>
            )}
          </motion.div>
        )}

        {/* ─── Recent Tab ───────────────────────────────────────────── */}
        {tab === "recent" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-4"
          >
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-sm text-zinc-400" htmlFor="flow-filter">
                Flow:
              </label>
              <select
                id="flow-filter"
                value={flowFilter}
                onChange={(e) => setFlowFilter(e.target.value)}
                className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100"
              >
                {FLOW_OPTIONS.map((f) => (
                  <option key={f} value={f}>
                    {f === "" ? "All flows" : f}
                  </option>
                ))}
              </select>
              <span className="text-xs text-zinc-500">Showing last 100 records</span>
            </div>

            {recentError && (
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
                <AlertTriangle className="mr-2 inline h-4 w-4" />
                {recentError}
              </div>
            )}

            {(() => {
              if (recentLoading && recent.length === 0) {
                return (
                  <div className="flex items-center gap-2 text-zinc-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading recent sends…
                  </div>
                );
              }
              if (recent.length === 0) {
                return (
                  <EmptyState
                    icon={<Mail className="h-8 w-8" />}
                    title="No sends logged"
                    description="No email send records match the current filter."
                  />
                );
              }
              return (
                <CardSection className="overflow-x-auto p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                        <th className="py-2 px-3">Timestamp</th>
                        <th className="py-2 px-3">Flow</th>
                        <th className="py-2 px-3">Recipient</th>
                        <th className="py-2 px-3">Subject</th>
                        <th className="py-2 px-3">Status</th>
                        <th className="py-2 px-3">Latency</th>
                        <th className="py-2 px-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recent.map((r) => (
                        <tr key={r.id} className="border-b border-zinc-900 hover:bg-zinc-900/50">
                          <td className="py-2 px-3 font-mono text-xs text-zinc-400">
                            {new Date(r.timestamp).toLocaleString()}
                          </td>
                          <td className="py-2 px-3">
                            <FlowBadge flow={r.flow} />
                          </td>
                          <td className="py-2 px-3 font-mono text-xs text-zinc-300">
                            {r.recipient}
                          </td>
                          <td
                            className="py-2 px-3 max-w-xs truncate text-zinc-300"
                            title={r.subject}
                          >
                            {r.subject}
                          </td>
                          <td className="py-2 px-3">
                            <SuccessBadge success={r.success} />
                          </td>
                          <td className="py-2 px-3 tabular-nums text-zinc-400">{r.elapsed_ms}ms</td>
                          <td className="py-2 px-3">
                            <Button
                              variant="ghost"
                              onClick={() => openDetail(r.id)}
                              title="View detail"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardSection>
              </Card>
              );
            })()}
          </motion.div>
        )}

        {/* ─── Config Tab ───────────────────────────────────────────── */}
        {tab === "config" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6"
          >
            {configError && (
              <div className="mb-4 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
                <AlertTriangle className="mr-2 inline h-4 w-4" />
                {configError}
              </div>
            )}

            {(() => {
              if (configLoading) {
                return (
                  <div className="flex items-center gap-2 text-zinc-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading config…
                  </div>
                );
              }
              if (!config) return null;
              return (
              <Card>
                <CardHeader
                  title={
                    <span className="flex items-center gap-2">
                      <SettingsIcon className="h-4 w-4" />
                      Resend Configuration (non-secret)
                    </span>
                  }
                />
                <CardSection className="overflow-x-auto p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wider text-zinc-500">
                        <th className="py-2 px-3">Key</th>
                        <th className="py-2 px-3">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(config).map(([k, v]) => (
                        <tr key={k} className="border-b border-zinc-900">
                          <td className="py-2 px-3 font-mono text-xs text-zinc-400">{k}</td>
                          <td className="py-2 px-3 font-mono text-xs text-zinc-200">{String(v)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardSection>
              </Card>
              );
            })()}
          </motion.div>
        )}
      </div>

      {/* ─── Record Detail Modal ─────────────────────────────────────── */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title="Email Send Record"
        size="lg"
      >
        {(() => {
          if (detailLoading) {
            return (
              <div className="flex items-center gap-2 p-6 text-zinc-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading record…
              </div>
            );
          }
          if (!detailRecord) {
            return <p className="p-6 text-sm text-zinc-400">Record not found.</p>;
          }
          return (
          <div className="space-y-3 p-4">
            <div className="flex items-center gap-2">
              <SuccessBadge success={detailRecord.success} />
              <FlowBadge flow={detailRecord.flow} />
            </div>
            <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-wider text-zinc-500">ID</dt>
                <dd className="font-mono text-xs text-zinc-300 break-all">{detailRecord.id}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wider text-zinc-500">Timestamp</dt>
                <dd className="font-mono text-xs text-zinc-300">
                  {new Date(detailRecord.timestamp).toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wider text-zinc-500">Recipient</dt>
                <dd className="font-mono text-xs text-zinc-300">{detailRecord.recipient}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wider text-zinc-500">Status Code</dt>
                <dd className="font-mono text-xs text-zinc-300">
                  {detailRecord.status_code ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wider text-zinc-500">Latency</dt>
                <dd className="font-mono text-xs text-zinc-300">{detailRecord.elapsed_ms} ms</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wider text-zinc-500">Message ID</dt>
                <dd className="font-mono text-xs text-zinc-300 break-all">
                  {detailRecord.message_id ?? "—"}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase tracking-wider text-zinc-500">Subject</dt>
                <dd className="text-zinc-200">{detailRecord.subject}</dd>
              </div>
              {detailRecord.error && (
                <div className="sm:col-span-2">
                  <dt className="text-xs uppercase tracking-wider text-red-400">Error</dt>
                  <dd className="rounded-md border border-red-500/30 bg-red-500/10 p-2 font-mono text-xs text-red-300 break-all">
                    {detailRecord.error}
                  </dd>
                </div>
              )}
              {detailRecord.tags.length > 0 && (
                <div className="sm:col-span-2">
                  <dt className="text-xs uppercase tracking-wider text-zinc-500">Tags</dt>
                  <dd className="flex flex-wrap gap-1">
                    {detailRecord.tags.map((t) => (
                      <Badge
                        key={`tag-${t}`}
                        className="bg-zinc-500/10 text-zinc-300 border border-zinc-500/30"
                      >
                        {t}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </div>
          );
        })()}
      </Modal>

      {/* ─── Clear Old Records Modal ─────────────────────────────────── */}
      <Modal
        open={clearOpen}
        onClose={() => (clearing ? undefined : setClearOpen(false))}
        title="Clear Old Log Records"
        size="md"
      >
        <div className="space-y-4 p-4">
          <p className="text-sm text-zinc-300">
            Remove email send log records older than the specified age. This action cannot be
            undone.
          </p>
          <label className="block text-sm text-zinc-400" htmlFor="clear-age">
            Max age (hours):
          </label>
          <input
            id="clear-age"
            type="number"
            min={1}
            max={8760}
            value={clearAgeHours}
            onChange={(e) => setClearAgeHours(Math.max(1, Number(e.target.value)))}
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
          />
          <p className="text-xs text-zinc-500">
            Default: 720 hours (30 days). Records older than this will be permanently removed from
            the in-memory buffer.
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setClearOpen(false)} disabled={clearing}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleClear} disabled={clearing}>
              {clearing ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  Clearing…
                </>
              ) : (
                <>
                  <Trash2 className="mr-1.5 h-4 w-4" />
                  Clear Records
                </>
              )}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
