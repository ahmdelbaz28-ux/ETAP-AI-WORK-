import { CheckCircle2, Lock, RotateCcw, Save, Sliders, X } from "lucide-react";
import { useEffect, useState } from "react";
import { request } from "../../lib/api";
import { useChatStore } from "../../store/chatStore";
import { cn } from "../../utils/helpers";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

export interface SolverParams {
  convergence_tolerance: number;
  max_iterations: number;
}

const DEFAULTS: SolverParams = {
  convergence_tolerance: 1e-5,
  max_iterations: 50,
};

interface ParametersDrawerProps {
  open: boolean;
  onClose: () => void;
  projectId?: string | null;
}

export function ParametersDrawer({ open, onClose, projectId: propProjectId }: ParametersDrawerProps) {
  const storeProjectId = useChatStore((s) => s.projectId);
  const streamStatus = useChatStore((s) => s.streamStatus);
  const isExecuting = streamStatus === "streaming" || streamStatus === "connecting";
  const targetProject = propProjectId ?? storeProjectId ?? "";

  const [params, setParams] = useState<SolverParams>(DEFAULTS);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;
    async function fetchParams() {
      setLoading(true);
      setError(null);
      try {
        const url = targetProject
          ? `/api/v1/studies/parameters/${encodeURIComponent(targetProject)}`
          : "/api/v1/studies/parameters";
        const res = await request<SolverParams>(url);
        if (active && res) {
          setParams({
            convergence_tolerance: res.convergence_tolerance ?? DEFAULTS.convergence_tolerance,
            max_iterations: res.max_iterations ?? DEFAULTS.max_iterations,
          });
        }
      } catch (err) {
        if (active) {
          // Fallback to defaults
          setParams(DEFAULTS);
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void fetchParams();
    return () => {
      active = false;
    };
  }, [open, targetProject]);

  const handleSave = async () => {
    if (isExecuting) return;
    setSaving(true);
    setError(null);
    setSavedSuccess(false);
    try {
      const url = targetProject
        ? `/api/v1/studies/parameters/${encodeURIComponent(targetProject)}`
        : "/api/v1/studies/parameters";
      await request<SolverParams>(url, {
        method: "PUT",
        body: JSON.stringify(params),
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("422") || msg.includes("acceleration_factor")) {
        setError("معامل ملغي — acceleration_factor محذوف من النظام (Deprecated parameter)");
      } else {
        setError(msg || "Failed to update solver parameters");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (isExecuting) return;
    setParams(DEFAULTS);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-xs animate-in fade-in duration-200"
      data-testid="parameters-drawer-overlay"
      onClick={onClose}
    >
      <div
        className={cn(
          "w-full max-w-md h-full bg-[#1A1F26] border-l border-[#334155] shadow-2xl flex flex-col",
          "animate-in slide-in-from-right duration-300",
        )}
        onClick={(e) => e.stopPropagation()}
        data-testid="parameters-drawer"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#334155] bg-[#14181F]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/30 text-brand-400 flex items-center justify-center">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                Solver Parameters
                <Badge variant="info" size="sm">
                  Newton-Raphson
                </Badge>
                {isExecuting && (
                  <Badge variant="warning" size="sm" className="flex items-center gap-1">
                    <Lock className="w-3 h-3" /> Locked
                  </Badge>
                )}
              </h2>
              <p className="text-[11px] text-slate-400">
                Project: <span className="font-mono text-slate-300">{targetProject || "UNASSIGNED"}</span> • Power-Flow Convergence Settings
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-[#20262E] transition-colors"
            data-testid="parameters-drawer-close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {isExecuting && (
            <div
              className="p-3 rounded-lg bg-amber-950/40 border border-amber-500/40 text-amber-300 text-xs flex items-center gap-2"
              data-testid="parameters-locked-banner"
            >
              <Lock className="w-4 h-4 shrink-0 text-amber-400" />
              <span>Parameters are locked while a simulation is running to guarantee reproducibility.</span>
            </div>
          )}
          {savedSuccess && (
            <div
              className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2 animate-in fade-in"
              data-testid="parameters-saved-alert"
            >
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
              <span>Parameters applied — subsequent study runs will use these values.</span>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs">
              {error}
            </div>
          )}

          {/* Convergence Tolerance */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <label htmlFor="convergence-tolerance" className="font-medium text-slate-200">
                Convergence Tolerance (ε)
              </label>
              <span className="font-mono text-brand-400 bg-brand-950/50 px-2 py-0.5 rounded border border-brand-500/30 text-[11px]">
                {params.convergence_tolerance.toExponential(1)}
              </span>
            </div>
            <input
              id="convergence-tolerance"
              type="range"
              min="0.000001"
              max="0.001"
              step="0.000001"
              value={params.convergence_tolerance}
              disabled={isExecuting}
              onChange={(e) =>
                setParams((prev) => ({
                  ...prev,
                  convergence_tolerance: Number.parseFloat(e.target.value),
                }))
              }
              className="w-full accent-brand-500 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="input-tolerance"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>1e-6 (Precision)</span>
              <span>1e-4</span>
              <span>1e-3 (Fast)</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Mismatches in MW and Mvar must be less than this tolerance for convergence.
            </p>
          </div>

          {/* Max Iterations */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <label htmlFor="max-iterations" className="font-medium text-slate-200">
                Maximum Iterations
              </label>
              <span className="font-mono text-brand-400 bg-brand-950/50 px-2 py-0.5 rounded border border-brand-500/30 text-[11px]">
                {params.max_iterations}
              </span>
            </div>
            <input
              id="max-iterations"
              type="range"
              min="10"
              max="200"
              step="5"
              value={params.max_iterations}
              disabled={isExecuting}
              onChange={(e) =>
                setParams((prev) => ({
                  ...prev,
                  max_iterations: Number.parseInt(e.target.value, 10),
                }))
              }
              className="w-full accent-brand-500 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="input-iterations"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>10 iters</span>
              <span>100</span>
              <span>200 iters</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Cutoff limit before declaring non-convergence or voltage collapse.
            </p>
          </div>

          {/* Title Block Reference Note */}
          <div className="p-3 rounded-lg bg-[#20262E] border border-[#334155] text-[11px] text-slate-300 font-mono">
            <div className="text-slate-400 font-semibold mb-1">COMPLIANCE SPECIFICATION:</div>
            <div>STANDARD: IEEE 3002.7 (Industrial Power Systems Load Flow)</div>
            <div>FORMULATION: Full Newton-Raphson with Polar Coordinates</div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#334155] bg-[#14181F] flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            icon={RotateCcw}
            onClick={handleReset}
            disabled={loading || saving || isExecuting}
            data-testid="parameters-reset-btn"
          >
            Defaults
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={saving ? undefined : Save}
              loading={saving}
              disabled={saving || isExecuting}
              onClick={() => void handleSave()}
              data-testid="parameters-save-btn"
            >
              Save Parameters
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ParametersDrawer;
