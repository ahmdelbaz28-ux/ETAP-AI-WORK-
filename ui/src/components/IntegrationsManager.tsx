import { motion } from "framer-motion";
import { AlertTriangle, Cable, CheckCircle2, RefreshCw, XCircle, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Button, Card, CardHeader } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn } from "../utils/helpers";

// ─── Types ───────────────────────────────────────────────────────────

interface PluginStatus {
  name: string;
  type: "autocad" | "revit";
  status: "connected" | "disconnected" | "error";
  version: string;
  last_heartbeat: string;
  timeout_seconds: number;
}

interface AutodeskStatus {
  plugins: PluginStatus[];
  pipe_connected: boolean;
  server_version: string;
}

const DEFAULT_TIMEOUTS = {
  autocad: 30,
  revit: 30,
};

// ─── Component ───────────────────────────────────────────────────────

export default function IntegrationsManager() {
  const { notify } = useNotify();
  const [status, setStatus] = useState<AutodeskStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [timeouts, setTimeouts] = useState(DEFAULT_TIMEOUTS);

  // Fetch Autodesk connector status
  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/connectors/autodesk/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      const fetched: AutodeskStatus = {
        plugins: Array.isArray(data.plugins)
          ? data.plugins.map((p: Record<string, unknown>) => ({
              name: String(p.name ?? "Unknown"),
              type: (p.type as "autocad" | "revit") ?? "autocad",
              status: (p.status as "connected" | "disconnected" | "error") ?? "disconnected",
              version: String(p.version ?? "—"),
              last_heartbeat: String(p.last_heartbeat ?? "—"),
              timeout_seconds: Number(p.timeout_seconds ?? 30),
            }))
          : [],
        pipe_connected: Boolean(data.pipe_connected ?? false),
        server_version: String(data.server_version ?? "—"),
      };
      setStatus(fetched);

      // Update timeouts from fetched data
      const autocadPlugin = fetched.plugins.find((p) => p.type === "autocad");
      const revitPlugin = fetched.plugins.find((p) => p.type === "revit");
      setTimeouts({
        autocad: autocadPlugin?.timeout_seconds ?? DEFAULT_TIMEOUTS.autocad,
        revit: revitPlugin?.timeout_seconds ?? DEFAULT_TIMEOUTS.revit,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Test pipe connection
  const handleTestConnection = async () => {
    setTesting(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/connectors/autodesk/test-connection`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          autocad_timeout: timeouts.autocad,
          revit_timeout: timeouts.revit,
        }),
        signal: AbortSignal.timeout(Math.max(timeouts.autocad, timeouts.revit) * 1000 + 5000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      notify("success", data.message ?? "Pipe connection test successful");
      fetchStatus();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Pipe connection test failed: ${msg}`);
    } finally {
      setTesting(false);
    }
  };

  // ─── Loading state ────────────────────────────────────────────────
  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading connector status…</span>
        </div>
      </div>
    );
  }

  // ─── Error state ──────────────────────────────────────────────────
  if (error && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] mb-2">
            Failed to load connector status
          </p>
          <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{error}</p>
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={fetchStatus}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const plugins = status?.plugins ?? [];
  const autocadPlugin = plugins.find((p) => p.type === "autocad");
  const revitPlugin = plugins.find((p) => p.type === "revit");

  const statusConfig = {
    connected: {
      variant: "success" as const,
      icon: <CheckCircle2 className="w-4 h-4" />,
      label: "Connected",
    },
    disconnected: {
      variant: "default" as const,
      icon: <XCircle className="w-4 h-4" />,
      label: "Disconnected",
    },
    error: {
      variant: "danger" as const,
      icon: <AlertTriangle className="w-4 h-4" />,
      label: "Error",
    },
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Cable className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Integrations</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">
                Autodesk connector health & pipe management
              </p>
              <ContextHelpButton contextId="integrations.autodesk" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={RefreshCw}
            onClick={fetchStatus}
            loading={loading}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={Zap}
            loading={testing}
            onClick={handleTestConnection}
          >
            Test Pipe Connection
          </Button>
        </div>
      </motion.div>

      {/* Pipe status banner */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div
          className={cn(
            "flex items-center justify-between p-4 rounded-xl border",
            status?.pipe_connected
              ? "bg-green-500/5 border-green-500/20"
              : "bg-red-500/5 border-red-500/20",
          )}
        >
          <div className="flex items-center gap-3">
            {status?.pipe_connected ? (
              <CheckCircle2 className="w-5 h-5 text-green-400" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400" />
            )}
            <div>
              <p className="text-sm font-medium text-[var(--text-primary)]">
                Pipe Connection {status?.pipe_connected ? "Active" : "Inactive"}
              </p>
              <p className="text-xs text-[var(--text-muted)]">
                Server version: {status?.server_version ?? "—"}
              </p>
            </div>
          </div>
          <Badge variant={status?.pipe_connected ? "success" : "danger"} dot size="md">
            {status?.pipe_connected ? "Online" : "Offline"}
          </Badge>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AutoCAD Plugin Card */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card padding="md">
            <CardHeader
              title="AutoCAD Plugin"
              subtitle="ETAP-AI AutoCAD integration"
              icon={<Cable className="w-4 h-4" />}
            />
            <div className="space-y-4">
              {/* Status badge */}
              <div className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                <div className="flex items-center gap-2.5">
                  {autocadPlugin ? (
                    statusConfig[autocadPlugin.status].icon
                  ) : (
                    <XCircle className="w-4 h-4" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      Connection Status
                    </p>
                    <p className="text-xs text-[var(--text-muted)]">
                      Last heartbeat: {autocadPlugin?.last_heartbeat ?? "—"}
                    </p>
                  </div>
                </div>
                <Badge
                  variant={autocadPlugin ? statusConfig[autocadPlugin.status].variant : "default"}
                  dot
                  size="sm"
                >
                  {autocadPlugin ? statusConfig[autocadPlugin.status].label : "Unknown"}
                </Badge>
              </div>

              {/* Plugin info */}
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--text-tertiary)]">Version</span>
                  <span className="text-[var(--text-primary)] font-mono">
                    {autocadPlugin?.version ?? "—"}
                  </span>
                </div>
              </div>

              {/* Timeout input */}
              <div>
                <label
                  htmlFor="autocad-timeout"
                  className="block text-sm font-medium text-[var(--text-secondary)] mb-2"
                >
                  Connection Timeout (seconds)
                </label>
                <input
                  id="autocad-timeout"
                  type="number"
                  min={5}
                  max={120}
                  step={5}
                  value={timeouts.autocad}
                  onChange={(e) => {
                    const val = Math.min(120, Math.max(5, Number(e.target.value) || 30));
                    setTimeouts({ ...timeouts, autocad: val });
                  }}
                  className="w-28 px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                />
                <p className="text-xs text-[var(--text-muted)] mt-1">Range: 5 – 120 seconds</p>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Revit Plugin Card */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card padding="md">
            <CardHeader
              title="Revit Plugin"
              subtitle="ETAP-AI Revit integration"
              icon={<Cable className="w-4 h-4" />}
            />
            <div className="space-y-4">
              {/* Status badge */}
              <div className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                <div className="flex items-center gap-2.5">
                  {revitPlugin ? (
                    statusConfig[revitPlugin.status].icon
                  ) : (
                    <XCircle className="w-4 h-4" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      Connection Status
                    </p>
                    <p className="text-xs text-[var(--text-muted)]">
                      Last heartbeat: {revitPlugin?.last_heartbeat ?? "—"}
                    </p>
                  </div>
                </div>
                <Badge
                  variant={revitPlugin ? statusConfig[revitPlugin.status].variant : "default"}
                  dot
                  size="sm"
                >
                  {revitPlugin ? statusConfig[revitPlugin.status].label : "Unknown"}
                </Badge>
              </div>

              {/* Plugin info */}
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--text-tertiary)]">Version</span>
                  <span className="text-[var(--text-primary)] font-mono">
                    {revitPlugin?.version ?? "—"}
                  </span>
                </div>
              </div>

              {/* Timeout input */}
              <div>
                <label
                  htmlFor="revit-timeout"
                  className="block text-sm font-medium text-[var(--text-secondary)] mb-2"
                >
                  Connection Timeout (seconds)
                </label>
                <input
                  id="revit-timeout"
                  type="number"
                  min={5}
                  max={120}
                  step={5}
                  value={timeouts.revit}
                  onChange={(e) => {
                    const val = Math.min(120, Math.max(5, Number(e.target.value) || 30));
                    setTimeouts({ ...timeouts, revit: val });
                  }}
                  className="w-28 px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                />
                <p className="text-xs text-[var(--text-muted)] mt-1">Range: 5 – 120 seconds</p>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
