/**
 * Email Digest Page — Admin/debug UI for the email-digest backend module.
 *
 * Wires to all 4 endpoints exposed by api/email_digest.py
 * (prefix /api/v1/email-digest):
 *   GET  /config                  — show current digest configuration
 *   POST /generate                — manually trigger a digest for a user
 *   GET  /preview/{email}         — render the next digest HTML (no send)
 *   POST /schedule/run            — process all scheduled digests (cron call)
 *
 * The page is admin/debug-oriented: it lets an operator inspect digest
 * configuration, fire a one-off digest for a specific user, preview what
 * the next digest would look like, and manually trigger the cron entry
 * point (useful for testing the digest pipeline outside the schedule).
 *
 * Ref: TASK-6
 */

import { motion } from "framer-motion";
import {
  CalendarClock,
  CheckCircle2,
  Eye,
  Mail,
  PlayCircle,
  RefreshCw,
  Send,
  Settings as SettingsIcon,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBanner, LoadingRow, StatRow } from "../components/admin-primitives";
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
import { adminFetch, authHeaders } from "../lib/admin-fetch";

// ---------------------------------------------------------------------------
// Types — mirror api/email_digest.py
// ---------------------------------------------------------------------------

interface DigestConfig {
  enabled: boolean;
  daily_schedule: string;
  weekly_schedule: string;
  timezone: string;
}

interface ConfigResponse {
  success: boolean;
  config: DigestConfig;
}

interface GenerateRequest {
  email: string;
  period: "daily" | "weekly";
  user_name?: string;
}

interface GenerateResult {
  success: boolean;
  message_id?: string | null;
  error?: string | null;
  message?: string;
  total_count?: number;
  by_flow?: Record<string, number>;
  trace_id?: string;
}

interface ScheduleRunResult {
  success: boolean;
  period?: string;
  recipients_count?: number;
  sent?: number;
  failed?: number;
  message?: string;
  now?: string;
  daily_time?: string;
  trace_id?: string;
}

type TabId = "overview" | "generate" | "preview";

// ---------------------------------------------------------------------------
// Fetch helper + UI primitives
// ---------------------------------------------------------------------------
// Replaced with shared adminFetch from lib/admin-fetch.ts and
// StatRow/ErrorBanner/LoadingRow/inputClass/labelClass from
// components/admin-primitives.tsx.
// Ref: fix/admin-pages-hardening (#4 + #6)

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

const PERIOD_OPTIONS: { readonly value: "daily" | "weekly"; readonly label: string }[] = [
  { value: "daily", label: "Daily (last 24h)" },
  { value: "weekly", label: "Weekly (last 7d)" },
];

