import { motion } from "framer-motion";
import { AlertTriangle, Plus, Trash2, Zap } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, CardHeader, Modal } from "../components/ui";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn } from "../utils/helpers";

// ─── Types ───────────────────────────────────────────────────────────

interface ZIPLoadCoefficients {
  aZ: number; // Active impedance fraction
  aI: number; // Active current fraction
  aP: number; // Active power fraction
  bZ: number; // Reactive impedance fraction
  bI: number; // Reactive current fraction
  bP: number; // Reactive power fraction
}

interface ZIPLoad {
  id: string;
  name: string;
  coefficients: ZIPLoadCoefficients;
  preset?: string;
}

const ZIP_PRESETS: Record<string, { label: string; coefficients: ZIPLoadCoefficients }> = {
  constant_power: {
    label: "Constant Power",
    coefficients: { aZ: 0, aI: 0, aP: 1, bZ: 0, bI: 0, bP: 1 },
  },
  constant_impedance: {
    label: "Constant Impedance",
    coefficients: { aZ: 1, aI: 0, aP: 0, bZ: 1, bI: 0, bP: 0 },
  },
  constant_current: {
    label: "Constant Current",
    coefficients: { aZ: 0, aI: 1, aP: 0, bZ: 0, bI: 1, bP: 0 },
  },
  residential_ieee: {
    label: "Residential (IEEE)",
    coefficients: { aZ: 0.12, aI: 0.22, aP: 0.66, bZ: 0.12, bI: 0.22, bP: 0.66 },
  },
  commercial_ieee: {
    label: "Commercial (IEEE)",
    coefficients: { aZ: 0.08, aI: 0.18, aP: 0.74, bZ: 0.08, bI: 0.18, bP: 0.74 },
  },
  industrial_ieee: {
    label: "Industrial (IEEE)",
    coefficients: { aZ: 0.05, aI: 0.12, aP: 0.83, bZ: 0.05, bI: 0.12, bP: 0.83 },
  },
  mixed_load: {
    label: "Mixed Load",
    coefficients: { aZ: 0.15, aI: 0.30, aP: 0.55, bZ: 0.20, bI: 0.25, bP: 0.55 },
  },
};

// ─── SVG Preview Chart ───────────────────────────────────────────────

