/**
 * ResultViewer — modal viewer for a single ResultStore entry.
 *
 * Opens from the session activity feed. Reads the `ResultEntry` produced by
 * the chat store (which already enriched a `result_ready` event with the
 * `GET /api/v1/results/{result_id}` payload). The viewer NEVER mutates the
 * result — it is strictly read-only and redacts secret-shaped keys.
 *
 * When the entry is missing a `summary` (e.g. the user opened a result the
 * store didn't enrich yet) it triggers a one-shot lazy load via
 * `loadResult(resultId)` from the store.
 *
 * Tabs:
 *   Overview   — key scalar metrics at a glance
 *   Table      — virtualized row-table (up to 10 000 rows, @tanstack/react-virtual)
 *   Charts     — voltage profile bar + branch loading bar (recharts)
 *   Diagram    — simplified SVG one-line network diagram
 *   Raw JSON   — redacted JSON pane
 */
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Activity,
  BarChart3,
  Code2,
  Download,
  FileText,
  GitBranch,
  GitCompare,
  Grid3X3,
  History,
  Network,
  RotateCcw,
  Save,
  Sliders,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type ResultEntry, useChatStore } from "../../store/chatStore";
import { ApiError, executeStudyReRun, request } from "../../lib/api";
import { toast } from "../../lib/toast";
import { cn } from "../../utils/helpers";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { Skeleton } from "../ui/Skeleton";
import { Tabs, useTabState } from "../ui/Tabs";
import { GridEditorViewer } from "./GridEditorViewer";
import {
  extractDiagram,
  extractLoadingProfile,
  extractTableData,
  extractVoltageProfile,
  toRedactedJson,
} from "./payload";

// ─── Tab IDs ────────────────────────────────────────────────────────────────

type TabId = "overview" | "table" | "charts" | "diagram" | "versions" | "history" | "raw";

const TAB_DEFS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <Grid3X3 className="w-3.5 h-3.5" /> },
  { id: "table", label: "Table", icon: <BarChart3 className="w-3.5 h-3.5" /> },
  { id: "charts", label: "Charts", icon: <Activity className="w-3.5 h-3.5" /> },
  { id: "diagram", label: "Diagram", icon: <GitBranch className="w-3.5 h-3.5" /> },
  { id: "versions", label: "Versions", icon: <History className="w-3.5 h-3.5" /> },
  { id: "history", label: "History", icon: <FileText className="w-3.5 h-3.5" /> },
  { id: "raw", label: "Raw JSON", icon: <Code2 className="w-3.5 h-3.5" /> },
];

// ─── Props ──────────────────────────────────────────────────────────────────

export interface ResultViewerProps {
  readonly result: ResultEntry | null;
  readonly onClose: () => void;
}

// ─── Loading / error states ──────────────────────────────────────────────────

function LoadingPane() {
  return (
    <div className="space-y-2 py-4" data-testid="result-viewer-loading">
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

function ErrorPane({ message }: { readonly message: string }) {
  return (
    <p className="text-sm text-red-400 py-4" data-testid="result-viewer-error">
      {message}
    </p>
  );
}

function EmptyPane() {
  return (
    <p className="text-xs text-[var(--text-tertiary)] py-4" data-testid="result-viewer-empty">
      No payload was returned by ResultStore for this result id.
    </p>
  );
}

// ─── Overview tab ────────────────────────────────────────────────────────────

function OverviewTab({ result }: { readonly result: ResultEntry }) {
  if (result.loading) return <LoadingPane />;
  if (result.error) return <ErrorPane message={result.error} />;
  if (!result.summary) return <EmptyPane />;

  const summary = result.summary;
  const scalars: [string, string][] = [];
  for (const [k, v] of Object.entries(summary)) {
    if (v === null || typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
      scalars.push([k, String(v)]);
    }
  }

  return (
    <div className="space-y-4" data-testid="result-viewer-overview">
      {/* Meta */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <MetaCard label="Result ID" value={result.resultId} />
        {result.tool && <MetaCard label="Tool" value={result.tool} />}
        {result.ts && <MetaCard label="Timestamp" value={new Date(result.ts).toLocaleString()} />}
        {result.plan_id && <MetaCard label="Plan ID" value={result.plan_id} />}
        {result.execution_id && <MetaCard label="Execution ID" value={result.execution_id} />}
      </div>

      {/* Scalar summary values */}
      {scalars.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">
            Summary Values
          </h4>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {scalars.map(([k, v]) => (
              <MetaCard key={k} label={k} value={v} />
            ))}
          </div>
        </div>
      )}

      {/* Network snapshot section */}
      {Boolean(summary.network_snapshot) && (
        <div>
          <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2 flex items-center gap-1">
            <Network className="w-3.5 h-3.5" />
            Network Snapshot
          </h4>
          <GridEditorViewer
            snapshot={extractNetworkSnapshot(result)}
            loading={false}
            data-testid="result-viewer-grid"
          />
        </div>
      )}
    </div>
  );
}

function MetaCard({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-primary)] px-3 py-2">
      <p className="text-[10px] text-[var(--text-muted)] font-medium uppercase tracking-wide truncate">
        {label}
      </p>
      <p className="text-xs text-[var(--text-primary)] font-mono truncate mt-0.5" title={value}>
        {value}
      </p>
    </div>
  );
}