export default function EmailDigestPage() {
  const { notify } = useNotify();
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabId>("overview");

  // ─── Config state (Overview tab) ────────────────────────────────────
  const [config, setConfig] = useState<DigestConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);

  // ─── Schedule run state (Overview tab) ──────────────────────────────
  const [runResult, setRunResult] = useState<ScheduleRunResult | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  // ─── Generate state (Generate tab) ──────────────────────────────────
  const [genEmail, setGenEmail] = useState("");
  const [genPeriod, setGenPeriod] = useState<"daily" | "weekly">("daily");
  const [genName, setGenName] = useState("");
  const [genResult, setGenResult] = useState<GenerateResult | null>(null);
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  // ─── Preview state (Preview tab) ────────────────────────────────────
  const [prevEmail, setPrevEmail] = useState("");
  const [prevPeriod, setPrevPeriod] = useState<"daily" | "weekly">("daily");
  const [prevHtml, setPrevHtml] = useState<string | null>(null);
  const [prevOpen, setPrevOpen] = useState(false);
  const [prevLoading, setPrevLoading] = useState(false);
  const [prevError, setPrevError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Data loaders
  // -------------------------------------------------------------------------

  const loadConfig = useCallback(async () => {
    setConfigLoading(true);
    setConfigError(null);
    try {
      const res = await adminFetch<ConfigResponse>("/api/v1/email-digest/config");
      setConfig(res.config);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setConfigError(msg);
    } finally {
      setConfigLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "overview" && config === null) loadConfig();
  }, [tab, config, loadConfig]);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const handleRunSchedule = useCallback(async () => {
    setRunLoading(true);
    setRunError(null);
    setRunResult(null);
    try {
      const res = await adminFetch<ScheduleRunResult>("/api/v1/email-digest/schedule/run", {
        method: "POST",
      });
      setRunResult(res);
      if (res.success && res.recipients_count !== undefined) {
        notify(
          "success",
          t("adminPages.emailDigest.scheduleRun.success", {
            sent: res.sent ?? 0,
            failed: res.failed ?? 0,
          }),
        );
      } else if (res.success && res.message) {
        notify("info", res.message);
      } else {
        notify("error", "Schedule run did not return success.");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setRunError(msg);
      notify("error", t("adminPages.emailDigest.scheduleRun.failed", { error: msg }));
    } finally {
      setRunLoading(false);
    }
  }, [notify, t]);

  const handleGenerate = useCallback(async () => {
    if (!genEmail.trim()) {
      setGenError("Email is required.");
      return;
    }
    setGenLoading(true);
    setGenError(null);
    setGenResult(null);
    try {
      const body: GenerateRequest = {
        email: genEmail.trim(),
        period: genPeriod,
        ...(genName.trim() ? { user_name: genName.trim() } : {}),
      };
      const res = await adminFetch<GenerateResult>("/api/v1/email-digest/generate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setGenResult(res);
      if (res.success && (res.total_count ?? 0) > 0) {
        notify(
          "success",
          t("adminPages.emailDigest.generate.success", {
            email: genEmail.trim(),
            period: genPeriod,
          }),
        );
      } else if (res.success && res.message) {
        notify("info", res.message);
      } else {
        notify(
          "error",
          t("adminPages.emailDigest.generate.failed", {
            error: res.error ?? t("adminPages.common.unknownError"),
          }),
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setGenError(msg);
      notify("error", t("adminPages.emailDigest.generate.failed", { error: msg }));
    } finally {
      setGenLoading(false);
    }
  }, [genEmail, genPeriod, genName, notify, t]);

  const handlePreview = useCallback(async () => {
    if (!prevEmail.trim()) {
      setPrevError("Email is required.");
      return;
    }
    setPrevLoading(true);
    setPrevError(null);
    setPrevHtml(null);
    try {
      // Preview returns HTML — use adminFetch with allowPlainText so we
      // get the raw response body without a JSON-parse error.
      // Ref: fix/admin-pages-hardening (#6 — no unsafe cast)
      const html = await adminFetch<string>(
        `/api/v1/email-digest/preview/${encodeURIComponent(prevEmail.trim())}?period=${prevPeriod}`,
        { headers: authHeaders() },
        { allowPlainText: true },
      );
      setPrevHtml(html);
      setPrevOpen(true);
      notify(
        "success",
        t("adminPages.emailDigest.preview.loaded", { defaultValue: "Digest preview loaded." }),
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setPrevError(msg);
      notify("error", t("adminPages.emailDigest.preview.loadFailed", { error: msg }));
    } finally {
      setPrevLoading(false);
    }
  }, [prevEmail, prevPeriod, notify, t]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const tabs = [
    { id: "overview", label: "Overview", icon: <SettingsIcon className="w-4 h-4" /> },
    { id: "generate", label: "Generate", icon: <Send className="w-4 h-4" /> },
    { id: "preview", label: "Preview", icon: <Eye className="w-4 h-4" /> },
  ];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6 p-6 max-w-7xl mx-auto"
    >
      {/* ─── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Mail className="w-6 h-6 text-brand-500" />
            Email Digest
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Admin &amp; debug tools for daily / weekly digest emails. Trigger a one-off digest,
            preview the next one, or run the scheduled batch.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setConfig(null);
            loadConfig();
          }}
          icon={RefreshCw}
        >
          Refresh
        </Button>
      </div>

      <Tabs tabs={tabs} activeTab={tab} onChange={(id) => setTab(id as TabId)} />

      {/* ─── Overview tab ───────────────────────────────────────────────── */}
      {tab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Config card */}
          <Card>
            <CardHeader
              title={
                <span className="flex items-center gap-2">
                  <SettingsIcon className="w-4 h-4" />
                  Digest Configuration
                </span>
              }
              subtitle="Current scheduling & feature flags"
            />
            <CardSection className="p-4">
              {configLoading && <LoadingRow label="Loading configuration…" />}
              {configError && <ErrorBanner message={configError} />}
              {!configLoading && !configError && config && (
                <div data-testid="config-card">
                  <StatRow
                    label="Enabled"
                    value={
                      config.enabled ? (
                        <Badge
                          className="bg-green-500/10 text-green-300 border border-green-500/30"
                          data-testid="config-enabled-badge"
                        >
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                          <span data-testid="config-enabled-text">ENABLED</span>
                        </Badge>
                      ) : (
                        <Badge
                          className="bg-red-500/10 text-red-300 border border-red-500/30"
                          data-testid="config-enabled-badge"
                        >
                          <XCircle className="w-3 h-3 mr-1" />
                          <span data-testid="config-enabled-text">DISABLED</span>
                        </Badge>
                      )
                    }
                  />
                  <StatRow label="Daily schedule" value={config.daily_schedule} />
                  <StatRow label="Weekly schedule" value={config.weekly_schedule} />
                  <StatRow label="Timezone" value={config.timezone} />
                </div>
              )}
              {!configLoading && !configError && !config && (
                <EmptyState
                  icon={<SettingsIcon className="w-8 h-8" />}
                  title="No configuration loaded"
                  description="Click Refresh to retry."
                />
              )}
            </CardSection>
          </Card>

          {/* Schedule run card */}
          <Card>
            <CardHeader
              title={
                <span className="flex items-center gap-2">
                  <CalendarClock className="w-4 h-4" />
                  Run Scheduled Digests
                </span>
              }
              subtitle="Manually trigger the cron entry point"
            />
            <CardSection className="p-4 space-y-4">
              <p className="text-sm text-zinc-400">
                Calls <code className="text-xs font-mono text-zinc-300">POST /schedule/run</code>.
                The backend checks the current time against the configured schedule and only sends
                digests if the window matches; otherwise it returns a skip message. Use this to
                verify the cron pipeline without waiting for the next scheduled slot.
              </p>

              <div className="flex items-center gap-3">
                <Button
                  variant="primary"
                  onClick={handleRunSchedule}
                  loading={runLoading}
                  icon={PlayCircle}
                  data-testid="run-schedule-btn"
                >
                  {runLoading ? "Running…" : "Run Now"}
                </Button>
              </div>

              {runError && <ErrorBanner message={runError} />}

              {runResult && (
                <div
                  data-testid="run-result"
                  className="rounded-md border border-zinc-700 bg-zinc-900/60 p-3 space-y-2"
                >
                  <div className="flex items-center gap-2">
                    {runResult.success ? (
                      <CheckCircle2 className="w-4 h-4 text-green-400" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400" />
                    )}
                    <span className="text-sm font-semibold text-zinc-200">
                      {runResult.success ? "Success" : "Failed"}
                    </span>
                  </div>
                  {runResult.message && (
                    <p className="text-xs text-zinc-400">{runResult.message}</p>
                  )}
                  {runResult.period && <StatRow label="Period" value={runResult.period} />}
                  {runResult.recipients_count !== undefined && (
                    <StatRow label="Recipients" value={runResult.recipients_count} />
                  )}
                  {runResult.sent !== undefined && <StatRow label="Sent" value={runResult.sent} />}
                  {runResult.failed !== undefined && (
                    <StatRow label="Failed" value={runResult.failed} />
                  )}
                  {runResult.now && <StatRow label="Now (UTC)" value={runResult.now} />}
                  {runResult.daily_time && (
                    <StatRow label="Daily time" value={runResult.daily_time} />
                  )}
                  {runResult.trace_id && <StatRow label="Trace ID" value={runResult.trace_id} />}
                </div>
              )}
            </CardSection>
          </Card>
        </div>
      )}

      {/* ─── Generate tab ───────────────────────────────────────────────── */}
      {tab === "generate" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Form card */}
          <Card>
            <CardHeader
              title={
                <span className="flex items-center gap-2">
                  <Send className="w-4 h-4" />
                  Generate &amp; Send Now
                </span>
              }
              subtitle="Manually trigger a digest for a single user"
            />
            <CardSection className="p-4 space-y-4">
              <div>
                <label
                  htmlFor="generate-email"
                  className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                >
                  Recipient email
                </label>
                <input
                  id="generate-email"
                  type="email"
                  value={genEmail}
                  onChange={(e) => setGenEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  data-testid="generate-email"
                />
              </div>

              <div>
                <label
                  htmlFor="generate-period"
                  className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                >
                  Period
                </label>
                <select
                  id="generate-period"
                  value={genPeriod}
                  onChange={(e) => setGenPeriod(e.target.value as "daily" | "weekly")}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  data-testid="generate-period"
                >
                  {PERIOD_OPTIONS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="generate-name"
                  className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                >
                  Display name (optional)
                </label>
                <input
                  id="generate-name"
                  type="text"
                  value={genName}
                  onChange={(e) => setGenName(e.target.value)}
                  placeholder="Ahmed"
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  data-testid="generate-name"
                />
              </div>

              {genError && <ErrorBanner message={genError} />}

              <div className="flex justify-end">
                <Button
                  variant="primary"
                  onClick={handleGenerate}
                  loading={genLoading}
                  icon={Send}
                  disabled={!genEmail.trim()}
                  data-testid="generate-submit"
                >
                  {genLoading ? "Sending…" : "Generate & Send"}
                </Button>
              </div>
            </CardSection>
          </Card>

          {/* Result card */}
          <Card>
            <CardHeader title="Result" subtitle="Backend response from POST /generate" />
            <CardSection className="p-4">
              {!genResult && !genLoading && (
                <EmptyState
                  icon={<Send className="w-8 h-8" />}
                  title="No result yet"
                  description="Fill the form and click Generate & Send to see the backend response here."
                />
              )}
              {genLoading && <LoadingRow label="Sending digest…" />}
              {genResult && (
                <div data-testid="generate-result" className="space-y-2">
                  <div className="flex items-center gap-2">
                    {genResult.success ? (
                      <CheckCircle2 className="w-4 h-4 text-green-400" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400" />
                    )}
                    <span className="text-sm font-semibold text-zinc-200">
                      {genResult.success ? "Success" : "Failed"}
                    </span>
                  </div>

                  {genResult.message && (
                    <p className="text-xs text-zinc-400">{genResult.message}</p>
                  )}
                  {genResult.error && (
                    <div className="rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300 font-mono break-all">
                      {genResult.error}
                    </div>
                  )}

                  {genResult.total_count !== undefined && (
                    <StatRow label="Total count" value={genResult.total_count} />
                  )}
                  {genResult.message_id !== undefined && genResult.message_id !== null && (
                    <StatRow label="Message ID" value={genResult.message_id} />
                  )}
                  {genResult.trace_id && <StatRow label="Trace ID" value={genResult.trace_id} />}

                  {genResult.by_flow && Object.keys(genResult.by_flow).length > 0 && (
                    <div className="pt-2">
                      <p className="text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-2">
                        By flow
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(genResult.by_flow).map(([flow, count]) => (
                          <Badge
                            key={flow}
                            className="bg-indigo-500/10 text-indigo-300 border border-indigo-500/30"
                          >
                            {flow}: {count}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardSection>
          </Card>
        </div>
      )}

      {/* ─── Preview tab ────────────────────────────────────────────────── */}
      {tab === "preview" && (
        <div className="grid grid-cols-1 gap-6">
          <Card>
            <CardHeader
              title={
                <span className="flex items-center gap-2">
                  <Eye className="w-4 h-4" />
                  Preview Digest
                </span>
              }
              subtitle="Render the next digest HTML without sending"
            />
            <CardSection className="p-4 space-y-4">
              <p className="text-sm text-zinc-400">
                Calls{" "}
                <code className="text-xs font-mono text-zinc-300">
                  GET /preview/&#123;email&#125;?period=...
                </code>{" "}
                and renders the HTML response in a modal. The backend enforces owner-or-admin
                authorization, so you can only preview your own digest unless you have the admin
                role.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto] gap-3 items-end">
                <div>
                  <label
                    htmlFor="preview-email"
                    className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                  >
                    Recipient email
                  </label>
                  <input
                    id="preview-email"
                    type="email"
                    value={prevEmail}
                    onChange={(e) => setPrevEmail(e.target.value)}
                    placeholder="user@example.com"
                    className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                    data-testid="preview-email"
                  />
                </div>
                <div>
                  <label
                    htmlFor="preview-period"
                    className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                  >
                    Period
                  </label>
                  <select
                    id="preview-period"
                    value={prevPeriod}
                    onChange={(e) => setPrevPeriod(e.target.value as "daily" | "weekly")}
                    className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                    data-testid="preview-period"
                  >
                    {PERIOD_OPTIONS.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>
                <Button
                  variant="primary"
                  onClick={handlePreview}
                  loading={prevLoading}
                  icon={Eye}
                  disabled={!prevEmail.trim()}
                  data-testid="preview-submit"
                >
                  {prevLoading ? "Loading…" : "Preview"}
                </Button>
              </div>

              {prevError && <ErrorBanner message={prevError} />}
            </CardSection>
          </Card>
        </div>
      )}

      {/* ─── Preview modal ──────────────────────────────────────────────── */}
      <Modal
        open={prevOpen}
        onClose={() => (prevLoading ? undefined : setPrevOpen(false))}
        title="Digest Preview"
        subtitle={prevEmail || undefined}
        size="xl"
      >
        <div className="p-2" data-testid="preview-modal">
          {prevHtml !== null ? (
            <iframe
              title="Digest HTML preview"
              srcDoc={prevHtml}
              className="w-full h-[70vh] rounded-md border border-zinc-700 bg-white"
              sandbox="allow-same-origin"
            />
          ) : (
            <LoadingRow label="Loading preview…" />
          )}
        </div>
      </Modal>
    </motion.div>
  );
}
