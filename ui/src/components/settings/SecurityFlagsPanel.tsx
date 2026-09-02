/**
 * SecurityFlagsPanel (P7d — Security & Feature Flags)
 * ===================================================
 * Settings tab panel that surfaces the BACKEND-AUTHORITATIVE feature flag
 * registry (GET /api/v1/feature-flags) and allows admin mutation through the
 * existing backend endpoint (PATCH /api/v1/feature-flags/{key}).
 *
 * SECURITY DESIGN (P7d):
 *   - Backend is the single source of truth. The UI never invents flag names,
 *     never authorizes, and never keeps optimistic client-side state: every
 *     toggle applies the value returned by the backend response.
 *   - Authorization is enforced server-side (RBAC `feature_flags:read` /
 *     `feature_flags:write`; API-key fallback). Unauthorized mutations fail
 *     on the backend and the error is surfaced via notify.
 *   - The displayed `effective_enabled` is the backend's evaluation of the
 *     current ENV (dev/test override semantics included) — the UI must not
 *     pretend a runtime value is permanent.
 *   - Dangerous flags fail closed: all backend defaults are disabled and
 *     unknown flag names are rejected with 404 by the backend.
 *   - `chat_first_ui` rollout (P10) is backend-controlled; it only appears
 *     here if the backend registry exposes it. The UI never activates it.
 *   - No secrets pass through this panel: flag payloads contain booleans and
 *     metadata only. Nothing is written to localStorage / sessionStorage.
 */

import { Info, Loader2, RefreshCw, Shield } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { type FeatureFlag, fetchFeatureFlags, patchFeatureFlag } from "../../lib/api";
import { Button, Card, CardHeader, Toggle } from "../ui";

type NotifyType = "success" | "error" | "info" | "warning";

interface SecurityFlagsPanelProps {
  readonly notify: (type: NotifyType, message: string) => void;
}

function statusBadgeClass(status: string): string {
  if (status === "internal") return "bg-amber-500/15 text-amber-400";

  if (status === "alpha") return "bg-red-500/15 text-red-400";
  if (status === "beta") return "bg-blue-500/15 text-blue-400";
  return "bg-[var(--bg-primary)] text-[var(--text-muted)]";
}

export function SecurityFlagsPanel({ notify }: SecurityFlagsPanelProps) {
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [env, setEnv] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetchFeatureFlags();
      if (resp?.success) {
        setFlags(resp.data);
        setEnv(resp.env);
      } else {
        notify("error", "Feature flags response rejected by client contract");
      }
    } catch (err) {
      notify(
        "error",
        `Failed to load feature flags: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    load();
  }, [load]);

  // Backend-authoritative toggle: the resulting state is taken from the
  // backend response (never from the clicked intent). On failure the row
  // keeps the backend's last known truth.
  const handleToggle = useCallback(
    async (flag: FeatureFlag) => {
      setToggling(flag.key);
      try {
        const resp = await patchFeatureFlag(flag.key, !flag.enabled);
        setFlags((prev) => prev.map((f) => (f.key === flag.key ? { ...f, ...resp.data } : f)));
        setEnv(resp.data.env || env);
        const isDev = /^(dev|test|development)$/.test(resp.data.env ?? "");
        notify(
          "success",
          `Flag '${flag.key}' ${resp.data.enabled ? "enabled" : "disabled"}${
            isDev ? " (dev override: effective ON)" : ""
          }`,
        );
      } catch (err) {
        notify(
          "error",
          `Failed to toggle flag '${flag.key}': ${err instanceof Error ? err.message : "Unknown error"}`,
        );
      } finally {
        setToggling(null);
      }
    },
    [notify, env],
  );

  return (
    <div className="space-y-6" data-testid="security-flags-panel">
      <Card padding="md">
        <CardHeader
          title="Security & Feature Flags"
          subtitle={`${flags.length} flag${flags.length === 1 ? "" : "s"} · backend registry`}
          icon={<Shield className="w-5 h-5 text-brand-400" />}
        />
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <Info className="w-3.5 h-3.5" />
            <span>
              Backend-authoritative. Toggles call{' '}
              <code className="mx-1 rounded bg-[var(--bg-primary)] px-1 py-0.5">
                PATCH /api/v1/feature-flags/&#123;key&#125;
              </code>{' '}
              (admin only, audited). Effective state honours the deployment environment — in
              dev/test the backend forces flags effectively ON.
            </span>
          </div>
          <div className="flex items-center gap-2">
            {env ? (
              <span
                className="rounded-full bg-[var(--bg-primary)] px-2 py-0.5 text-xs font-semibold text-[var(--text-muted)]"
                data-testid="feature-flags-env"
              >
                env: {env}
              </span>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              onClick={load}
              disabled={loading}
              data-testid="feature-flags-refresh"
            >
              {loading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              Refresh
            </Button>
          </div>
        </div>
      </Card>

      {loading ? (
        <Card padding="md">
          <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading feature flags from backend…
          </div>
        </Card>
      ) : (
        flags.map((flag) => {
          const isToggling = toggling === flag.key;
          return (
            <Card key={flag.key} padding="md" data-testid={`flag-row-${flag.key}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className="font-mono text-sm font-semibold"
                      data-testid={`flag-key-${flag.key}`}
                    >
                      {flag.key}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${statusBadgeClass(flag.status)}`}
                    >
                      {flag.status}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                        flag.effective_enabled
                          ? "bg-green-500/15 text-green-400"
                          : "bg-red-500/15 text-red-400"
                      }`}
                      data-testid={`flag-effective-${flag.key}`}
                    >
                      effective: {flag.effective_enabled ? "ON" : "OFF"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--text-muted)]">{flag.description}</p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {isToggling ? (
                    <Loader2 className="w-4 h-4 animate-spin text-[var(--text-muted)]" />
                  ) : null}
                  <Toggle
                    checked={flag.enabled}
                    onChange={() => handleToggle(flag)}
                    disabled={isToggling}
                    label={`Toggle ${flag.key}`}
                    size="sm"
                  />
                </div>
              </div>
            </Card>
          );
        })
      )}

      {!loading && flags.length === 0 ? (
        <Card padding="md">
          <div className="text-sm text-[var(--text-muted)]" data-testid="feature-flags-empty">
            No feature flags reported by the backend registry.
          </div>
        </Card>
      ) : null}
    </div>
  );
}

export default SecurityFlagsPanel;