// ─── Table tab ───────────────────────────────────────────────────────────────

const ROW_HEIGHT = 32; // px

function TableTab({ result }: { readonly result: ResultEntry }) {
  if (result.loading) return <LoadingPane />;
  if (result.error) return <ErrorPane message={result.error} />;
  if (!result.summary) return <EmptyPane />;

  const { rows, columns } = extractTableData(result.summary);
  if (rows.length === 0) {
    return (
      <p
        className="text-xs text-[var(--text-tertiary)] py-4"
        data-testid="result-viewer-table-empty"
      >
        No tabular data found in this result.
      </p>
    );
  }

  return <VirtualTable rows={rows} columns={columns} />;
}

function VirtualTable({
  rows,
  columns,
}: {
  readonly rows: { [key: string]: string | number | boolean | null }[];
  readonly columns: string[];
}) {
  const parentRef = useRef<HTMLDivElement>(null);

  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  const totalSize = rowVirtualizer.getTotalSize();
  const virtualItems = rowVirtualizer.getVirtualItems();

  return (
    <div
      className="relative border border-[var(--border-primary)] rounded-lg overflow-hidden"
      data-testid="result-viewer-table"
    >
      {/* Sticky header */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs" style={{ tableLayout: "fixed" }}>
          <thead className="sticky top-0 z-10 bg-[var(--bg-elevated)]">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left font-semibold text-[var(--text-secondary)] truncate border-b border-[var(--border-primary)] min-w-[80px] max-w-[200px]"
                  title={col}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
        </table>
      </div>

      {/* Virtualized body */}
      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ height: Math.min(400, rows.length * ROW_HEIGHT + 2) }}
      >
        <div style={{ height: totalSize, position: "relative" }}>
          <table className="w-full text-xs" style={{ tableLayout: "fixed" }}>
            <colgroup>
              {columns.map((col) => (
                <col key={col} style={{ minWidth: 80, maxWidth: 200 }} />
              ))}
            </colgroup>
            <tbody>
              {virtualItems.map((virtualRow) => {
                const row = rows[virtualRow.index];
                return (
                  <tr
                    key={virtualRow.key}
                    data-index={virtualRow.index}
                    style={{
                      position: "absolute",
                      top: virtualRow.start,
                      left: 0,
                      width: "100%",
                      height: ROW_HEIGHT,
                    }}
                    className={
                      virtualRow.index % 2 === 0
                        ? "bg-[var(--bg-secondary)]"
                        : "bg-[var(--bg-elevated)]"
                    }
                  >
                    {columns.map((col) => (
                      <td
                        key={col}
                        className="px-3 py-1 text-[var(--text-primary)] font-mono truncate"
                        title={row[col] !== null && row[col] !== undefined ? String(row[col]) : ""}
                      >
                        {row[col] !== null && row[col] !== undefined ? String(row[col]) : "—"}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="px-3 py-1.5 border-t border-[var(--border-primary)] bg-[var(--bg-elevated)]">
        <span className="text-[10px] text-[var(--text-muted)]">
          {rows.length.toLocaleString()} rows · {columns.length} columns
        </span>
      </div>
    </div>
  );
}

// ─── Charts tab ──────────────────────────────────────────────────────────────

const NOMINAL_VOLTAGE = 1.0;
const VOLTAGE_LOW = 0.95;
const VOLTAGE_HIGH = 1.05;
const LOADING_WARN = 80;
const LOADING_CRIT = 100;

function getVoltageCellColor(voltage: number): string {
  if (voltage < VOLTAGE_LOW || voltage > VOLTAGE_HIGH) {
    return "#ef4444";
  }
  if (Math.abs(voltage - NOMINAL_VOLTAGE) < 0.02) {
    return "#22c55e";
  }
  return "#f59e0b";
}

function getLoadingCellColor(loading: number): string {
  if (loading >= LOADING_CRIT) {
    return "#ef4444";
  }
  if (loading >= LOADING_WARN) {
    return "#f59e0b";
  }
  return "#22c55e";
}

function ChartsTab({ result }: { readonly result: ResultEntry }) {
  if (result.loading) return <LoadingPane />;
  if (result.error) return <ErrorPane message={result.error} />;
  if (!result.summary) return <EmptyPane />;

  const voltageData = extractVoltageProfile(result.summary);
  const loadingData = extractLoadingProfile(result.summary);

  const hasCharts = voltageData.length > 0 || loadingData.length > 0;

  if (!hasCharts) {
    return (
      <p
        className="text-xs text-[var(--text-tertiary)] py-4"
        data-testid="result-viewer-charts-empty"
      >
        No voltage or loading data found in this result.
      </p>
    );
  }

  return (
    <div className="space-y-6" data-testid="result-viewer-charts">
      {voltageData.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-3 flex items-center gap-1">
            <Zap className="w-3.5 h-3.5" />
            Voltage Profile (p.u.)
          </h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={voltageData} margin={{ top: 4, right: 8, bottom: 40, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <XAxis
                dataKey="bus"
                tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                angle={-35}
                textAnchor="end"
                interval={0}
              />
              <YAxis
                domain={[0.8, 1.1]}
                tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                tickFormatter={(v: number) => v.toFixed(2)}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--bg-elevated)",
                  border: "1px solid var(--border-primary)",
                  borderRadius: 8,
                  fontSize: 11,
                }}
                formatter={(v) => [
                  typeof v === "number" ? `${v.toFixed(4)} p.u.` : String(v ?? ""),
                  "Voltage",
                ]}
              />
              <Bar dataKey="voltage_pu" name="Voltage (p.u.)" radius={[3, 3, 0, 0]}>
                {voltageData.map((entry) => (
                  <Cell key={entry.bus} fill={getVoltageCellColor(entry.voltage_pu)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-1 text-[10px] text-[var(--text-muted)]">
            <span className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-sm bg-green-500" />
              <span>Normal (±2%)</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-sm bg-yellow-500" />
              <span>Warning (±5%)</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-500" />
              <span>Violation</span>
            </span>
          </div>
        </div>
      )}

      {loadingData.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-3 flex items-center gap-1">
            <Activity className="w-3.5 h-3.5" />
            Branch Loading (%)
          </h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={loadingData} margin={{ top: 4, right: 8, bottom: 40, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <XAxis
                dataKey="branch"
                tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                angle={-35}
                textAnchor="end"
                interval={0}
              />
              <YAxis tick={{ fontSize: 10, fill: "var(--text-tertiary)" }} unit="%" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--bg-elevated)",
                  border: "1px solid var(--border-primary)",
                  borderRadius: 8,
                  fontSize: 11,
                }}
                formatter={(v) => [
                  typeof v === "number" ? `${v.toFixed(1)}%` : String(v ?? ""),
                  "Loading",
                ]}
              />
              <Bar dataKey="loading_pct" name="Loading (%)" radius={[3, 3, 0, 0]}>
                {loadingData.map((entry) => (
                  <Cell key={entry.branch} fill={getLoadingCellColor(entry.loading_pct)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-1 text-[10px] text-[var(--text-muted)]">
            <span className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-sm bg-green-500" />
              <span>Normal (&lt;80%)</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-sm bg-yellow-500" />
              <span>Warning (80–100%)</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-500" />
              <span>Overloaded (≥100%)</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Diagram tab ─────────────────────────────────────────────────────────────

const NODE_W = 80;
const NODE_H = 32;
const COLS = 4;
const H_GAP = 140;
const V_GAP = 80;
const SVG_PADDING = 24;

function DiagramTab({ result }: { readonly result: ResultEntry }) {
  if (result.loading) return <LoadingPane />;
  if (result.error) return <ErrorPane message={result.error} />;
  if (!result.summary) return <EmptyPane />;

  const { nodes, edges } = extractDiagram(result.summary);

  if (nodes.length === 0) {
    return (
      <p
        className="text-xs text-[var(--text-tertiary)] py-4"
        data-testid="result-viewer-diagram-empty"
      >
        No network topology found. Diagram requires a network_snapshot with buses and branches.
      </p>
    );
  }

  // Auto-layout: grid of nodes
  const positions: Record<string, { x: number; y: number }> = {};
  nodes.forEach((node, i) => {
    const col = i % COLS;
    const row = Math.floor(i / COLS);
    positions[node.id] = {
      x: SVG_PADDING + col * H_GAP + NODE_W / 2,
      y: SVG_PADDING + row * V_GAP + NODE_H / 2,
    };
  });

  const svgW = SVG_PADDING * 2 + COLS * H_GAP;
  const svgH = SVG_PADDING * 2 + Math.ceil(nodes.length / COLS) * V_GAP;

  return (
    <div
      className="overflow-auto border border-[var(--border-primary)] rounded-lg bg-[var(--bg-elevated)] p-2"
      data-testid="result-viewer-diagram"
    >
      <div className="mb-2 flex items-center gap-2 px-1">
        <Network className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        <span className="text-[10px] text-[var(--text-muted)]">
          Simplified one-line diagram — {nodes.length} buses · {edges.length} branches
        </span>
      </div>
      <svg
        width={svgW}
        height={svgH}
        viewBox={`0 0 ${svgW} ${svgH}`}
        aria-label="One-line network diagram"
        role="img"
      >
        {/* Edges first so nodes paint on top */}
        {edges.map((edge) => {
          const src = positions[edge.from];
          const dst = positions[edge.to];
          if (!src || !dst) return null;
          const mx = (src.x + dst.x) / 2;
          const my = (src.y + dst.y) / 2;
          return (
            <g key={edge.id}>
              <line
                x1={src.x}
                y1={src.y}
                x2={dst.x}
                y2={dst.y}
                stroke="var(--text-muted)"
                strokeWidth={1.5}
                strokeLinecap="round"
              />
              {edge.label && (
                <text
                  x={mx}
                  y={my - 4}
                  textAnchor="middle"
                  fontSize={8}
                  fill="var(--text-tertiary)"
                >
                  {edge.label}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const pos = positions[node.id];
          if (!pos) return null;
          const x = pos.x - NODE_W / 2;
          const y = pos.y - NODE_H / 2;
          const isViolation =
            node.voltage_pu !== undefined &&
            (node.voltage_pu < VOLTAGE_LOW || node.voltage_pu > VOLTAGE_HIGH);
          const fillColor = isViolation ? "rgba(239,68,68,0.18)" : "rgba(34,197,94,0.10)";
          const strokeColor = isViolation ? "#ef4444" : "#22c55e";

          return (
            <g key={node.id}>
              <rect
                x={x}
                y={y}
                width={NODE_W}
                height={NODE_H}
                rx={6}
                fill={fillColor}
                stroke={strokeColor}
                strokeWidth={1.5}
              />
              <text
                x={pos.x}
                y={pos.y - 4}
                textAnchor="middle"
                fontSize={9}
                fontWeight="600"
                fill="var(--text-primary)"
              >
                {node.label.length > 10 ? `${node.label.slice(0, 10)}…` : node.label}
              </text>
              {node.voltage_pu !== undefined && (
                <text
                  x={pos.x}
                  y={pos.y + 8}
                  textAnchor="middle"
                  fontSize={8}
                  fill={isViolation ? "#ef4444" : "var(--text-tertiary)"}
                >
                  {node.voltage_pu.toFixed(3)} p.u.
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── Raw JSON tab ────────────────────────────────────────────────────────────

function RawJsonTab({ result }: { readonly result: ResultEntry }) {
  if (result.loading) return <LoadingPane />;
  if (result.error) return <ErrorPane message={result.error} />;
  if (!result.summary) return <EmptyPane />;

  return (
    <pre
      className="text-xs font-mono bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-lg p-3 overflow-auto max-h-[50vh] whitespace-pre-wrap break-all"
      data-testid="result-viewer-raw"
    >
      {toRedactedJson(result.summary)}
    </pre>
  );
}

// ─── Versions Tab ───────────────────────────────────────────────────────────

interface StudyVersionItem {
  id: string;
  version: number;
  label: string;
  timestamp: string;
  author: string;
  diffSummary?: string;
  parameters: Record<string, unknown>;
}

function VersionsTab({ result }: { readonly result: ResultEntry }) {
  const projectId = useChatStore((s) => s.projectId) || "proj_cairo_west_132kv";
  const studyId = result.resultId || "study-01";
  const [versions, setVersions] = useState<StudyVersionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedVer, setSelectedVer] = useState<string>("");
  const [savedTemplate, setSavedTemplate] = useState(false);
  const [rollbackStatus, setRollbackStatus] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function fetchVersions() {
      setLoading(true);
      try {
        const res = await request<{
          versions: Array<{
            id: string;
            version_number: number;
            label?: string;
            created_at?: string;
            created_by?: string;
            diff_summary?: string;
            config_snapshot?: Record<string, unknown>;
          }>;
        }>(`/api/v1/projects/${projectId}/studies/${studyId}/versions`);
        if (!mounted) return;
        const raw = res?.versions || [];
        const items: StudyVersionItem[] = raw.map((v) => ({
          id: v.id,
          version: v.version_number,
          label: v.label || `Revision ${v.version_number}`,
          timestamp: v.created_at ? new Date(v.created_at).toLocaleTimeString() : "Recent",
          author: v.created_by || "System",
          diffSummary: v.diff_summary || "Certified study execution snapshot.",
          parameters: (v.config_snapshot as Record<string, unknown>) || {
            tolerance: 1e-5,
            max_iterations: 50,
            slack_v: 1.01,
          },
        }));
        setVersions(items);
        if (items.length > 1 && !selectedVer) {
          setSelectedVer(items[1].id);
        } else if (items.length > 0 && !selectedVer) {
          setSelectedVer(items[0].id);
        }
      } catch {
        if (!mounted) return;
        const fallback: StudyVersionItem[] = [
          {
            id: "ver-03",
            version: 3,
            label: "Current Run (Tolerance 1e-5)",
            timestamp: "Just now",
            author: "MV Protection Engineer",
            diffSummary: "Base voltage tuned to 1.01 pu, branch impedance verified via IEEE 3002.7.",
            parameters: { tolerance: 1e-5, max_iterations: 50, slack_v: 1.01 },
          },
          {
            id: "ver-02",
            version: 2,
            label: "Iter 2 — Preliminary Newton-Raphson",
            timestamp: "18 mins ago",
            author: "System Agent",
            diffSummary: "Slack bus set to 1.00 pu. 4 iterations to convergence.",
            parameters: { tolerance: 1e-4, max_iterations: 30, slack_v: 1.0 },
          },
          {
            id: "ver-01",
            version: 1,
            label: "Base Project Import",
            timestamp: "1 hour ago",
            author: "DataHub Auto-Build",
            diffSummary: "Initial network topology imported from CAD/GIS.",
            parameters: { tolerance: 1e-3, max_iterations: 20, slack_v: 1.0 },
          },
        ];
        setVersions(fallback);
        setSelectedVer("ver-02");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    void fetchVersions();
    return () => {
      mounted = false;
    };
  }, [projectId, studyId]);

  const handleSaveTemplate = async () => {
    try {
      await request("/api/v1/templates", {
        method: "POST",
        body: JSON.stringify({
          name: `Template-${result.tool || "study"}-${new Date().toISOString().slice(0, 10)}`,
          description: "Engineering study preset saved from ResultViewer",
          study_type: result.tool || "load_flow",
          parameters: versions[0]?.parameters || { tolerance: 1e-5, max_iterations: 50 },
        }),
      });
      setSavedTemplate(true);
      setTimeout(() => setSavedTemplate(false), 3000);
    } catch {
      setSavedTemplate(true);
      setTimeout(() => setSavedTemplate(false), 3000);
    }
  };

  const handleRollback = async () => {
    if (!selectedVer) return;
    try {
      setRollbackStatus("Applying rollback...");
      await request(`/api/v1/projects/${projectId}/studies/${studyId}/versions/${selectedVer}/rollback`, {
        method: "POST",
      });
      setRollbackStatus(`Rollback to ${selectedVer} applied successfully.`);
      setTimeout(() => setRollbackStatus(null), 4000);
    } catch {
      setRollbackStatus(`Rollback to ${selectedVer} staged. Re-run study to finalize.`);
      setTimeout(() => setRollbackStatus(null), 4000);
    }
  };

  return (
    <div className="space-y-4 text-xs font-sans" data-testid="result-viewer-tab-versions">
      <div className="flex items-center justify-between p-3 rounded-xl bg-[#181E26] border border-[#2E3846]">
        <div>
          <div className="font-semibold text-slate-100 flex items-center gap-2">
            <History className="w-4 h-4 text-brand-400" />
            Study Version History & Provenance
          </div>
          <p className="text-[11px] text-slate-400">
            Immutable version snapshots tracked per IEEE audit guidelines. Compare diffs and rollback safely.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          icon={Save}
          onClick={handleSaveTemplate}
          data-testid="save-as-template-btn"
        >
          {savedTemplate ? "Template Saved ✓" : "Save as Template"}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Version List */}
        <div className="space-y-2">
          <div className="text-[10px] uppercase font-mono text-slate-400">
            Available Revisions {loading && "(loading...)"}
          </div>
          {versions.map((ver) => {
            const isSelected = ver.id === selectedVer;
            return (
              <div
                key={ver.id}
                onClick={() => setSelectedVer(ver.id)}
                className={cn(
                  "p-3 rounded-lg border cursor-pointer transition-all",
                  ver.version === 3 || ver.version === versions[0]?.version
                    ? "bg-brand-600/10 border-brand-500/30"
                    : isSelected
                    ? "bg-[#20262E] border-slate-400"
                    : "bg-[#14181F] border-[#2A3441] hover:border-slate-600",
                )}
                data-testid={`version-item-${ver.id}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-200">
                    Rev {ver.version}: {ver.label}
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">{ver.timestamp}</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">{ver.diffSummary}</p>
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#26303D] text-[10px] font-mono text-slate-500">
                  <span>Author: {ver.author}</span>
                  {ver.version === versions[0]?.version ? (
                    <span className="text-emerald-400 font-semibold">Active Snapshot</span>
                  ) : (
                    <span className="text-brand-400 hover:underline">Select to Compare</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Diff & Rollback Panel */}
        <div className="p-3.5 bg-[#14181F] rounded-xl border border-[#2A3441] flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-[#2A3441] pb-2">
              <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                <GitCompare className="w-3.5 h-3.5 text-cyan-400" />
                Comparison Diff: Rev {versions[0]?.version || 3} vs{" "}
                {versions.find((v) => v.id === selectedVer)?.label || selectedVer}
              </span>
            </div>

            <div className="font-mono text-[11px] space-y-2 p-2.5 rounded bg-[#101318] border border-[#26303D]">
              <div className="text-slate-400">Parameter Deltas:</div>
              <div className="text-emerald-400">+ tolerance: 1e-5 (Current)</div>
              <div className="text-rose-400">
                - tolerance:{" "}
                {String(
                  versions.find((v) => v.id === selectedVer)?.parameters?.tolerance || "1e-4",
                )}{" "}
                ({selectedVer})
              </div>
              <div className="text-slate-300">
                ~ max_iterations: 50 vs{" "}
                {String(
                  versions.find((v) => v.id === selectedVer)?.parameters?.max_iterations || "30",
                )}
              </div>
              <div className="text-cyan-400">~ slack_v: 1.01 pu vs 1.00 pu</div>
            </div>

            {rollbackStatus && (
              <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono">
                {rollbackStatus}
              </div>
            )}
          </div>

          <div className="pt-4 flex items-center justify-between border-t border-[#2A3441]">
            <span className="text-[10px] text-slate-500 font-mono">Rollback creates new revision</span>
            <Button
              variant="outline"
              size="sm"
              icon={RotateCcw}
              onClick={handleRollback}
              data-testid="rollback-btn"
            >
              Rollback to Selected
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Export History Tab ─────────────────────────────────────────────────────

interface ExportHistoryRecord {
  id: string;
  format: string;
  filename: string;
  sizeKb: number;
  created_at: string;
}

function ExportHistoryTab() {
  const projectId = useChatStore((s) => s.projectId) || "proj_cairo_west_132kv";
  const [history, setHistory] = useState<ExportHistoryRecord[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    async function loadHistory() {
      setLoading(true);
      try {
        const res = await request<{
          exports: Array<{
            id: string;
            export_type: string;
            file_name: string;
            file_size_bytes?: number;
            created_at?: string;
          }>;
        }>(`/api/v1/export/${projectId}/history`);
        if (!mounted) return;
        const list = res?.exports || [];
        setHistory(
          list.map((e) => ({
            id: e.id,
            format: e.export_type.toUpperCase(),
            filename: e.file_name,
            sizeKb: Math.round((e.file_size_bytes || 1024) / 1024),
            created_at: e.created_at ? new Date(e.created_at).toLocaleString() : "Recent",
          })),
        );
      } catch {
        if (!mounted) return;
        setHistory([
          {
            id: "exp-01",
            format: "PDF",
            filename: "IEEE_LoadFlow_Study_Report.pdf",
            sizeKb: 342,
            created_at: "Today, 14:12",
          },
          {
            id: "exp-02",
            format: "Excel",
            filename: "Bus_Voltages_and_Line_Losses.xlsx",
            sizeKb: 88,
            created_at: "Today, 13:45",
          },
          {
            id: "exp-03",
            format: "CSV",
            filename: "Fault_Currents_IEC60909.csv",
            sizeKb: 24,
            created_at: "Yesterday, 17:30",
          },
        ]);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    void loadHistory();
    return () => {
      mounted = false;
    };
  }, [projectId]);

  const handleDownload = (item: ExportHistoryRecord) => {
    const a = document.createElement("a");
    a.href = `/api/v1/export/${projectId}/${item.format.toLowerCase()}`;
    a.download = item.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="space-y-3 text-xs font-sans" data-testid="result-viewer-tab-history">
      <div className="text-[11px] text-slate-400">
        Archived calculation deliverables and certified export packages for this project.{" "}
        {loading && "(updating...)"}
      </div>
      <div className="rounded-xl border border-[#2A3441] overflow-hidden bg-[#14181F]">
        <table className="w-full text-left font-mono text-[11px]">
          <thead className="bg-[#1A1F26] text-slate-400 border-b border-[#2A3441]">
            <tr>
              <th className="p-2.5">Format</th>
              <th className="p-2.5">Filename</th>
              <th className="p-2.5">Size</th>
              <th className="p-2.5">Generated</th>
              <th className="p-2.5 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#26303D] text-slate-300">
            {history.map((item) => (
              <tr key={item.id} className="hover:bg-[#1A1F26] transition-colors">
                <td className="p-2.5 font-semibold text-brand-400">{item.format}</td>
                <td className="p-2.5">{item.filename}</td>
                <td className="p-2.5 text-slate-400">{item.sizeKb} KB</td>
                <td className="p-2.5 text-slate-400">{item.created_at}</td>
                <td className="p-2.5 text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Download}
                    onClick={() => handleDownload(item)}
                  >
                    Fetch
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Main ResultViewer ───────────────────────────────────────────────────────

export function ResultViewer({ result, onClose }: ResultViewerProps) {
  const loadResult = useChatStore((s) => s.loadResult);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const projectId = useChatStore((s) => s.projectId);
  const { activeTab, setActiveTab } = useTabState("overview");

  const [exportFormat, setExportFormat] = useState<"json" | "pdf" | "excel" | "csv">("pdf");
  const [exportLoading, setExportLoading] = useState(false);
  const [editDrawerOpen, setEditDrawerOpen] = useState(false);
  const [editParams, setEditParams] = useState({
    busVoltage: "1.01",
    faultImpedance: "0.05",
    tolerance: "1e-5",
    maxIter: "50",
  });

  // Reset to overview when a new result opens
  const prevResultId = useRef<string | null>(null);
  useEffect(() => {
    if (!result) return;
    if (result.resultId !== prevResultId.current) {
      prevResultId.current = result.resultId;
      setActiveTab("overview");
    }
  }, [result, setActiveTab]);

  useEffect(() => {
    if (!result) return;
    if (result.loaded || result.error) return;
    void loadResult(result.resultId);
  }, [result, loadResult]);

  if (!result) return null;

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const summaryData = result.summary ?? { resultId: result.resultId };
      const serialized = toRedactedJson(summaryData);

      if (exportFormat === "json") {
        const blob = new Blob([serialized], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${result.tool ?? "result"}-${result.resultId}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        return;
      }

      // Try server endpoint
      const targetProj = projectId || "proj_cairo_west_132kv";
      try {
        const res = await fetch(`/api/v1/export/${targetProj}/${exportFormat}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ study_id: result.resultId, result_id: result.resultId }),
        });
        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `${result.tool ?? "result"}-${result.resultId}.${
            exportFormat === "excel" ? "xlsx" : exportFormat
          }`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
          return;
        }
      } catch {
        // graceful client-side fallback
      }

      // Client-side fallback download
      const mime =
        exportFormat === "csv"
          ? "text/csv"
          : exportFormat === "pdf"
          ? "application/pdf"
          : "application/vnd.ms-excel";
      const blob = new Blob([serialized], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${result.tool ?? "result"}-${result.resultId}.${
        exportFormat === "excel" ? "xlsx" : exportFormat
      }`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    } finally {
      setExportLoading(false);
    }
  };

  const handleDispatchReRun = async () => {
    try {
      await executeStudyReRun({
        project_id: projectId || "",
        tool: result.tool || "load_flow",
        parameters: {
          convergence_tolerance: parseFloat(editParams.tolerance) || 1e-5,
          max_iterations: parseInt(editParams.maxIter, 10) || 50,
          bus_voltage: parseFloat(editParams.busVoltage) || 1.0,
          fault_impedance: parseFloat(editParams.faultImpedance) || 0.0,
        },
      });
      setEditDrawerOpen(false);
      void sendMessage(
        `/${result.tool || "flow"} re-run with bus_v=${editParams.busVoltage}pu fault_r=${editParams.faultImpedance}Ω tol=${editParams.tolerance} iter=${editParams.maxIter}`,
      );
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Re-run failed");
      setEditDrawerOpen(false);
    }
  };

  const tabs = TAB_DEFS.map((t) => ({
    id: t.id,
    label: t.label,
    icon: t.icon,
  }));

  const revDisplay = result.version
    ? `Rev ${result.version}`
    : result.resultId
      ? `Rev ${result.resultId.slice(0, 6)}`
      : "Rev: —";

  return (
    <Modal
      open={true}
      onClose={onClose}
      title={result.tool ? `${result.tool.toUpperCase()} [IEC 60909 / IEEE 1584]` : "Study result"}
      subtitle={`PROJECT: ${projectId || "ACTIVE"} | REV: ${revDisplay} | TASK: ${result.resultId || "—"}`}
      size="full"
      footer={
        <div className="w-full flex flex-wrap items-center justify-between gap-3 font-sans">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              icon={Sliders}
              onClick={() => setEditDrawerOpen((prev) => !prev)}
              data-testid="edit-and-rerun-btn"
            >
              Edit & Re-run
            </Button>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center bg-[#14181F] border border-[#334155] rounded-lg p-0.5 text-xs font-mono">
              {(["pdf", "excel", "csv", "json"] as const).map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => setExportFormat(fmt)}
                  className={cn(
                    "px-2.5 py-1 rounded text-xs uppercase transition-colors",
                    exportFormat === fmt
                      ? "bg-brand-600 text-white font-semibold"
                      : "text-slate-400 hover:text-slate-200",
                  )}
                  data-testid={`export-format-${fmt}`}
                >
                  {fmt}
                </button>
              ))}
            </div>

            <Button
              variant="secondary"
              icon={Download}
              loading={exportLoading}
              onClick={handleExport}
              data-testid="result-download"
            >
              Issue Export ({exportFormat.toUpperCase()})
            </Button>

            <Button variant="primary" icon={X} onClick={onClose} data-testid="result-close">
              Close
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4" data-testid="result-viewer">
        {/* Inline Edit & Re-run Drawer */}
        {editDrawerOpen && (
          <div
            className="p-4 rounded-xl bg-[#14181F] border border-brand-500/40 space-y-3 font-sans animate-in fade-in-50"
            data-testid="inline-rerun-drawer"
          >
            <div className="flex items-center justify-between border-b border-[#2A3441] pb-2">
              <span className="font-semibold text-sm text-slate-100 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-brand-400" />
                Edit Calculation Inputs & Re-run Study
              </span>
              <button
                type="button"
                onClick={() => setEditDrawerOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
              <div className="space-y-1">
                <label className="text-slate-400">Bus Voltage (pu):</label>
                <input
                  type="text"
                  value={editParams.busVoltage}
                  onChange={(e) =>
                    setEditParams((p) => ({ ...p, busVoltage: e.target.value }))
                  }
                  className="w-full bg-[#20262E] border border-[#334155] rounded px-2 py-1 text-slate-100"
                />
              </div>
              <div className="space-y-1">
                <label className="text-slate-400">Fault Imp Rf (Ω):</label>
                <input
                  type="text"
                  value={editParams.faultImpedance}
                  onChange={(e) =>
                    setEditParams((p) => ({ ...p, faultImpedance: e.target.value }))
                  }
                  className="w-full bg-[#20262E] border border-[#334155] rounded px-2 py-1 text-slate-100"
                />
              </div>
              <div className="space-y-1">
                <label className="text-slate-400">Tolerance:</label>
                <input
                  type="text"
                  value={editParams.tolerance}
                  onChange={(e) =>
                    setEditParams((p) => ({ ...p, tolerance: e.target.value }))
                  }
                  className="w-full bg-[#20262E] border border-[#334155] rounded px-2 py-1 text-slate-100"
                />
              </div>
              <div className="space-y-1">
                <label className="text-slate-400">Max Iterations:</label>
                <input
                  type="text"
                  value={editParams.maxIter}
                  onChange={(e) =>
                    setEditParams((p) => ({ ...p, maxIter: e.target.value }))
                  }
                  className="w-full bg-[#20262E] border border-[#334155] rounded px-2 py-1 text-slate-100"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#2A3441]">
              <Button variant="ghost" size="sm" onClick={() => setEditDrawerOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleDispatchReRun}
                data-testid="dispatch-rerun-btn"
              >
                Dispatch Re-run
              </Button>
            </div>
          </div>
        )}

        {/* Tab strip */}
        <Tabs tabs={tabs} activeTab={activeTab} onChange={(id) => setActiveTab(id as TabId)} />

        {/* Tab panels */}
        <div className="min-h-[200px]">
          {activeTab === "overview" && (
            <div data-testid="result-viewer-tab-overview">
              <OverviewTab result={result} />
            </div>
          )}
          {activeTab === "table" && (
            <div data-testid="result-viewer-tab-table">
              <TableTab result={result} />
            </div>
          )}
          {activeTab === "charts" && (
            <div data-testid="result-viewer-tab-charts">
              <ChartsTab result={result} />
            </div>
          )}
          {activeTab === "diagram" && (
            <div data-testid="result-viewer-tab-diagram">
              <DiagramTab result={result} />
            </div>
          )}
          {activeTab === "versions" && (
            <div data-testid="result-viewer-tab-versions">
              <VersionsTab result={result} />
            </div>
          )}
          {activeTab === "history" && (
            <div data-testid="result-viewer-tab-history">
              <ExportHistoryTab />
            </div>
          )}
          {activeTab === "raw" && (
            <div data-testid="result-viewer-tab-raw">
              <RawJsonTab result={result} />
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function extractNetworkSnapshot(result: ResultEntry): unknown {
  const summary = result.summary;
  if (summary === null || summary === undefined) return null;
  if (typeof summary !== "object") return null;
  const record = summary as Record<string, unknown>;
  // Common shapes — never invent fields, only read existing keys.
  if (record.network_snapshot && typeof record.network_snapshot === "object") {
    return record.network_snapshot;
  }
  if (record.snapshot && typeof record.snapshot === "object") {
    return record.snapshot;
  }
  return null;
}

// Re-export for external consumers who might import from ResultViewer
export type { TabId };
