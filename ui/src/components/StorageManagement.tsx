import { motion } from "framer-motion";
import { AlertTriangle, Database, HardDrive, RefreshCw, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, CardHeader, Modal } from "../components/ui";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn, formatDuration } from "../utils/helpers";

// ─── Types ───────────────────────────────────────────────────────────

interface StorageMetrics {
  total_size_bytes: number;
  object_count: number;
  categories: {
    name: string;
    size_bytes: number;
    count: number;
    retention_days: number;
  }[];
  retention_policy: {
    default_days: number;
    temp_artifacts_days: number;
    audit_logs_days: number;
  };
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

// ─── Component ───────────────────────────────────────────────────────

export default function StorageManagement() {
  const { notify } = useNotify();
  const [metrics, setMetrics] = useState<StorageMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [purging, setPurging] = useState(false);
  const [showPurgeModal, setShowPurgeModal] = useState(false);
  const [backingUp, setBackingUp] = useState(false);

  // Fetch storage metrics
  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/storage/metrics`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      setMetrics({
        total_size_bytes: data.total_size_bytes ?? 0,
        object_count: data.object_count ?? 0,
        categories: Array.isArray(data.categories)
          ? data.categories.map((c: Record<string, unknown>) => ({
              name: String(c.name ?? "Unknown"),
              size_bytes: Number(c.size_bytes ?? 0),
              count: Number(c.count ?? 0),
              retention_days: Number(c.retention_days ?? 30),
            }))
          : [],
        retention_policy: {
          default_days: data.retention_policy?.default_days ?? 90,
          temp_artifacts_days: data.retention_policy?.temp_artifacts_days ?? 7,
          audit_logs_days: data.retention_policy?.audit_logs_days ?? 365,
        },
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // Purge temporary CAD artifacts
  const handlePurge = async () => {
    setPurging(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/storage/purge`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ category: "temp_cad_artifacts" }),
        signal: AbortSignal.timeout(15000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      notify("success", "Temporary CAD artifacts purged successfully");
      setShowPurgeModal(false);
      fetchMetrics();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to purge artifacts: ${msg}`);
    } finally {
      setPurging(false);
    }
  };

  const handleManualBackup = async () => {
    setBackingUp(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/storage/retention`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ trigger_backup: true }),
        signal: AbortSignal.timeout(30000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      notify("success", "Manual backup triggered successfully");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to trigger backup: ${msg}`);
    } finally {
      setBackingUp(false);
    }
  };

  // ─── Loading state ────────────────────────────────────────────────
  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading storage metrics…</span>
        </div>
      </div>
    );
  }

  // ─── Error state ──────────────────────────────────────────────────
  if (error && !metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] mb-2">Failed to load storage metrics</p>
          <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{error}</p>
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={fetchMetrics}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const totalSize = metrics?.total_size_bytes ?? 0;
  const objectCount = metrics?.object_count ?? 0;
  const categories = metrics?.categories ?? [];
  const retention = metrics?.retention_policy;

  // Find the temp CAD category for the purge button
  const tempCadCategory = categories.find((c) => c.name.toLowerCase().includes("temp") || c.name.toLowerCase().includes("cad"));

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
            <Database className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Storage Management</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Object storage usage & retention policies</p>
              <ContextHelpButton contextId="storage.management" />
            </div>
          </div>
        </div>
        <Button variant="secondary" size="sm" icon={RefreshCw} onClick={fetchMetrics} loading={loading}>
          Refresh
        </Button>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Overview stats */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card padding="md">
            <CardHeader
              title="Storage Overview"
              subtitle="Total usage & object count"
              icon={<HardDrive className="w-4 h-4" />}
            />
            <div className="space-y-4">
              <div className="text-center p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                <p className="text-3xl font-bold text-[var(--text-primary)] mono-engineering">
                  {formatBytes(totalSize)}
                </p>
                <p className="text-xs text-[var(--text-muted)] mt-1">Total Storage Used</p>
              </div>
              <div className="text-center p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                <p className="text-3xl font-bold text-[var(--text-primary)] mono-engineering">
                  {objectCount.toLocaleString()}
                </p>
                <p className="text-xs text-[var(--text-muted)] mt-1">Total Objects</p>
              </div>

              {/* Usage bar visualization */}
              {categories.length > 0 && (
                <div>
                  <p className="text-xs text-[var(--text-muted)] mb-2 font-medium">Storage by Category</p>
                  <div className="h-3 rounded-full overflow-hidden bg-[var(--border-primary)] flex">
                    {categories.map((cat, idx) => {
                      const pct = totalSize > 0 ? (cat.size_bytes / totalSize) * 100 : 0;
                      if (pct < 1) return null;
                      const colors = [
                        "bg-brand-500",
                        "bg-green-500",
                        "bg-amber-500",
                        "bg-red-500",
                        "bg-blue-500",
                        "bg-purple-500",
                      ];
                      return (
                        <div
                          key={cat.name}
                          className={cn(colors[idx % colors.length], "h-full transition-all")}
                          style={{ width: `${pct}%` }}
                          title={`${cat.name}: ${formatBytes(cat.size_bytes)} (${pct.toFixed(1)}%)`}
                        />
                      );
                    })}
                  </div>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {categories.map((cat, idx) => {
                      const colors = [
                        "bg-brand-500",
                        "bg-green-500",
                        "bg-amber-500",
                        "bg-red-500",
                        "bg-blue-500",
                        "bg-purple-500",
                      ];
                      return (
                        <div key={cat.name} className="flex items-center gap-1.5">
                          <span className={cn("w-2 h-2 rounded-full", colors[idx % colors.length])} />
                          <span className="text-xs text-[var(--text-muted)]">{cat.name}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Category breakdown */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card padding="md">
            <CardHeader
              title="Category Breakdown"
              subtitle="Storage usage per category"
              icon={<Database className="w-4 h-4" />}
            />
            {categories.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-[var(--text-muted)]">No storage categories found</p>
              </div>
            ) : (
              <div className="max-h-96 overflow-y-auto space-y-3 pr-1">
                {categories.map((cat) => (
                  <div
                    key={cat.name}
                    className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <p className="text-sm font-medium text-[var(--text-primary)]">{cat.name}</p>
                      <Badge variant="neutral" size="sm">
                        {cat.count} objects
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[var(--text-muted)]">
                        {formatBytes(cat.size_bytes)}
                      </span>
                      <span className="text-xs text-[var(--text-muted)]">
                        Retention: {cat.retention_days}d
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Purge & Backup buttons */}
            <div className="mt-4 pt-4 border-t border-[var(--border-primary)] flex items-center gap-3 flex-wrap">
              <Button
                variant="danger"
                size="sm"
                icon={Trash2}
                onClick={() => setShowPurgeModal(true)}
                disabled={!tempCadCategory || tempCadCategory.count === 0}
              >
                Clear Temporary CAD Artifacts
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={Save}
                loading={backingUp}
                onClick={handleManualBackup}
              >
                Trigger Manual Backup
              </Button>
              {tempCadCategory && (
                <p className="text-xs text-[var(--text-muted)] mt-1.5">
                  {formatBytes(tempCadCategory.size_bytes)} in {tempCadCategory.count} temporary files
                </p>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Retention policy */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card padding="md">
            <CardHeader
              title="Retention Policy"
              subtitle="Data retention durations"
              icon={<HardDrive className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {retention && (
                <>
                  <div className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[var(--text-secondary)]">Default Retention</span>
                      <span className="text-sm font-mono text-[var(--text-primary)]">
                        {formatDuration(retention.default_days * 86400)}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">{retention.default_days} days</p>
                  </div>
                  <div className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[var(--text-secondary)]">Temp CAD Artifacts</span>
                      <span className="text-sm font-mono text-[var(--text-primary)]">
                        {formatDuration(retention.temp_artifacts_days * 86400)}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">{retention.temp_artifacts_days} days</p>
                  </div>
                  <div className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-[var(--text-secondary)]">Audit Logs</span>
                      <span className="text-sm font-mono text-[var(--text-primary)]">
                        {formatDuration(retention.audit_logs_days * 86400)}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">{retention.audit_logs_days} days</p>
                  </div>
                </>
              )}
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Purge confirmation modal */}
      <Modal
        open={showPurgeModal}
        onClose={() => setShowPurgeModal(false)}
        title="Purge Temporary CAD Artifacts"
        subtitle="This action cannot be undone"
        size="sm"
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setShowPurgeModal(false)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" icon={Trash2} loading={purging} onClick={handlePurge}>
              Purge Artifacts
            </Button>
          </>
        }
      >
        <div className="flex items-start gap-3 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-[var(--text-secondary)]">
              This will permanently delete all temporary CAD artifacts from storage.
            </p>
            {tempCadCategory && (
              <p className="text-xs text-[var(--text-muted)] mt-1">
                {formatBytes(tempCadCategory.size_bytes)} across {tempCadCategory.count} files will be removed.
              </p>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}
