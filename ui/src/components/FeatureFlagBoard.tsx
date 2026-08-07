import { motion } from "framer-motion";
import { AlertTriangle, FlaskConical, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, CardHeader, Toggle } from "../components/ui";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn } from "../utils/helpers";

// ─── Types ───────────────────────────────────────────────────────────

type FeatureFlagStatus = "alpha" | "beta" | "stable";

interface FeatureFlag {
  id: string;
  key: string;
  name: string;
  description: string;
  status: FeatureFlagStatus;
  enabled: boolean;
  category: string;
}

const STATUS_CONFIG: Record<FeatureFlagStatus, { variant: "info" | "warning" | "success"; label: string }> = {
  alpha: { variant: "info", label: "Alpha" },
  beta: { variant: "warning", label: "Beta" },
  stable: { variant: "success", label: "Stable" },
};

// ─── Component ───────────────────────────────────────────────────────

export default function FeatureFlagBoard() {
  const { notify } = useNotify();
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [original, setOriginal] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch feature flags
  const fetchFlags = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/feature-flags`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      const items: FeatureFlag[] = Array.isArray(data)
        ? data.map((f: Record<string, unknown>) => ({
            id: typeof f.id === "string" ? f.id : crypto.randomUUID(),
            key: typeof f.key === "string" ? f.key : "",
            name: typeof f.name === "string" ? f.name : "Unnamed Flag",
            description: typeof f.description === "string" ? f.description : "",
            status: (f.status as FeatureFlagStatus) ?? "beta",
            enabled: Boolean(f.enabled ?? false),
            category: typeof f.category === "string" ? f.category : "general",
          }))
        : [];
      setFlags(items);
      setOriginal(items);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFlags();
  }, [fetchFlags]);

  // Save all flags
  const handleSave = async () => {
    setSaving(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/feature-flags`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ flags: flags.map((f) => ({ key: f.key, enabled: f.enabled })) }),
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      setOriginal(flags.map((f) => ({ ...f })));
      notify("success", "Feature flags updated successfully");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to save feature flags: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Toggle a flag
  const toggleFlag = (id: string) => {
    setFlags(flags.map((f) => (f.id === id ? { ...f, enabled: !f.enabled } : f)));
  };

  const hasChanges = JSON.stringify(flags) !== JSON.stringify(original);

  // Group flags by category
  const categories = flags.reduce<Record<string, FeatureFlag[]>>((acc, flag) => {
    const cat = flag.category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(flag);
    return acc;
  }, {});

  // Count enabled flags
  const enabledCount = flags.filter((f) => f.enabled).length;
  const totalCount = flags.length;

  // ─── Loading state ────────────────────────────────────────────────
  if (loading && error === null) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading feature flags…</span>
        </div>
      </div>
    );
  }

  // ─── Error state ──────────────────────────────────────────────────
  if (error && flags.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] mb-2">Failed to load feature flags</p>
          <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{error}</p>
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={fetchFlags}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

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
            <FlaskConical className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Feature Flags</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Manage beta capabilities & experimental features</p>
              <ContextHelpButton contextId="admin.feature-flags" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="neutral" size="md">
            {enabledCount}/{totalCount} enabled
          </Badge>
          <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave} disabled={!hasChanges}>
            Save Changes
          </Button>
        </div>
      </motion.div>

      {/* Summary bar */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <div className="flex items-center gap-4 p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)]">
          <div className="flex items-center gap-2">
            <Badge variant="info" size="sm" dot>Alpha</Badge>
            <span className="text-xs text-[var(--text-muted)]">
              {flags.filter((f) => f.status === "alpha").length} flags
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="warning" size="sm" dot>Beta</Badge>
            <span className="text-xs text-[var(--text-muted)]">
              {flags.filter((f) => f.status === "beta").length} flags
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="success" size="sm" dot>Stable</Badge>
            <span className="text-xs text-[var(--text-muted)]">
              {flags.filter((f) => f.status === "stable").length} flags
            </span>
          </div>
        </div>
      </motion.div>

      {/* Flag categories */}
      {Object.entries(categories).length === 0 ? (
        <Card padding="md">
          <div className="text-center py-8">
            <p className="text-sm text-[var(--text-muted)]">No feature flags configured</p>
          </div>
        </Card>
      ) : (
        Object.entries(categories).map(([category, categoryFlags], categoryIdx) => (
          <motion.div
            key={category}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + categoryIdx * 0.05 }}
          >
            <Card padding="md">
              <CardHeader
                title={category.charAt(0).toUpperCase() + category.slice(1)}
                subtitle={`${categoryFlags.length} feature${categoryFlags.length !== 1 ? "s" : ""}`}
                icon={<FlaskConical className="w-4 h-4" />}
              />
              <div className="space-y-3">
                {categoryFlags.map((flag) => {
                  const statusConfig = STATUS_CONFIG[flag.status] ?? STATUS_CONFIG.beta;
                  const isChanged = original.find((o) => o.id === flag.id)?.enabled !== flag.enabled;
                  return (
                    <div
                      key={flag.id}
                      className={cn(
                        "flex items-center justify-between p-3 rounded-lg border transition-all",
                        flag.enabled
                          ? "bg-brand-500/5 border-brand-500/20"
                          : "bg-[var(--bg-primary)] border-[var(--border-primary)]",
                        isChanged && "ring-1 ring-brand-500/30",
                      )}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <p className="text-sm font-medium text-[var(--text-primary)]">{flag.name}</p>
                          <Badge variant={statusConfig.variant} size="sm">
                            {statusConfig.label}
                          </Badge>
                          {isChanged && (
                            <Badge variant="brand" size="sm">Modified</Badge>
                          )}
                        </div>
                        <p className="text-xs text-[var(--text-muted)]">{flag.description}</p>
                        <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">{flag.key}</p>
                      </div>
                      <Toggle
                        checked={flag.enabled}
                        onChange={() => toggleFlag(flag.id)}
                        size="sm"
                      />
                    </div>
                  );
                })}
              </div>
            </Card>
          </motion.div>
        ))
      )}

      {/* Unsaved changes indicator */}
      {hasChanges && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-primary)] shadow-lg"
        >
          <span className="text-sm text-[var(--text-secondary)]">Unsaved changes</span>
          <Button variant="ghost" size="sm" onClick={() => setFlags(original.map((f) => ({ ...f })))}>
            Discard
          </Button>
          <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave}>
            Save
          </Button>
        </motion.div>
      )}
    </div>
  );
}
