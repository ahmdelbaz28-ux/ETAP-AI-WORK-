import {
  Activity,
  CheckCircle2,
  Globe,
  Maximize2,
  Minimize2,
  Network,
  Radio,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useChatStore } from "../../store/chatStore";
import { cn } from "../../utils/helpers";
import { Badge } from "../ui/Badge";

export function AutoViewPanel() {
  const activeView = useChatStore((s) => s.activeView);
  const setActiveView = useChatStore((s) => s.setActiveView);
  const results = useChatStore((s) => s.results);
  const [isExpanded, setIsExpanded] = useState(false);
  const [lastVerified, setLastVerified] = useState<string | null>(null);

  // When a new result arrives, update verified timestamp
  useEffect(() => {
    if (results.length > 0) {
      setLastVerified(new Date().toLocaleTimeString());
    }
  }, [results.length]);

  if (!activeView) return null;

  return (
    <aside
      className={cn(
        "border-l border-[var(--border-primary)] bg-[var(--bg-input)] flex flex-col z-30 transition-all duration-300 ease-in-out shadow-2xl shrink-0",
        isExpanded ? "w-[680px]" : "w-[440px]",
      )}
      data-testid="auto-view-panel"
      aria-label="Auto-view Live Subsystem Panel"
    >
      {/* Top Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[var(--border-primary)] bg-[var(--bg-elevated)] shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 p-1 bg-[var(--bg-card)] rounded-md border border-[var(--border-primary)]">
            <button
              type="button"
              onClick={() => setActiveView("scada")}
              className={cn(
                "px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 cursor-pointer",
                activeView === "scada"
                  ? "bg-cyan-600/30 text-cyan-300 border border-cyan-500/40"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-primary)]",
              )}
              data-testid="autoview-tab-scada"
            >
              <Activity className="w-3 h-3" />
              SCADA
            </button>
            <button
              type="button"
              onClick={() => setActiveView("gis")}
              className={cn(
                "px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 cursor-pointer",
                activeView === "gis"
                  ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/40"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-primary)]",
              )}
              data-testid="autoview-tab-gis"
            >
              <Globe className="w-3 h-3" />
              GIS Map
            </button>
            <button
              type="button"
              onClick={() => setActiveView("grid")}
              className={cn(
                "px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 cursor-pointer",
                activeView === "grid"
                  ? "bg-brand-600/30 text-brand-300 border border-brand-500/40"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-primary)]",
              )}
              data-testid="autoview-tab-grid"
            >
              <Network className="w-3 h-3" />
              SLD Grid
            </button>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {lastVerified && (
            <span
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-mono"
              data-testid="autoview-verified-badge"
            >
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              verified ✓
            </span>
          )}

          <button
            type="button"
            onClick={() => setIsExpanded((prev) => !prev)}
            className="p-1.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] rounded hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
            title={isExpanded ? "Collapse width" : "Expand width"}
            data-testid="autoview-expand-btn"
          >
            {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>

          <button
            type="button"
            onClick={() => setActiveView(null)}
            className="p-1.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] rounded hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
            title="Close panel"
            data-testid="autoview-close-btn"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Subsystem Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeView === "scada" && (
          <div className="space-y-4 text-xs font-sans" data-testid="autoview-scada-content">
            <div className="p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] space-y-2">
              <div className="flex items-center justify-between text-[11px]">
                <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
                  Primary MV Feeder Substation
                </span>
                <Badge variant="success" size="sm">
                  IEC 61850 Live
                </Badge>
              </div>
              <div className="grid grid-cols-3 gap-2 pt-2">
                <div className="p-2 bg-[var(--bg-input)] rounded-lg border border-[var(--border-primary)]">
                  <div className="text-[10px] text-[var(--text-tertiary)]">Bus Voltage</div>
                  <div className="text-sm font-mono font-semibold text-cyan-400">22.04 kV</div>
                  <div className="text-[9px] text-emerald-400">1.002 pu (Nominal)</div>
                </div>
                <div className="p-2 bg-[var(--bg-input)] rounded-lg border border-[var(--border-primary)]">
                  <div className="text-[10px] text-[var(--text-tertiary)]">Grid Freq</div>
                  <div className="text-sm font-mono font-semibold text-emerald-400">50.01 Hz</div>
                  <div className="text-[9px] text-[var(--text-muted)]">Stable sync</div>
                </div>
                <div className="p-2 bg-[var(--bg-input)] rounded-lg border border-[var(--border-primary)]">
                  <div className="text-[10px] text-[var(--text-tertiary)]">Feeder Load</div>
                  <div className="text-sm font-mono font-semibold text-amber-400">14.8 MVA</div>
                  <div className="text-[9px] text-[var(--text-muted)]">68% Capacity</div>
                </div>
              </div>
            </div>

            <div className="p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] space-y-2.5">
              <div className="text-[11px] font-semibold text-[var(--text-primary)]">Bay Breaker State Overview</div>
              <div className="space-y-1.5 font-mono text-[11px]">
                <div className="flex items-center justify-between p-2 bg-[var(--bg-input)] rounded border border-[var(--border-primary)]">
                  <span>CB-01 (Incomer 1)</span>
                  <Badge variant="success" size="sm">CLOSED</Badge>
                </div>
                <div className="flex items-center justify-between p-2 bg-[var(--bg-input)] rounded border border-[var(--border-primary)]">
                  <span>CB-02 (Bus Coupler)</span>
                  <Badge variant="neutral" size="sm">OPEN</Badge>
                </div>
                <div className="flex items-center justify-between p-2 bg-[var(--bg-input)] rounded border border-[var(--border-primary)]">
                  <span>CB-03 (Feeder West)</span>
                  <Badge variant="success" size="sm">CLOSED</Badge>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeView === "gis" && (
          <div className="space-y-4 text-xs font-sans" data-testid="autoview-gis-content">
            <div className="p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] space-y-2">
              <div className="flex items-center justify-between text-[11px]">
                <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-emerald-400" />
                  Geospatial Grid Corridors
                </span>
                <span className="font-mono text-[10px] text-[var(--text-tertiary)]">EPSG:3857</span>
              </div>
              <div className="h-44 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] flex flex-col items-center justify-center relative overflow-hidden p-4 text-center">
                {/* Visual grid illustration */}
                <div className="absolute inset-0 opacity-15 bg-[radial-gradient(var(--color-success,#10b981)_1px,transparent_1px)] [background-size:16px_16px]" />
                <Globe className="w-10 h-10 text-emerald-500/40 mb-2" />
                <div className="font-semibold text-[var(--text-primary)] text-xs">ArcGIS Online / Pro Map Active</div>
                <p className="text-[10px] text-[var(--text-tertiary)] max-w-xs mt-1">
                  Feeder F-07 corridor synchronized with CAD/GIS shapefiles. 14 substations mapped.
                </p>
              </div>
            </div>

            <div className="p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] space-y-2">
              <div className="text-[11px] font-semibold text-[var(--text-primary)]">Geospatial Validation Layers</div>
              <div className="space-y-1.5 font-mono text-[11px]">
                <div className="flex justify-between items-center p-2 bg-[var(--bg-input)] rounded border border-[var(--border-primary)]">
                  <span>Underground Cable Lengths:</span>
                  <span className="text-emerald-400">12.4 km (Verified)</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-[var(--bg-input)] rounded border border-[var(--border-primary)]">
                  <span>Substation Geotagging:</span>
                  <span className="text-emerald-400">100% Linked</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeView === "grid" && (
          <div className="space-y-4 text-xs font-sans" data-testid="autoview-grid-content">
            <div className="p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] space-y-2">
              <div className="flex items-center justify-between text-[11px]">
                <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                  <Network className="w-3.5 h-3.5 text-brand-400" />
                  Single Line Diagram (SLD) Snapshot
                </span>
                <span className="font-mono text-[10px] text-[var(--text-tertiary)]">ETAP Model Active</span>
              </div>
              <div className="h-44 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] flex flex-col items-center justify-center relative p-4 text-center">
                <div className="absolute inset-0 opacity-15 bg-[radial-gradient(var(--accent-primary,#3b82f6)_1px,transparent_1px)] [background-size:16px_16px]" />
                <Network className="w-10 h-10 text-brand-500/40 mb-2" />
                <div className="font-semibold text-[var(--text-primary)] text-xs">MV Bus & Branch Topology</div>
                <p className="text-[10px] text-[var(--text-tertiary)] max-w-xs mt-1">
                  132kV / 33kV / 11kV busbars and step-down transformers synchronized with Newton-Raphson model.
                </p>
              </div>
            </div>

            <div className="p-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] space-y-2">
              <div className="text-[11px] font-semibold text-[var(--text-primary)]">Active Bus Voltages & Flows</div>
              <div className="space-y-1.5 font-mono text-[11px]">
                <div className="flex justify-between items-center p-2 bg-[var(--bg-input)] rounded border border-[var(--border-primary)]">
                  <span>Bus-1 (Cairo West 132kV):</span>
                  <span className="text-brand-400">132.1 kV / 0.0°</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-[var(--bg-input)] rounded border border-[var(--border-primary)]">
                  <span>Bus-2 (Helwan MV 33kV):</span>
                  <span className="text-emerald-400">32.89 kV / -2.4°</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

export default AutoViewPanel;
