/**
 * Study Versions Page — Version-control UI for the study_versions backend module.
 *
 * Wires to all 4 endpoints exposed by api/study_versions.py
 * (prefix /api/v1/projects/{project_id}/studies/{study_id}/versions):
 *   GET  /                                  — list versions
 *   POST /                                  — create a new version snapshot
 *   POST /{version_id}/rollback             — roll study back to a version
 *   GET  /{v1}/compare/{v2}                 — compare two versions (diff)
 *
 * The page is operator-oriented: it lets an admin/engineer pick a target
 * study (project_id + study_id), browse its version history, create new
 * snapshots, roll back to a previous version, and compare two versions
 * side-by-side. All four endpoints share the same URL prefix; the page
 * gates all calls behind a single target-study form so an operator can't
 * fire a /rollback before choosing what they're rolling back.
 *
 * Ref: TASK-7
 */

import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  GitBranch,
  GitCompare,
  History,
  Loader2,
  RefreshCw,
  RotateCcw,
  Save,
  XCircle,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, CardHeader, CardSection, EmptyState, Tabs } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

// ---------------------------------------------------------------------------
// Types — mirror api/study_versions.py
// ---------------------------------------------------------------------------

interface VersionResponse {
  id: string;
  study_id: string;
  project_id: string;
  version_number: number;
  label: string | null;
  description: string | null;
  config_snapshot?: Record<string, unknown> | null;
  diff_summary?: string | null;
  created_by: string;
  created_at: string | null;
}

interface VersionListResponse {
  versions: VersionResponse[];
  total: number;
}

interface VersionCreateRequest {
  label?: string;
  description?: string;
}

interface RollbackResponse {
  message: string;
  version: number;
}

interface CompareResponse {
  version_a: VersionResponse;
  version_b: VersionResponse;
  config_diff: Record<string, { from: unknown; to: unknown }>;
  results_diff: Record<string, { from: unknown; to: unknown }> | null;
}

type TabId = "versions" | "create" | "compare";

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

async function studyFetch<T>(path: string, init?: RequestInit): Promise<T> {
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
    Object.assign(mergedHeaders, callerHeaders as Record<string, string>);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: mergedHeaders,
  });
  const text = await res.text().catch(() => "");
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = `${detail}: ${parsed.detail}`;
      else if (parsed?.message) detail = `${detail}: ${parsed.message}`;
      else if (parsed?.error) detail = `${detail}: ${parsed.error}`;
    } catch {
      if (text) detail = `${detail}: ${text.slice(0, 200)}`;
    }
    throw new Error(detail);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

// ---------------------------------------------------------------------------
// Small UI primitives (local — kept here to avoid bloating shared ui/)
// ---------------------------------------------------------------------------

function StatRow({ label, value }: { readonly label: string; readonly value: ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[var(--border-primary)] last:border-0 gap-3">
      <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold shrink-0">
        {label}
      </span>
      <span className="text-sm text-zinc-100 font-mono text-right break-all">{value}</span>
    </div>
  );
}

function ErrorBanner({ message }: { readonly message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300"
    >
      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
      <span className="break-words">{message}</span>
    </div>
  );
}

function LoadingRow({ label }: { readonly label: string }) {
  return (
    <div className="flex items-center gap-2 py-2 text-sm text-zinc-400">
      <Loader2 className="w-4 h-4 animate-spin" />
      <span>{label}</span>
    </div>
  );
}

