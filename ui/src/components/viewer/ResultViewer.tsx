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
  GitBranch,
  Grid3X3,
  Network,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useRef } from "react";
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

type TabId = "overview" | "table" | "charts" | "diagram" | "raw";

const TAB_DEFS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <Grid3X3 className="w-3.5 h-3.5" /> },
  { id: "table", label: "Table", icon: <BarChart3 className="w-3.5 h-3.5" /> },
  { id: "charts", label: "Charts", icon: <Activity className="w-3.5 h-3.5" /> },
  { id: "diagram", label: "Diagram", icon: <GitBranch className="w-3.5 h-3.5" /> },
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

// ─── Main ResultViewer ───────────────────────────────────────────────────────

export function ResultViewer({ result, onClose }: ResultViewerProps) {
  const loadResult = useChatStore((s) => s.loadResult);
  const { activeTab, setActiveTab } = useTabState("overview");

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
    // result_ready marks new entries loading=true (announcement pending
    // enrichment) — the guard must not check `loading` or the lazy load
    // could never start and the viewer would stay on its skeleton forever.
    if (result.loaded || result.error) return;
    void loadResult(result.resultId);
  }, [result, loadResult]);

  if (!result) return null;

  const handleDownload = () => {
    try {
      const blob = new Blob([toRedactedJson(result.summary ?? { resultId: result.resultId })], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${result.tool ?? "result"}-${result.resultId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      // No-op: download is a UX nicety, never a critical path.
    }
  };

  const tabs = TAB_DEFS.map((t) => ({
    id: t.id,
    label: t.label,
    icon: t.icon,
  }));

  return (
    <Modal
      open={true}
      onClose={onClose}
      title={result.tool ?? "Study result"}
      subtitle={result.resultId}
      size="full"
      footer={
        <>
          <Button
            variant="secondary"
            icon={Download}
            onClick={handleDownload}
            data-testid="result-download"
          >
            Download JSON
          </Button>
          <Button variant="primary" icon={X} onClick={onClose} data-testid="result-close">
            Close
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4" data-testid="result-viewer">
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