function ZIPLoadPreviewChart({ coefficients }: { readonly coefficients: ZIPLoadCoefficients }) {
  // Compute load response P/P0 vs V/V0 for the active power portion
  // P/P0 = aZ * (V/V0)^2 + aI * (V/V0) + aP
  const width = 280;
  const height = 160;
  const padX = 40;
  const padY = 20;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;

  const points: string[] = [];
  const nPoints = 50;

  for (let i = 0; i <= nPoints; i++) {
    const v = 0.8 + (i / nPoints) * 0.4; // V/V0 from 0.8 to 1.2
    const pActive = coefficients.aZ * v * v + coefficients.aI * v + coefficients.aP;
    const x = padX + (i / nPoints) * plotW;
    const yActive = padY + plotH - ((pActive - 0.4) / 1.0) * plotH;
    points.push(`${x},${Math.max(padY, Math.min(padY + plotH, yActive))}`);
    // Reactive points are collected in a separate pass below.
  }

  const reactivePoints: string[] = [];
  for (let i = 0; i <= nPoints; i++) {
    const v = 0.8 + (i / nPoints) * 0.4;
    const pReactive = coefficients.bZ * v * v + coefficients.bI * v + coefficients.bP;
    const x = padX + (i / nPoints) * plotW;
    const yReactive = padY + plotH - ((pReactive - 0.4) / 1.0) * plotH;
    reactivePoints.push(`${x},${Math.max(padY, Math.min(padY + plotH, yReactive))}`);
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ minHeight: 120 }}>
      {/* Grid lines */}
      <line x1={padX} y1={padY} x2={padX} y2={padY + plotH} stroke="var(--border-primary)" strokeWidth="0.5" />
      <line x1={padX} y1={padY + plotH} x2={padX + plotW} y2={padY + plotH} stroke="var(--border-primary)" strokeWidth="0.5" />

      {/* Y-axis labels */}
      <text x={padX - 5} y={padY + 4} textAnchor="end" fill="var(--text-muted)" fontSize="8">1.4</text>
      <text x={padX - 5} y={padY + plotH / 2 + 3} textAnchor="end" fill="var(--text-muted)" fontSize="8">0.9</text>
      <text x={padX - 5} y={padY + plotH + 3} textAnchor="end" fill="var(--text-muted)" fontSize="8">0.4</text>

      {/* X-axis labels */}
      <text x={padX} y={padY + plotH + 12} textAnchor="middle" fill="var(--text-muted)" fontSize="8">0.8</text>
      <text x={padX + plotW / 2} y={padY + plotH + 12} textAnchor="middle" fill="var(--text-muted)" fontSize="8">1.0</text>
      <text x={padX + plotW} y={padY + plotH + 12} textAnchor="middle" fill="var(--text-muted)" fontSize="8">1.2</text>

      {/* Reference line at P/P0 = 1.0, V/V0 = 1.0 */}
      <line x1={padX + plotW / 2} y1={padY} x2={padX + plotW / 2} y2={padY + plotH} stroke="var(--border-primary)" strokeWidth="0.5" strokeDasharray="4,3" />

      {/* Active power curve */}
      <polyline points={points.join(" ")} fill="none" stroke="var(--color-engine-power)" strokeWidth="2" />

      {/* Reactive power curve */}
      <polyline points={reactivePoints.join(" ")} fill="none" stroke="var(--color-engine-voltage)" strokeWidth="2" strokeDasharray="6,3" />

      {/* Legend */}
      <line x1={padX + 10} y1={padY + 8} x2={padX + 25} y2={padY + 8} stroke="var(--color-engine-power)" strokeWidth="2" />
      <text x={padX + 28} y={padY + 11} fill="var(--text-muted)" fontSize="8">P (active)</text>
      <line x1={padX + 80} y1={padY + 8} x2={padX + 95} y2={padY + 8} stroke="var(--color-engine-voltage)" strokeWidth="2" strokeDasharray="6,3" />
      <text x={padX + 98} y={padY + 11} fill="var(--text-muted)" fontSize="8">Q (reactive)</text>

      {/* Axis titles */}
      <text x={padX + plotW / 2} y={height - 2} textAnchor="middle" fill="var(--text-tertiary)" fontSize="9">V / V₀</text>
      <text x={8} y={padY + plotH / 2} textAnchor="middle" fill="var(--text-tertiary)" fontSize="9" transform={`rotate(-90, 8, ${padY + plotH / 2})`}>P / P₀</text>
    </svg>
  );
}

// ─── Coefficient Input ───────────────────────────────────────────────

