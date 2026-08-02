import { motion } from "framer-motion";
import { AlertTriangle, RotateCcw, Save, Settings, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, Card, CardHeader } from "../components/ui";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn } from "../utils/helpers";

// ─── Types ───────────────────────────────────────────────────────────

interface SolverParameters {
  convergence_tolerance: number;
  max_iterations: number;
  acceleration_factor: number;
  zbus_enabled: boolean;
  zbus_iteration_limit: number;
  zbus_voltage_threshold: number;
}

const DEFAULT_PARAMETERS: SolverParameters = {
  convergence_tolerance: 1e-4,
  max_iterations: 50,
  acceleration_factor: 1.4,
  zbus_enabled: true,
  zbus_iteration_limit: 100,
  zbus_voltage_threshold: 0.001,
};

// ─── Logarithmic slider helper ───────────────────────────────────────

const LOG_MIN = -6; // 1e-6
const LOG_MAX = -3; // 1e-3

function logToSlider(logVal: number): number {
  return ((logVal - LOG_MIN) / (LOG_MAX - LOG_MIN)) * 100;
}

function sliderToLog(pct: number): number {
  return LOG_MIN + (pct / 100) * (LOG_MAX - LOG_MIN);
}

function formatTolerance(val: number): string {
  return val.toExponential(1);
}

// ─── Component ───────────────────────────────────────────────────────