/** Render a config/results diff value compactly. */
function DiffValue({ value }: { readonly value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-zinc-500 italic">∅</span>;
  }
  if (typeof value === "object") {
    return (
      <pre className="text-xs font-mono text-zinc-300 whitespace-pre-wrap break-all max-h-32 overflow-auto">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return <span className="text-xs font-mono text-zinc-200 break-all">{String(value)}</span>;
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function StudyVersionsPage() {
  const { notify } = useNotify();
  const [tab, setTab] = useState<TabId>("versions");

  // ─── Target study state (shared by all tabs) ─────────────────────────
  const [projectId, setProjectId] = useState("");
  const [studyId, setStudyId] = useState("");
  // `lockedProjectId` / `lockedStudyId` are the values actually used for
  // the most recent successful list call. We keep them separate so a user
  // can edit the inputs without auto-firing calls; the Load button commits
  // them. The Create/Compare tabs also use these locked values to ensure
  // they operate on the same study the user just listed versions for.
  const [lockedProjectId, setLockedProjectId] = useState("");
  const [lockedStudyId, setLockedStudyId] = useState("");

  // ─── Versions tab state ──────────────────────────────────────────────
  const [versions, setVersions] = useState<VersionResponse[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState<string | null>(null);

  // ─── Rollback state (Versions tab) ───────────────────────────────────
  const [rollbackId, setRollbackId] = useState<string | null>(null);
  const [rollbackResult, setRollbackResult] = useState<RollbackResponse | null>(null);
  const [rollbackError, setRollbackError] = useState<string | null>(null);

  // ─── Create tab state ────────────────────────────────────────────────
  const [createLabel, setCreateLabel] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createResult, setCreateResult] = useState<VersionResponse | null>(null);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // ─── Compare tab state ───────────────────────────────────────────────
  const [compareV1, setCompareV1] = useState("");
  const [compareV2, setCompareV2] = useState("");
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Derived helpers
  // -------------------------------------------------------------------------

  const versionsBasePath = useMemo(() => {
    if (!lockedProjectId || !lockedStudyId) return null;
    return `/api/v1/projects/${encodeURIComponent(lockedProjectId)}/studies/${encodeURIComponent(
      lockedStudyId,
    )}/versions`;
  }, [lockedProjectId, lockedStudyId]);

  // Versions list as <select> options (used by Compare tab)
  const versionSelectOptions = useMemo(
    () =>
      versions.map((v) => ({
        value: v.id,
        label: `v${v.version_number}${v.label ? ` — ${v.label}` : ""}`,
      })),
    [versions],
  );

  // -------------------------------------------------------------------------
  // Data loaders
  // -------------------------------------------------------------------------

  const loadVersions = useCallback(async () => {
    if (!versionsBasePath) return;
    setVersionsLoading(true);
    setVersionsError(null);
    try {
      const res = await studyFetch<VersionListResponse>(versionsBasePath);
      setVersions(res.versions ?? []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setVersionsError(msg);
      setVersions([]);
    } finally {
      setVersionsLoading(false);
    }
  }, [versionsBasePath]);

  // Auto-load versions whenever the locked target changes (i.e. after the
  // user clicks "Load Versions"). We intentionally depend on `versionsBasePath`
  // (a memoised string) so we don't refetch on every keystroke in the inputs.
  useEffect(() => {
    if (versionsBasePath && tab === "versions") loadVersions();
  }, [versionsBasePath, tab, loadVersions]);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const handleLoadVersions = useCallback(() => {
    const p = projectId.trim();
    const s = studyId.trim();
    if (!p || !s) {
      setVersionsError("Both Project ID and Study ID are required.");
      return;
    }
    // Commit the inputs to the locked values. This triggers the
    // versionsBasePath memo and the auto-load effect above.
    setLockedProjectId(p);
    setLockedStudyId(s);
    setRollbackResult(null);
    setRollbackError(null);
    setVersionsError(null);
    setCompareResult(null);
    setCompareError(null);
  }, [projectId, studyId]);

  const handleRollback = useCallback(
    async (version: VersionResponse) => {
      if (!versionsBasePath) return;
      setRollbackId(version.id);
      setRollbackError(null);
      setRollbackResult(null);
      try {
        const res = await studyFetch<RollbackResponse>(
          `${versionsBasePath}/${encodeURIComponent(version.id)}/rollback`,
          { method: "POST" },
        );
        setRollbackResult(res);
        notify("success", res.message || `Rolled back to version ${version.version_number}.`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setRollbackError(msg);
        notify("error", `Rollback failed: ${msg}`);
      } finally {
        setRollbackId(null);
      }
    },
    [versionsBasePath, notify],
  );

  const handleCreate = useCallback(async () => {
    if (!versionsBasePath) {
      setCreateError("Load a study first (Project ID + Study ID) on the Versions tab.");
      return;
    }
    setCreateLoading(true);
    setCreateError(null);
    setCreateResult(null);
    try {
      const body: VersionCreateRequest = {};
      if (createLabel.trim()) body.label = createLabel.trim();
      if (createDescription.trim()) body.description = createDescription.trim();
      const res = await studyFetch<VersionResponse>(versionsBasePath, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setCreateResult(res);
      notify(
        "success",
        `Snapshot created: v${res.version_number}${res.label ? ` — ${res.label}` : ""}.`,
      );
      // Refresh the versions list so the new snapshot shows up immediately
      // when the user switches back to the Versions tab.
      void loadVersions();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setCreateError(msg);
      notify("error", `Create snapshot failed: ${msg}`);
    } finally {
      setCreateLoading(false);
    }
  }, [versionsBasePath, createLabel, createDescription, notify, loadVersions]);

  const handleCompare = useCallback(async () => {
    if (!versionsBasePath) {
      setCompareError("Load a study first (Project ID + Study ID) on the Versions tab.");
      return;
    }
    if (!compareV1 || !compareV2) {
      setCompareError("Pick two versions to compare.");
      return;
    }
    if (compareV1 === compareV2) {
      setCompareError("Pick two different versions.");
      return;
    }
    setCompareLoading(true);
    setCompareError(null);
    setCompareResult(null);
    try {
      const res = await studyFetch<CompareResponse>(
        `${versionsBasePath}/${encodeURIComponent(compareV1)}/compare/${encodeURIComponent(compareV2)}`,
        { method: "GET" },
      );
      setCompareResult(res);
      notify("success", "Comparison loaded.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setCompareError(msg);
      notify("error", `Compare failed: ${msg}`);
    } finally {
      setCompareLoading(false);
    }
  }, [versionsBasePath, compareV1, compareV2, notify]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const tabs = [
    {
      id: "versions",
      label: "Versions",
      icon: <History className="w-4 h-4" />,
    },
    {
      id: "create",
      label: "Create Snapshot",
      icon: <Save className="w-4 h-4" />,
    },
    {
      id: "compare",
      label: "Compare",
      icon: <GitCompare className="w-4 h-4" />,
    },
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
            <GitBranch className="w-6 h-6 text-brand-500" />
            Study Versions
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Version control for studies — browse snapshots, create new ones, roll back to a previous
            state, and compare two versions side-by-side.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void loadVersions();
          }}
          icon={RefreshCw}
          disabled={!versionsBasePath || versionsLoading}
        >
          Refresh
        </Button>
      </div>

      {/* ─── Target study form ──────────────────────────────────────────── */}
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <GitBranch className="w-4 h-4" />
              Target Study
            </span>
          }
          subtitle="All endpoints operate on this study — pick it once, then use the tabs below."
        />
        <CardSection className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
            <div>
              <label
                htmlFor="sv-project-id"
                className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
              >
                Project ID
              </label>
              <input
                id="sv-project-id"
                type="text"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                placeholder="e.g. proj-001"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                data-testid="sv-project-id"
              />
            </div>
            <div>
              <label
                htmlFor="sv-study-id"
                className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
              >
                Study ID
              </label>
              <input
                id="sv-study-id"
                type="text"
                value={studyId}
                onChange={(e) => setStudyId(e.target.value)}
                placeholder="e.g. study-001"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                data-testid="sv-study-id"
              />
            </div>
            <Button
              variant="primary"
              onClick={handleLoadVersions}
              loading={versionsLoading}
              icon={History}
              disabled={!projectId.trim() || !studyId.trim()}
              data-testid="sv-load-btn"
            >
              Load Versions
            </Button>
          </div>
          {lockedProjectId && lockedStudyId && (
            <p className="mt-3 text-xs text-zinc-400" data-testid="sv-target-summary">
              Target: project <code className="font-mono text-zinc-300">{lockedProjectId}</code> /
              study <code className="font-mono text-zinc-300">{lockedStudyId}</code>
            </p>
          )}
        </CardSection>
      </Card>

      <Tabs tabs={tabs} activeTab={tab} onChange={(id) => setTab(id as TabId)} />

      {/* ─── Versions tab ───────────────────────────────────────────────── */}
      {tab === "versions" && (
        <Card>
          <CardHeader
            title={
              <span className="flex items-center gap-2">
                <History className="w-4 h-4" />
                Version History
              </span>
            }
            subtitle={
              versionsBasePath
                ? "Snapshots ordered newest-first"
                : "Load a study to see its history"
            }
          />
          <CardSection className="p-4">
            {!versionsBasePath && (
              <EmptyState
                icon={<History className="w-8 h-8" />}
                title="No target study selected"
                description="Enter a Project ID and Study ID above, then click Load Versions."
              />
            )}
            {versionsBasePath && versionsLoading && <LoadingRow label="Loading versions…" />}
            {versionsBasePath && !versionsLoading && versionsError && (
              <ErrorBanner message={versionsError} />
            )}
            {versionsBasePath && !versionsLoading && !versionsError && versions.length === 0 && (
              <EmptyState
                icon={<History className="w-8 h-8" />}
                title="No versions yet"
                description="Create a snapshot from the Create Snapshot tab."
              />
            )}
            {versionsBasePath && !versionsLoading && !versionsError && versions.length > 0 && (
              <div data-testid="sv-versions-table" className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-zinc-400 border-b border-[var(--border-primary)]">
                      <th className="py-2 pr-3 font-semibold">Ver</th>
                      <th className="py-2 pr-3 font-semibold">Label</th>
                      <th className="py-2 pr-3 font-semibold">Description</th>
                      <th className="py-2 pr-3 font-semibold">Created by</th>
                      <th className="py-2 pr-3 font-semibold">Created at</th>
                      <th className="py-2 pr-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versions.map((v) => (
                      <tr
                        key={v.id}
                        className="border-b border-[var(--border-primary)] last:border-0 hover:bg-zinc-900/40"
                        data-testid={`sv-version-row-${v.id}`}
                      >
                        <td className="py-2 pr-3">
                          <Badge
                            className="bg-indigo-500/10 text-indigo-300 border border-indigo-500/30"
                            data-testid={`sv-version-number-${v.id}`}
                          >
                            v{v.version_number}
                          </Badge>
                        </td>
                        <td className="py-2 pr-3 text-zinc-200">{v.label ?? "—"}</td>
                        <td
                          className="py-2 pr-3 text-zinc-400 max-w-md truncate"
                          title={v.description ?? ""}
                        >
                          {v.description ?? "—"}
                        </td>
                        <td className="py-2 pr-3 text-zinc-400 font-mono text-xs">
                          {v.created_by || "—"}
                        </td>
                        <td className="py-2 pr-3 text-zinc-400 font-mono text-xs">
                          {v.created_at ?? "—"}
                        </td>
                        <td className="py-2 pr-3 text-right">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleRollback(v)}
                            loading={rollbackId === v.id}
                            icon={RotateCcw}
                            data-testid={`sv-rollback-btn-${v.id}`}
                          >
                            Rollback
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Rollback result block */}
            {rollbackResult && (
              <div
                data-testid="sv-rollback-result"
                className="mt-4 rounded-md border border-green-500/30 bg-green-500/10 p-3 space-y-2"
              >
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                  <span className="text-sm font-semibold text-zinc-200">Rollback successful</span>
                </div>
                <StatRow label="Message" value={rollbackResult.message} />
                <StatRow label="Version" value={`v${rollbackResult.version}`} />
              </div>
            )}
            {rollbackError && (
              <div className="mt-4">
                <ErrorBanner message={rollbackError} />
              </div>
            )}
          </CardSection>
        </Card>
      )}

      {/* ─── Create tab ─────────────────────────────────────────────────── */}
      {tab === "create" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Form card */}
          <Card>
            <CardHeader
              title={
                <span className="flex items-center gap-2">
                  <Save className="w-4 h-4" />
                  Create Snapshot
                </span>
              }
              subtitle="Save the current study config + results as a new version"
            />
            <CardSection className="p-4 space-y-4">
              {!versionsBasePath && (
                <p className="text-xs text-amber-300">
                  Tip: load a study on the Versions tab first. The snapshot will be created for{" "}
                  <code className="font-mono">{projectId || "<project_id>"}</code> /{" "}
                  <code className="font-mono">{studyId || "<study_id>"}</code>.
                </p>
              )}
              <div>
                <label
                  htmlFor="create-label"
                  className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                >
                  Label (optional, max 255)
                </label>
                <input
                  id="create-label"
                  type="text"
                  maxLength={255}
                  value={createLabel}
                  onChange={(e) => setCreateLabel(e.target.value)}
                  placeholder="e.g. Pre-deploy baseline"
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  data-testid="sv-create-label"
                />
              </div>
              <div>
                <label
                  htmlFor="create-description"
                  className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                >
                  Description (optional, max 2000)
                </label>
                <textarea
                  id="create-description"
                  maxLength={2000}
                  rows={4}
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                  placeholder="What changed in this version?"
                  className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  data-testid="sv-create-description"
                />
              </div>
              {createError && <ErrorBanner message={createError} />}
              <div className="flex justify-end">
                <Button
                  variant="primary"
                  onClick={handleCreate}
                  loading={createLoading}
                  icon={Save}
                  disabled={!versionsBasePath}
                  data-testid="sv-create-submit"
                >
                  {createLoading ? "Saving…" : "Create Snapshot"}
                </Button>
              </div>
            </CardSection>
          </Card>

          {/* Result card */}
          <Card>
            <CardHeader title="Created Version" subtitle="Backend response from POST /versions" />
            <CardSection className="p-4">
              {!createResult && !createLoading && (
                <EmptyState
                  icon={<Save className="w-8 h-8" />}
                  title="No snapshot created yet"
                  description="Fill the form and click Create Snapshot to see the new version here."
                />
              )}
              {createLoading && <LoadingRow label="Creating snapshot…" />}
              {createResult && (
                <div data-testid="sv-create-result" className="space-y-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-400" />
                    <span className="text-sm font-semibold text-zinc-200">Snapshot created</span>
                    <Badge
                      className="bg-indigo-500/10 text-indigo-300 border border-indigo-500/30"
                      data-testid="sv-create-version-number"
                    >
                      v{createResult.version_number}
                    </Badge>
                  </div>
                  <StatRow label="ID" value={createResult.id} />
                  <StatRow label="Label" value={createResult.label ?? "—"} />
                  <StatRow label="Description" value={createResult.description ?? "—"} />
                  <StatRow label="Created by" value={createResult.created_by || "—"} />
                  <StatRow label="Created at" value={createResult.created_at ?? "—"} />
                </div>
              )}
            </CardSection>
          </Card>
        </div>
      )}

      {/* ─── Compare tab ────────────────────────────────────────────────── */}
      {tab === "compare" && (
        <div className="grid grid-cols-1 gap-6">
          <Card>
            <CardHeader
              title={
                <span className="flex items-center gap-2">
                  <GitCompare className="w-4 h-4" />
                  Compare Two Versions
                </span>
              }
              subtitle="Side-by-side diff of config_snapshot and results_snapshot"
            />
            <CardSection className="p-4 space-y-4">
              {!versionsBasePath && (
                <p className="text-xs text-amber-300">
                  Load a study on the Versions tab first — the version dropdowns below populate from
                  that study's history.
                </p>
              )}
              {versionsBasePath && versions.length < 2 && (
                <p className="text-xs text-amber-300">
                  Only {versions.length} version(s) loaded — you need at least two to compare. Load
                  more versions or create a new snapshot first.
                </p>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
                <div>
                  <label
                    htmlFor="compare-v1"
                    className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                  >
                    Version A
                  </label>
                  <select
                    id="compare-v1"
                    value={compareV1}
                    onChange={(e) => setCompareV1(e.target.value)}
                    className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                    data-testid="sv-compare-v1"
                  >
                    <option value="">— pick version A —</option>
                    {versionSelectOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="compare-v2"
                    className="block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1"
                  >
                    Version B
                  </label>
                  <select
                    id="compare-v2"
                    value={compareV2}
                    onChange={(e) => setCompareV2(e.target.value)}
                    className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                    data-testid="sv-compare-v2"
                  >
                    <option value="">— pick version B —</option>
                    {versionSelectOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <Button
                  variant="primary"
                  onClick={handleCompare}
                  loading={compareLoading}
                  icon={GitCompare}
                  disabled={!versionsBasePath || !compareV1 || !compareV2}
                  data-testid="sv-compare-submit"
                >
                  {compareLoading ? "Comparing…" : "Compare"}
                </Button>
              </div>
              {compareError && <ErrorBanner message={compareError} />}
            </CardSection>
          </Card>

          {compareResult && (
            <div data-testid="sv-compare-result" className="grid grid-cols-1 gap-6">
              {/* Side-by-side metadata */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                  <CardHeader
                    title={
                      <span className="flex items-center gap-2">
                        <Badge className="bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
                          A
                        </Badge>
                        v{compareResult.version_a.version_number}
                      </span>
                    }
                    subtitle={compareResult.version_a.label ?? "No label"}
                  />
                  <CardSection className="p-4">
                    <StatRow label="ID" value={compareResult.version_a.id} />
                    <StatRow
                      label="Description"
                      value={compareResult.version_a.description ?? "—"}
                    />
                    <StatRow label="Created by" value={compareResult.version_a.created_by || "—"} />
                    <StatRow label="Created at" value={compareResult.version_a.created_at ?? "—"} />
                  </CardSection>
                </Card>
                <Card>
                  <CardHeader
                    title={
                      <span className="flex items-center gap-2">
                        <Badge className="bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                          B
                        </Badge>
                        v{compareResult.version_b.version_number}
                      </span>
                    }
                    subtitle={compareResult.version_b.label ?? "No label"}
                  />
                  <CardSection className="p-4">
                    <StatRow label="ID" value={compareResult.version_b.id} />
                    <StatRow
                      label="Description"
                      value={compareResult.version_b.description ?? "—"}
                    />
                    <StatRow label="Created by" value={compareResult.version_b.created_by || "—"} />
                    <StatRow label="Created at" value={compareResult.version_b.created_at ?? "—"} />
                  </CardSection>
                </Card>
              </div>

              {/* Config diff */}
              <Card>
                <CardHeader
                  title="Config Diff"
                  subtitle={
                    Object.keys(compareResult.config_diff).length === 0
                      ? "No differences"
                      : `${Object.keys(compareResult.config_diff).length} changed key(s)`
                  }
                />
                <CardSection className="p-4">
                  {Object.keys(compareResult.config_diff).length === 0 ? (
                    <EmptyState
                      icon={<CheckCircle2 className="w-8 h-8" />}
                      title="Config identical"
                      description="Both versions have the same config_snapshot."
                    />
                  ) : (
                    <div className="overflow-x-auto" data-testid="sv-config-diff">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs uppercase tracking-wider text-zinc-400 border-b border-[var(--border-primary)]">
                            <th className="py-2 pr-3 font-semibold">Key</th>
                            <th className="py-2 pr-3 font-semibold">From (A)</th>
                            <th className="py-2 pr-3 font-semibold">To (B)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(compareResult.config_diff).map(([key, diff]) => (
                            <tr
                              key={key}
                              className="border-b border-[var(--border-primary)] last:border-0"
                              data-testid={`sv-config-diff-row-${key}`}
                            >
                              <td className="py-2 pr-3 font-mono text-xs text-zinc-200 align-top">
                                {key}
                              </td>
                              <td className="py-2 pr-3 align-top">
                                <DiffValue value={diff.from} />
                              </td>
                              <td className="py-2 pr-3 align-top">
                                <DiffValue value={diff.to} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardSection>
              </Card>

              {/* Results diff */}
              {compareResult.results_diff && (
                <Card>
                  <CardHeader
                    title="Results Diff"
                    subtitle={
                      Object.keys(compareResult.results_diff).length === 0
                        ? "No differences"
                        : `${Object.keys(compareResult.results_diff).length} changed key(s)`
                    }
                  />
                  <CardSection className="p-4">
                    {Object.keys(compareResult.results_diff).length === 0 ? (
                      <EmptyState
                        icon={<CheckCircle2 className="w-8 h-8" />}
                        title="Results identical"
                        description="Both versions have the same results_snapshot."
                      />
                    ) : (
                      <div className="overflow-x-auto" data-testid="sv-results-diff">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-xs uppercase tracking-wider text-zinc-400 border-b border-[var(--border-primary)]">
                              <th className="py-2 pr-3 font-semibold">Key</th>
                              <th className="py-2 pr-3 font-semibold">From (A)</th>
                              <th className="py-2 pr-3 font-semibold">To (B)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(compareResult.results_diff).map(([key, diff]) => (
                              <tr
                                key={key}
                                className="border-b border-[var(--border-primary)] last:border-0"
                                data-testid={`sv-results-diff-row-${key}`}
                              >
                                <td className="py-2 pr-3 font-mono text-xs text-zinc-200 align-top">
                                  {key}
                                </td>
                                <td className="py-2 pr-3 align-top">
                                  <DiffValue value={diff.from} />
                                </td>
                                <td className="py-2 pr-3 align-top">
                                  <DiffValue value={diff.to} />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardSection>
                </Card>
              )}

              {/* No results diff block */}
              {!compareResult.results_diff && (
                <Card>
                  <CardHeader title="Results Diff" subtitle="Not available" />
                  <CardSection className="p-4">
                    <EmptyState
                      icon={<XCircle className="w-8 h-8" />}
                      title="No results snapshot"
                      description="Version A or B has no results_snapshot — results diff skipped."
                    />
                  </CardSection>
                </Card>
              )}
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