function CoefficientInput({
  label,
  value,
  onChange,
}: {
  readonly label: string;
  readonly value: number;
  readonly onChange: (val: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs font-medium text-[var(--text-tertiary)] min-w-[24px]">{label}</label>
      <input
        type="number"
        min={0}
        max={1}
        step={0.01}
        value={value}
        onChange={(e) => {
          const v = Math.min(1, Math.max(0, Number(e.target.value) || 0));
          onChange(v);
        }}
        className="w-20 px-2 py-1.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
      />
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────

interface ZIPLoadEditorDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onLoadSaved?: () => void;
}

export default function ZIPLoadEditorDialog({ open, onClose, onLoadSaved }: ZIPLoadEditorDialogProps) {
  const { notify } = useNotify();
  const [loads, setLoads] = useState<ZIPLoad[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingCoeffs, setEditingCoeffs] = useState<ZIPLoadCoefficients>(ZIP_PRESETS.constant_power.coefficients);
  const [selectedPreset, setSelectedPreset] = useState<string>("custom");
  const [activeLoadId, setActiveLoadId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Validation: active coefficients sum to 1.0
  const activeSum = useMemo(
    () => editingCoeffs.aZ + editingCoeffs.aI + editingCoeffs.aP,
    [editingCoeffs],
  );
  const reactiveSum = useMemo(
    () => editingCoeffs.bZ + editingCoeffs.bI + editingCoeffs.bP,
    [editingCoeffs],
  );
  const isValid = Math.abs(activeSum - 1.0) < 0.01 && Math.abs(reactiveSum - 1.0) < 0.01;

  // Fetch ZIP loads
  const fetchLoads = useCallback(async () => {
    setLoading(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/equipment/zip-generators/zip-loads`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      const items: ZIPLoad[] = Array.isArray(data)
        ? data.map((item: Record<string, unknown>) => ({
            id: String(item.id ?? crypto.randomUUID()),
            name: String(item.name ?? "Unnamed Load"),
            coefficients: {
              aZ: Number((item.coefficients as Record<string, number>)?.aZ ?? 0),
              aI: Number((item.coefficients as Record<string, number>)?.aI ?? 0),
              aP: Number((item.coefficients as Record<string, number>)?.aP ?? 1),
              bZ: Number((item.coefficients as Record<string, number>)?.bZ ?? 0),
              bI: Number((item.coefficients as Record<string, number>)?.bI ?? 0),
              bP: Number((item.coefficients as Record<string, number>)?.bP ?? 1),
            },
            preset: String(item.preset ?? "custom"),
          }))
        : [];
      setLoads(items);
    } catch {
      // Silently fail — dialog may be opened without backend
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchLoads();
  }, [open, fetchLoads]);

  // Preset selection
  const handlePresetChange = (preset: string) => {
    setSelectedPreset(preset);
    if (preset !== "custom" && ZIP_PRESETS[preset]) {
      setEditingCoeffs({ ...ZIP_PRESETS[preset].coefficients });
    }
  };

  // Create new ZIP load
  const handleCreate = async () => {
    if (!isValid) {
      notify("error", "Coefficients must sum to 1.0 for both active and reactive");
      return;
    }
    setSaving(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/equipment/zip-generators/zip-loads`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          name: `ZIP Load ${loads.length + 1}`,
          coefficients: editingCoeffs,
          preset: selectedPreset,
        }),
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      notify("success", "ZIP load created successfully");
      fetchLoads();
      onLoadSaved?.();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to create ZIP load: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Update existing ZIP load
  const handleUpdate = async () => {
    if (!activeLoadId || !isValid) return;
    setSaving(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/equipment/zip-generators/zip-loads/${activeLoadId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ coefficients: editingCoeffs, preset: selectedPreset }),
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      notify("success", "ZIP load updated successfully");
      setActiveLoadId(null);
      fetchLoads();
      onLoadSaved?.();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to update ZIP load: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Delete ZIP load
  const handleDelete = async (id: string) => {
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/equipment/zip-generators/zip-loads/${id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      notify("success", "ZIP load deleted");
      fetchLoads();
      if (activeLoadId === id) setActiveLoadId(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to delete ZIP load: ${msg}`);
    }
  };

  // Select a load for editing
  const handleSelectLoad = (load: ZIPLoad) => {
    setActiveLoadId(load.id);
    setEditingCoeffs({ ...load.coefficients });
    setSelectedPreset(load.preset ?? "custom");
  };

  return (
    <Modal open={open} onClose={onClose} title="ZIP Load Editor" subtitle="Edit ZIP load model coefficients" size="xl">
      <div className="flex items-center gap-2 mb-4">
        <ContextHelpButton contextId="equipment.zip-load-editor" />
        <span className="text-xs text-[var(--text-muted)]">ZIP load models define how load varies with voltage</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Load list & editor */}
        <div className="space-y-4">
          {/* Preset selection */}
          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">Preset</label>
            <select
              value={selectedPreset}
              onChange={(e) => handlePresetChange(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
            >
              <option value="custom">Custom</option>
              {Object.entries(ZIP_PRESETS).map(([key, preset]) => (
                <option key={key} value={key}>
                  {preset.label}
                </option>
              ))}
            </select>
          </div>

          {/* Active power coefficients */}
          <div>
            <p className="text-sm font-medium text-[var(--text-secondary)] mb-2">Active Power (P)</p>
            <div className="flex items-center gap-3 flex-wrap">
              <CoefficientInput label="aZ" value={editingCoeffs.aZ} onChange={(v) => setEditingCoeffs({ ...editingCoeffs, aZ: v })} />
              <CoefficientInput label="aI" value={editingCoeffs.aI} onChange={(v) => setEditingCoeffs({ ...editingCoeffs, aI: v })} />
              <CoefficientInput label="aP" value={editingCoeffs.aP} onChange={(v) => setEditingCoeffs({ ...editingCoeffs, aP: v })} />
              <Badge variant={Math.abs(activeSum - 1.0) < 0.01 ? "success" : "danger"} size="sm">
                Σ = {activeSum.toFixed(2)}
              </Badge>
            </div>
          </div>

          {/* Reactive power coefficients */}
          <div>
            <p className="text-sm font-medium text-[var(--text-secondary)] mb-2">Reactive Power (Q)</p>
            <div className="flex items-center gap-3 flex-wrap">
              <CoefficientInput label="bZ" value={editingCoeffs.bZ} onChange={(v) => setEditingCoeffs({ ...editingCoeffs, bZ: v })} />
              <CoefficientInput label="bI" value={editingCoeffs.bI} onChange={(v) => setEditingCoeffs({ ...editingCoeffs, bI: v })} />
              <CoefficientInput label="bP" value={editingCoeffs.bP} onChange={(v) => setEditingCoeffs({ ...editingCoeffs, bP: v })} />
              <Badge variant={Math.abs(reactiveSum - 1.0) < 0.01 ? "success" : "danger"} size="sm">
                Σ = {reactiveSum.toFixed(2)}
              </Badge>
            </div>
          </div>

          {/* Validation warning */}
          {!isValid && (
            <motion.div
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20"
            >
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span className="text-xs text-amber-400">Both active and reactive coefficients must sum to 1.0</span>
            </motion.div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm" icon={Plus} loading={saving} onClick={activeLoadId ? handleUpdate : handleCreate} disabled={!isValid}>
              {activeLoadId ? "Update Load" : "Create Load"}
            </Button>
            {activeLoadId && (
              <Button variant="ghost" size="sm" onClick={() => { setActiveLoadId(null); setEditingCoeffs(ZIP_PRESETS.constant_power.coefficients); setSelectedPreset("custom"); }}>
                Cancel Edit
              </Button>
            )}
          </div>
        </div>

        {/* Right: Preview chart & load list */}
        <div className="space-y-4">
          {/* Preview chart */}
          <Card padding="md">
            <CardHeader title="Load Response Preview" subtitle="P/P₀ vs V/V₀" icon={<Zap className="w-4 h-4" />} />
            <ZIPLoadPreviewChart coefficients={editingCoeffs} />
          </Card>

          {/* Existing loads list */}
          <div>
            <p className="text-sm font-medium text-[var(--text-secondary)] mb-2">Existing ZIP Loads</p>
            {(() => {
              if (loading) {
                return (
                  <div className="flex items-center justify-center py-6">
                    <div className="w-6 h-6 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
                  </div>
                );
              }
              if (loads.length === 0) {
                return <p className="text-xs text-[var(--text-muted)] py-4 text-center">No ZIP loads configured</p>;
              }
              return (
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1">
                  {loads.map((load) => (
                    <div
                      key={load.id}
                      role="button"
                      tabIndex={0}
                      aria-label={`Select ${load.name}`}
                      className={cn(
                        "flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-all",
                        activeLoadId === load.id
                          ? "bg-brand-500/10 border-brand-500/30"
                          : "bg-[var(--bg-primary)] border-[var(--border-primary)] hover:border-brand-500/30",
                      )}
                      onClick={() => handleSelectLoad(load)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          handleSelectLoad(load);
                        }
                      }}
                    >
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">{load.name}</p>
                        <p className="text-xs text-[var(--text-muted)] font-mono">
                          aZ={load.coefficients.aZ.toFixed(2)} aI={load.coefficients.aI.toFixed(2)} aP={load.coefficients.aP.toFixed(2)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); handleDelete(load.id); }}
                        className="p-1.5 rounded-lg hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              );
            })()}
          </div>
        </div>
      </div>
    </Modal>
  );
}