export default function EngineeringEngineSettings() {
  const { notify } = useNotify();
  const [params, setParams] = useState<SolverParameters>(DEFAULT_PARAMETERS);
  const [original, setOriginal] = useState<SolverParameters>(DEFAULT_PARAMETERS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch current parameters
  const fetchParams = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/studies/parameters`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      const fetched: SolverParameters = {
        convergence_tolerance: data.convergence_tolerance ?? DEFAULT_PARAMETERS.convergence_tolerance,
        max_iterations: data.max_iterations ?? DEFAULT_PARAMETERS.max_iterations,
        acceleration_factor: data.acceleration_factor ?? DEFAULT_PARAMETERS.acceleration_factor,
        zbus_enabled: data.zbus_enabled ?? DEFAULT_PARAMETERS.zbus_enabled,
        zbus_iteration_limit: data.zbus_iteration_limit ?? DEFAULT_PARAMETERS.zbus_iteration_limit,
        zbus_voltage_threshold: data.zbus_voltage_threshold ?? DEFAULT_PARAMETERS.zbus_voltage_threshold,
      };
      setParams(fetched);
      setOriginal(fetched);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchParams();
  }, [fetchParams]);

  // Save parameters
  const handleSave = async () => {
    setSaving(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/studies/parameters`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(params),
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      setOriginal({ ...params });
      notify("success", "Solver parameters saved successfully");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to save parameters: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Reset to defaults
  const handleReset = () => {
    setParams({ ...DEFAULT_PARAMETERS });
    notify("info", "Parameters reset to defaults");
  };

  const hasChanges = JSON.stringify(params) !== JSON.stringify(original);

  // ─── Loading state ────────────────────────────────────────────────
  if (loading && error === null) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading solver parameters…</span>
        </div>
      </div>
    );
  }

  // ─── Error state ──────────────────────────────────────────────────
  if (error && loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] mb-2">Failed to load solver parameters</p>
          <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{error}</p>
          <Button variant="secondary" size="sm" onClick={fetchParams}>
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
            <SlidersHorizontal className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Engine Settings</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Solver parameters & convergence configuration</p>
              <ContextHelpButton contextId="engineering.engine-settings" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" icon={RotateCcw} onClick={handleReset}>
            Reset Defaults
          </Button>
          <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave} disabled={!hasChanges}>
            Save Changes
          </Button>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Convergence Settings */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card padding="md">
            <CardHeader
              title="Convergence Settings"
              subtitle="Power flow solver convergence criteria"
              icon={<Settings className="w-4 h-4" />}
            />
            <div className="space-y-6">
              {/* Convergence Tolerance — logarithmic slider */}
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  Convergence Tolerance
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={1}
                    value={logToSlider(Math.log10(params.convergence_tolerance))}
                    onChange={(e) => {
                      const logVal = sliderToLog(Number(e.target.value));
                      setParams({ ...params, convergence_tolerance: Math.pow(10, logVal) });
                    }}
                    className="flex-1 h-2 rounded-full appearance-none bg-[var(--border-primary)] cursor-pointer accent-brand-500"
                  />
                  <span className="text-sm font-mono text-[var(--text-primary)] min-w-[80px] text-right">
                    {formatTolerance(params.convergence_tolerance)}
                  </span>
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-xs text-[var(--text-muted)]">1e-6 (tight)</span>
                  <span className="text-xs text-[var(--text-muted)]">1e-3 (loose)</span>
                </div>
              </div>

              {/* Max Iterations */}
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  Max Iterations
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min={10}
                    max={200}
                    step={1}
                    value={params.max_iterations}
                    onChange={(e) => {
                      const val = Math.min(200, Math.max(10, Number(e.target.value) || 10));
                      setParams({ ...params, max_iterations: val });
                    }}
                    className="w-28 px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  />
                  <span className="text-xs text-[var(--text-muted)]">Range: 10 – 200</span>
                </div>
              </div>

              {/* Acceleration Factor */}
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  Acceleration Factor
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min={1.0}
                    max={2.0}
                    step={0.05}
                    value={params.acceleration_factor}
                    onChange={(e) => {
                      const val = Math.min(2.0, Math.max(1.0, Number(e.target.value) || 1.0));
                      setParams({ ...params, acceleration_factor: val });
                    }}
                    className="w-28 px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  />
                  <span className="text-xs text-[var(--text-muted)]">Range: 1.0 – 2.0</span>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* ZBus Parameters */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card padding="md">
            <CardHeader
              title="ZBus Parameters"
              subtitle="Impedance matrix solver options"
              icon={<Settings className="w-4 h-4" />}
            />
            <div className="space-y-6">
              {/* ZBus Enabled */}
              <div className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">ZBus Solver Enabled</p>
                  <p className="text-xs text-[var(--text-muted)] mt-0.5">Use impedance matrix method for fault analysis</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={params.zbus_enabled}
                  onClick={() => setParams({ ...params, zbus_enabled: !params.zbus_enabled })}
                  className={cn(
                    "relative rounded-full transition-colors shrink-0 w-11 h-6",
                    params.zbus_enabled ? "bg-brand-500" : "bg-[var(--border-secondary)]",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 bg-white rounded-full shadow-sm transition-transform w-5 h-5",
                      params.zbus_enabled ? "translate-x-[22px]" : "translate-x-0.5",
                    )}
                  />
                </button>
              </div>

              {/* ZBus Iteration Limit */}
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  ZBus Iteration Limit
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min={10}
                    max={500}
                    step={10}
                    value={params.zbus_iteration_limit}
                    onChange={(e) => {
                      const val = Math.min(500, Math.max(10, Number(e.target.value) || 10));
                      setParams({ ...params, zbus_iteration_limit: val });
                    }}
                    className="w-28 px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  />
                  <span className="text-xs text-[var(--text-muted)]">Range: 10 – 500</span>
                </div>
              </div>

              {/* ZBus Voltage Threshold */}
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                  Voltage Threshold (pu)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min={0.0001}
                    max={0.1}
                    step={0.0001}
                    value={params.zbus_voltage_threshold}
                    onChange={(e) => {
                      const val = Math.min(0.1, Math.max(0.0001, Number(e.target.value) || 0.001));
                      setParams({ ...params, zbus_voltage_threshold: val });
                    }}
                    className="w-28 px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  />
                  <span className="text-xs text-[var(--text-muted)]">Range: 0.0001 – 0.1 pu</span>
                </div>
              </div>

              {/* Current values summary */}
              <div className="p-3 bg-[var(--bg-elevated)] rounded-lg border border-[var(--border-primary)]">
                <p className="text-xs text-[var(--text-muted)] mb-2 font-medium">Current Configuration</p>
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-tertiary)]">Tolerance</span>
                    <span className="text-[var(--text-primary)] font-mono">{formatTolerance(params.convergence_tolerance)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-tertiary)]">Max Iterations</span>
                    <span className="text-[var(--text-primary)] font-mono">{params.max_iterations}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-tertiary)]">Acceleration</span>
                    <span className="text-[var(--text-primary)] font-mono">{params.acceleration_factor.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-tertiary)]">ZBus</span>
                    <span className={cn("font-mono", params.zbus_enabled ? "text-green-400" : "text-[var(--text-muted)]")}>
                      {params.zbus_enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Unsaved changes indicator */}
      {hasChanges && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-primary)] shadow-lg"
        >
          <span className="text-sm text-[var(--text-secondary)]">Unsaved changes</span>
          <Button variant="ghost" size="sm" onClick={() => setParams({ ...original })}>
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
